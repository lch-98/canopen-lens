#include "analyzer.hpp"

#include <algorithm>
#include <deque>

namespace col {

AxisState decode_statusword(uint16_t sw) {
    if ((sw & 0x4F) == 0x00) return AxisState::NOT_READY_TO_SWITCH_ON;
    if ((sw & 0x4F) == 0x40) return AxisState::SWITCH_ON_DISABLED;
    if ((sw & 0x6F) == 0x21) return AxisState::READY_TO_SWITCH_ON;
    if ((sw & 0x6F) == 0x23) return AxisState::SWITCHED_ON;
    if ((sw & 0x6F) == 0x27) return AxisState::OPERATION_ENABLED;
    if ((sw & 0x6F) == 0x07) return AxisState::QUICK_STOP_ACTIVE;
    if ((sw & 0x4F) == 0x0F) return AxisState::FAULT_REACTION_ACTIVE;
    if ((sw & 0x4F) == 0x08) return AxisState::FAULT;
    return AxisState::UNKNOWN;
}

CwCommand decode_controlword(uint16_t cw, uint16_t previous) {
    if ((cw & 0x80) && !(previous & 0x80)) return CwCommand::FAULT_RESET;
    if (cw & 0x80) return CwCommand::NONE;  // reset bit held high: no new command
    if ((cw & 0x02) == 0x00) return CwCommand::DISABLE_VOLTAGE;
    if ((cw & 0x06) == 0x02) return CwCommand::QUICK_STOP;
    if ((cw & 0x07) == 0x06) return CwCommand::SHUTDOWN;
    if ((cw & 0x0F) == 0x07) return CwCommand::SWITCH_ON;
    if ((cw & 0x0F) == 0x0F) return CwCommand::ENABLE_OPERATION;
    return CwCommand::NONE;
}

uint64_t extract_bits(const Frame& f, unsigned bit_off, unsigned bits, bool& complete) {
    complete = (bit_off + bits) <= static_cast<unsigned>(f.dlc) * 8u;
    uint64_t v = 0;
    for (unsigned b = 0; b < bits && b < 64; ++b) {
        unsigned pos = bit_off + b;
        unsigned byte = pos / 8;
        if (byte >= f.dlc) break;
        if (f.data[byte] & (1u << (pos % 8))) v |= (uint64_t{1} << b);
    }
    return v;
}

std::vector<PdoField> decode_pdo_fields(const Frame& f, const PdoMapping& m) {
    std::vector<PdoField> out;
    unsigned off = 0;
    for (const auto& e : m.entries) {
        PdoField pf;
        pf.index = e.index;
        pf.sub = e.sub;
        pf.bits = e.bits;
        pf.raw = extract_bits(f, off, e.bits, pf.complete);
        out.push_back(pf);
        off += e.bits;
    }
    return out;
}

namespace {

uint32_t le32(const uint8_t* p, size_t n) {
    uint32_t v = 0;
    for (size_t i = 0; i < n && i < 4; ++i) v |= static_cast<uint32_t>(p[i]) << (8 * i);
    return v;
}

// CiA 402 predefined PDO mapping (statusword/controlword always first).
std::vector<PdoMapEntry> cia402_default(bool tx, uint8_t num) {
    if (tx) {
        switch (num) {
            case 1: return {{0x6041, 0, 16}};
            case 2: return {{0x6041, 0, 16}, {0x6061, 0, 8}};
            case 3: return {{0x6041, 0, 16}, {0x6064, 0, 32}};
            default: return {{0x6041, 0, 16}, {0x606C, 0, 32}};
        }
    }
    switch (num) {
        case 1: return {{0x6040, 0, 16}};
        case 2: return {{0x6040, 0, 16}, {0x6060, 0, 8}};
        case 3: return {{0x6040, 0, 16}, {0x607A, 0, 32}};
        default: return {{0x6040, 0, 16}, {0x60FF, 0, 32}};
    }
}

bool is_cia402_object(uint16_t base) {
    switch (base) {
        case 0x603F: case 0x6040: case 0x6041: case 0x6060: case 0x6061: case 0x6064:
        case 0x606C: case 0x6071: case 0x6077: case 0x607A: case 0x6081: case 0x6083:
        case 0x6084: case 0x6098: case 0x60FF: case 0x6502:
            return true;
        default:
            return false;
    }
}

}  // namespace

int drive_evidence(const Frame& f, uint8_t& node) {
    if (f.ext || f.rtr || f.error || f.dlc < 4) return 0;
    bool req = f.id >= 0x601 && f.id <= 0x67F;
    bool resp = f.id >= 0x581 && f.id <= 0x5FF;
    if (!req && !resp) return 0;
    node = static_cast<uint8_t>(f.id & 0x7F);
    uint8_t cs = f.data[0] >> 5;
    bool init = req ? (cs == 1 || cs == 2) : (cs == 2 || cs == 3);
    if (!init) return 0;
    uint16_t index = static_cast<uint16_t>(f.data[1] | (f.data[2] << 8));
    if (resp && cs == 2 && index == 0x1000 && (f.data[0] & 0x02) && f.dlc >= 6)
        return (le32(&f.data[4], 2) & 0xFFFF) == 402 ? 1 : -1;
    // Other profiles (e.g. CiA 401 I/O) also live in 0x6000-0x9FFF, so only
    // objects that are typical for CiA 402 count, on any axis.
    if (f.data[3] == 0 && is_cia402_object(axis_base(index))) return 1;
    // mapping a statusword/controlword into a PDO is just as clear a sign
    bool map_obj = (index >= 0x1600 && index <= 0x1603) || (index >= 0x1A00 && index <= 0x1A03);
    if (req && cs == 1 && map_obj && f.data[3] >= 1 && (f.data[0] & 0x02) && f.dlc >= 8) {
        uint16_t mapped = axis_base(static_cast<uint16_t>(f.data[6] | (f.data[7] << 8)));
        if (mapped == 0x6040 || mapped == 0x6041) return 1;
    }
    return 0;
}

struct Analyzer::NodeState {
    // SDO
    bool sdo_active = false;
    bool sdo_answered = true;
    bool sdo_upload = false;
    uint32_t sdo_row = 0;
    double sdo_t = 0.0;
    uint16_t sdo_index = 0;
    uint8_t sdo_sub = 0;
    bool sdo_expedited = false;
    uint32_t sdo_value = 0;

    // PDO mapping: current version per PDO, plus the list being edited over SDO
    uint32_t tpdo_ref[4] = {UINT32_MAX, UINT32_MAX, UINT32_MAX, UINT32_MAX};
    uint32_t rpdo_ref[4] = {UINT32_MAX, UINT32_MAX, UINT32_MAX, UINT32_MAX};
    std::vector<PdoMapEntry> edit_t[4], edit_r[4];

    // CiA 402, one state machine per axis
    struct Axis {
        AxisState state = AxisState::UNKNOWN;
        uint16_t last_cw = 0;
        bool have_cw = false;
        bool expect_active = false;
        bool expect_fault_cleared = false;  // fault reset: any non-fault state is fine
        AxisState expect_state = AxisState::UNKNOWN;
        double expect_deadline = 0.0;
        double expect_t = 0.0;
        uint32_t expect_row = 0;
    };
    Axis axes[kMaxAxes];
    int max_axis = -1;
    int expecting = 0;   // number of axes with a pending expectation

    // EMCY / NMT
    int64_t last_emcy_row = -1;
    double last_emcy_t = -1e9;
    uint16_t last_emcy_code = 0;
    double last_reset_cmd_t = -1e9;

    // Heartbeat
    bool seen_any_hb = false;
    double last_hb_t = 0.0;
    uint32_t last_hb_row = 0;
    uint8_t last_hb_state = 0;
    std::deque<double> periods;   // recent regular intervals
    bool lost_reported = false;

    bool seen = false;
};

struct Analyzer::Impl {
    const Options& opt;
    Results& out;
    const std::map<uint8_t, bool>& overrides;
    const BaseMappings& base;
    std::vector<bool> drive;
    std::vector<bool> drive_known_negative;
    std::vector<NodeState> st;
    bool timed;
    double last_error_frame_t = -1e9;
    bool error_issue_open = false;

    Impl(const Options& o, Results& r, const std::map<uint8_t, bool>& ov, const BaseMappings& b,
         std::vector<bool> d, bool t)
        : opt(o), out(r), overrides(ov), base(b), drive(std::move(d)), drive_known_negative(128, false),
          st(128), timed(t) {
        if (drive.size() != 128) drive.assign(128, false);
        for (const auto& [key, entries] : base) {
            uint8_t node = static_cast<uint8_t>(key >> 8);
            for (const auto& e : entries)
                if (node < 128 && (axis_base(e.index) == 0x6040 || axis_base(e.index) == 0x6041)) drive[node] = true;
        }
        for (const auto& [node, val] : overrides)
            if (node < 128) drive[node] = val;

        out.issues.clear();
        out.mappings.clear();
        out.node_info.assign(128, NodeInfo{});
        for (int n = 0; n < 128; ++n) {
            out.node_info[n].node = static_cast<uint8_t>(n);
            out.node_info[n].axis_states.fill(AxisState::UNKNOWN);
        }
        out.timelines.assign(128 * kMaxAxes, {});
        for (int n = 1; n < 128; ++n) init_mappings(static_cast<uint8_t>(n), 0);
    }

    uint32_t push_mapping(PdoMapping m) {
        out.mappings.push_back(std::move(m));
        return static_cast<uint32_t>(out.mappings.size() - 1);
    }

    // EDS mapping first, CiA 402 defaults for drives. Only fills PDOs that have none yet.
    void init_mappings(uint8_t n, uint32_t row) {
        for (int tx = 0; tx < 2; ++tx) {
            for (uint8_t num = 1; num <= 4; ++num) {
                uint32_t& ref = (tx ? st[n].tpdo_ref : st[n].rpdo_ref)[num - 1];
                if (ref != UINT32_MAX) continue;
                PdoMapping m;
                m.node = n;
                m.tx = tx != 0;
                m.num = num;
                m.since_row = row;
                auto it = base.find(map_key(n, m.tx, num));
                if (it != base.end()) {
                    m.origin = MapOrigin::EDS;
                    m.entries = it->second;
                } else if (drive[n]) {
                    m.origin = MapOrigin::CIA402_DEFAULT;
                    m.entries = cia402_default(m.tx, num);
                } else {
                    continue;
                }
                ref = push_mapping(std::move(m));
                (tx ? st[n].edit_t : st[n].edit_r)[num - 1] = out.mappings[ref].entries;
            }
        }
    }

    void add_issue(Record* rec, const Issue& is) {
        if (rec) rec->has_issue = true;
        out.issues.push_back(is);
    }

    // ---------------------------------------------------------------- CiA 402
    void check_axis(uint8_t node, uint8_t axis, double t, bool at_end) {
        NodeState& ns = st[node];
        NodeState::Axis& s = ns.axes[axis];
        if (!s.expect_active || !timed) return;
        bool reached = s.expect_fault_cleared ? (s.state != AxisState::FAULT && s.state != AxisState::UNKNOWN)
                                              : (s.state == s.expect_state);
        if (reached) {
            clear_expectation(ns, s);
            return;
        }
        if (t > s.expect_deadline) {
            Issue is;
            is.severity = Severity::ERROR;
            is.type = s.expect_fault_cleared ? IssueType::AXIS_FAULT_RESET_FAILED : IssueType::AXIS_ENABLE_FAILED;
            is.t = s.expect_t;
            is.row = s.expect_row;
            is.node = node;
            is.axis = axis;
            is.code = static_cast<uint32_t>(static_cast<int>(s.state));
            is.value = opt.state_timeout;
            add_issue(nullptr, is);
            clear_expectation(ns, s);
        }
        (void)at_end;
    }

    void clear_expectation(NodeState& ns, NodeState::Axis& s) {
        if (s.expect_active) ns.expecting--;
        s.expect_active = false;
    }

    void set_expectation(NodeState& ns, NodeState::Axis& s, bool fault_cleared, AxisState state, double t, uint32_t row) {
        if (!s.expect_active) ns.expecting++;
        s.expect_active = true;
        s.expect_fault_cleared = fault_cleared;
        s.expect_state = state;
        s.expect_deadline = t + opt.state_timeout;
        s.expect_t = t;
        s.expect_row = row;
    }

    void check_node(uint8_t node, double t, bool at_end) {
        NodeState& ns = st[node];
        if (!ns.expecting) return;
        for (int a = 0; a <= ns.max_axis; ++a) check_axis(node, static_cast<uint8_t>(a), t, at_end);
    }

    void note_axis(uint8_t node, uint8_t axis) {
        NodeState& ns = st[node];
        if (axis > ns.max_axis) ns.max_axis = axis;
        out.node_info[node].axis_count = static_cast<uint8_t>(ns.max_axis + 1);
    }

    void on_statusword(const Frame& f, Record& r, uint32_t row, std::vector<AxisWord>& words, uint8_t node,
                       uint8_t axis, uint16_t sw) {
        NodeState& ns = st[node];
        NodeState::Axis& s = ns.axes[axis];
        note_axis(node, axis);
        AxisState state = decode_statusword(sw);
        if (!r.has_statusword) {
            r.has_statusword = true;
            r.sw_axis = axis;
            r.statusword = sw;
            r.axis_state = state;
        }
        words.push_back(AxisWord{axis, true, sw, state, CwCommand::NONE});
        r.words_count++;
        if (state != s.state) {
            out.timelines[node * kMaxAxes + axis].push_back({f.t, row, state, sw});
            if (state == AxisState::FAULT || state == AxisState::FAULT_REACTION_ACTIVE) {
                bool was_fault = s.state == AxisState::FAULT || s.state == AxisState::FAULT_REACTION_ACTIVE;
                if (!was_fault) {
                    Issue is;
                    is.severity = Severity::ERROR;
                    is.type = IssueType::AXIS_FAULT;
                    is.t = f.t;
                    is.row = row;
                    is.node = node;
                    is.axis = axis;
                    is.code = sw;
                    if (ns.last_emcy_row >= 0 && (!timed || f.t - ns.last_emcy_t < 2.0)) {
                        is.related_row = ns.last_emcy_row;
                        is.related_code = ns.last_emcy_code;
                    }
                    add_issue(&r, is);
                }
            } else if (state == AxisState::QUICK_STOP_ACTIVE) {
                Issue is;
                is.severity = Severity::WARNING;
                is.type = IssueType::AXIS_QUICK_STOP;
                is.t = f.t;
                is.row = row;
                is.node = node;
                is.axis = axis;
                is.code = sw;
                add_issue(&r, is);
            }
            s.state = state;
            out.node_info[node].axis_states[axis] = state;
            if (axis == 0) out.node_info[node].axis_state = state;
        }
        check_axis(node, axis, f.t, false);
    }

    void on_controlword(const Frame& f, Record& r, uint32_t row, std::vector<AxisWord>& words, uint8_t node,
                        uint8_t axis, uint16_t cw) {
        NodeState& ns = st[node];
        NodeState::Axis& s = ns.axes[axis];
        note_axis(node, axis);
        CwCommand cmd = decode_controlword(cw, s.have_cw ? s.last_cw : 0);
        if (!r.has_controlword) {
            r.has_controlword = true;
            r.cw_axis = axis;
            r.controlword = cw;
            r.cw_command = cmd;
        }
        words.push_back(AxisWord{axis, false, cw, AxisState::UNKNOWN, cmd});
        r.words_count++;
        bool changed = !s.have_cw || cw != s.last_cw;
        s.last_cw = cw;
        s.have_cw = true;
        if (!changed || cmd == CwCommand::NONE) return;
        if (cmd == CwCommand::ENABLE_OPERATION && s.state != AxisState::OPERATION_ENABLED) {
            set_expectation(ns, s, false, AxisState::OPERATION_ENABLED, f.t, row);
        } else if (cmd == CwCommand::FAULT_RESET && s.state == AxisState::FAULT) {
            set_expectation(ns, s, true, AxisState::UNKNOWN, f.t, row);
        } else if (s.expect_active && !s.expect_fault_cleared && cmd != CwCommand::ENABLE_OPERATION) {
            clear_expectation(ns, s);  // the master changed its mind before the enable completed
        }
    }

    // --------------------------------------------------------------------- SDO
    void apply_sdo_write(const Frame& f, Record& r, uint32_t row, std::vector<AxisWord>& words, uint8_t node,
                         uint16_t index, uint8_t sub, uint32_t value) {
        NodeState& s = st[node];
        bool rx = index >= 0x1600 && index <= 0x1603;
        bool tx = index >= 0x1A00 && index <= 0x1A03;
        if (rx || tx) {
            uint8_t num = static_cast<uint8_t>((index & 0x3) + 1);
            auto& edit = (tx ? s.edit_t : s.edit_r)[num - 1];
            if (sub == 0) {
                if (value <= 64) edit.resize(value);
            } else if (sub <= 64) {
                if (edit.size() < sub) edit.resize(sub);
                edit[sub - 1] = {static_cast<uint16_t>(value >> 16), static_cast<uint8_t>((value >> 8) & 0xFF),
                                 static_cast<uint8_t>(value & 0xFF)};
            }
            PdoMapping m;
            m.node = node;
            m.tx = tx;
            m.num = num;
            m.origin = MapOrigin::LOG_SDO;
            m.since_row = row;
            m.entries = edit;
            (tx ? s.tpdo_ref : s.rpdo_ref)[num - 1] = push_mapping(std::move(m));
        } else if (axis_base(index) == 0x6040 && sub == 0 && drive[node]) {
            on_controlword(f, r, row, words, node, static_cast<uint8_t>(axis_of(index)), static_cast<uint16_t>(value));
        }
    }

    void sdo_no_response(uint8_t node) {
        NodeState& s = st[node];
        Issue is;
        is.severity = Severity::ERROR;
        is.type = IssueType::SDO_NO_RESPONSE;
        is.t = s.sdo_t;
        is.row = s.sdo_row;
        is.node = node;
        is.index = s.sdo_index;
        is.sub = s.sdo_sub;
        is.code = s.sdo_upload ? 1 : 0;
        is.value = opt.sdo_timeout;
        add_issue(nullptr, is);
        s.sdo_answered = true;  // reported once
    }

    // --------------------------------------------------------------- heartbeat
    double hb_period(const NodeState& s) const {
        if (s.periods.size() < 3) return 0.0;
        std::vector<double> v(s.periods.begin(), s.periods.end());
        std::nth_element(v.begin(), v.begin() + v.size() / 2, v.end());
        return v[v.size() / 2];
    }

    double hb_limit(double period) const { return std::max(period * opt.hb_gap_factor, period + 0.02); }

    void check_hb_lost(uint8_t node, double t) {
        NodeState& s = st[node];
        if (!timed || !s.seen_any_hb || s.lost_reported) return;
        double period = hb_period(s);
        if (period <= 0) return;
        double silent = t - s.last_hb_t;
        if (silent > hb_limit(period) && silent > 3 * period) {
            Issue is;
            is.severity = Severity::ERROR;
            is.type = IssueType::HEARTBEAT_LOST;
            is.t = s.last_hb_t;
            is.row = s.last_hb_row;
            is.node = node;
            is.value = silent;
            is.expected = period;
            add_issue(nullptr, is);
            s.lost_reported = true;
        }
    }
};

Analyzer::Analyzer(const Options& opt, Results& out, const std::map<uint8_t, bool>& overrides,
                   const BaseMappings& base, std::vector<bool> drive, bool timed)
    : impl_(new Impl(opt, out, overrides, base, std::move(drive), timed)) {}

Analyzer::~Analyzer() { delete impl_; }

bool Analyzer::is_drive(uint8_t node) const { return node < 128 && impl_->drive[node]; }

void Analyzer::process(const Frame& f, Record& r, uint32_t row, std::vector<AxisWord>& words) {
    Impl& I = *impl_;
    auto& st = I.st;
    auto& node_info = I.out.node_info;
    const bool timed = I.timed;
    const uint32_t id = f.id;
    now_ = f.t;
    r.words_off = static_cast<uint32_t>(words.size());
    r.words_count = 0;

    if (f.error) {
        r.kind = Kind::ERROR_FRAME;
        if (!I.error_issue_open || !timed || f.t - I.last_error_frame_t > 1.0) {
            Issue is;
            is.severity = Severity::WARNING;
            is.type = IssueType::BUS_ERROR_FRAME;
            is.t = f.t;
            is.row = row;
            is.code = id;
            I.add_issue(&r, is);
            I.error_issue_open = true;
        }
        I.last_error_frame_t = f.t;
        return;
    }
    if (f.ext) {
        r.kind = Kind::UNKNOWN;
        return;
    }

    // live decoding learns about drives on the way
    {
        uint8_t en = 0;
        int ev = I.opt.auto_detect_drives ? drive_evidence(f, en) : 0;
        if (ev != 0 && en > 0 && en < 128 && !I.overrides.count(en)) {
            if (ev > 0 && !I.drive[en] && !I.drive_known_negative[en]) {
                I.drive[en] = true;
                I.init_mappings(en, row);
            } else if (ev < 0) {
                I.drive_known_negative[en] = true;
                I.drive[en] = false;
            }
        }
    }

    uint8_t node = 0;
    if (id == 0x000) {
        r.kind = Kind::NMT;
        if (f.dlc >= 2) {
            r.nmt_cmd = f.data[0];
            r.nmt_target = f.data[1];
            if (r.nmt_cmd == 0x81 || r.nmt_cmd == 0x82) {
                if (r.nmt_target == 0) {
                    for (auto& s : st) s.last_reset_cmd_t = f.t;
                } else if (r.nmt_target < 128) {
                    st[r.nmt_target].last_reset_cmd_t = f.t;
                }
            }
        }
    } else if (id == 0x080) {
        r.kind = Kind::SYNC;
    } else if (id > 0x080 && id <= 0x0FF) {
        r.kind = Kind::EMCY;
        node = static_cast<uint8_t>(id - 0x080);
        if (f.dlc >= 3) {
            r.emcy_code = static_cast<uint16_t>(f.data[0] | (f.data[1] << 8));
            r.error_register = f.data[2];
            Issue is;
            is.t = f.t;
            is.row = row;
            is.node = node;
            is.code = r.emcy_code;
            is.index = r.error_register;
            if (r.emcy_code == 0x0000) {
                is.severity = Severity::INFO;
                is.type = IssueType::EMCY_RESET;
            } else {
                is.severity = Severity::ERROR;
                is.type = IssueType::EMCY;
                node_info[node].emcy_count++;
                st[node].last_emcy_row = row;
                st[node].last_emcy_t = f.t;
                st[node].last_emcy_code = r.emcy_code;
                // link a drive fault reported just before this EMCY
                for (auto it = I.out.issues.rbegin(); it != I.out.issues.rend() && it - I.out.issues.rbegin() < 64; ++it) {
                    if (it->type == IssueType::AXIS_FAULT && it->node == node && it->related_row < 0 &&
                        (!timed || f.t - it->t <= 0.2)) {
                        it->related_row = row;
                        it->related_code = r.emcy_code;
                        break;
                    }
                }
            }
            I.add_issue(&r, is);
        }
    } else if (id == 0x100) {
        r.kind = Kind::TIME;
    } else if (id >= 0x181 && id <= 0x57F && (id & 0x7F) != 0) {
        uint32_t fn = id & 0x780;
        node = static_cast<uint8_t>(id & 0x7F);
        bool tx = (fn == 0x180 || fn == 0x280 || fn == 0x380 || fn == 0x480);
        r.kind = tx ? Kind::TPDO : Kind::RPDO;
        r.pdo_num = static_cast<uint8_t>(tx ? (fn - 0x180) / 0x100 + 1 : (fn - 0x200) / 0x100 + 1);
        if (!f.rtr) {
            uint32_t ref = (tx ? st[node].tpdo_ref : st[node].rpdo_ref)[r.pdo_num - 1];
            r.map_ref = ref;
            if (ref != UINT32_MAX && I.drive[node]) {
                const std::vector<PdoMapEntry> entries = I.out.mappings[ref].entries;
                unsigned off = 0;
                for (const auto& e : entries) {
                    uint16_t b = axis_base(e.index);
                    if (e.sub == 0 && e.bits == 16 && (tx ? b == 0x6041 : b == 0x6040)) {
                        bool complete;
                        uint64_t v = extract_bits(f, off, e.bits, complete);
                        uint8_t axis = static_cast<uint8_t>(axis_of(e.index));
                        if (complete) {
                            if (tx) I.on_statusword(f, r, row, words, node, axis, static_cast<uint16_t>(v));
                            else I.on_controlword(f, r, row, words, node, axis, static_cast<uint16_t>(v));
                        }
                    }
                    off += e.bits;
                }
            }
        }
    } else if ((id >= 0x581 && id <= 0x5FF) || (id >= 0x601 && id <= 0x67F)) {
        bool req = id >= 0x601;
        node = static_cast<uint8_t>(id & 0x7F);
        r.kind = req ? Kind::SDO_REQ : Kind::SDO_RESP;
        auto& s = st[node];
        if (f.dlc < 1) {
            r.sdo_type = SdoType::INVALID;
        } else {
            uint8_t b0 = f.data[0];
            uint8_t cs = b0 >> 5;
            auto read_mux = [&]() {
                if (f.dlc >= 4) {
                    r.index = static_cast<uint16_t>(f.data[1] | (f.data[2] << 8));
                    r.sub = f.data[3];
                    r.sdo_index_known = true;
                }
            };
            auto read_value = [&]() {
                bool e = b0 & 0x02, sz = b0 & 0x01;
                r.sdo_expedited = e;
                if (e) {
                    uint8_t n = sz ? ((b0 >> 2) & 0x3) : 0;
                    r.value_len = static_cast<uint8_t>(4 - n);
                    if (f.dlc >= 4 + r.value_len) r.value = le32(&f.data[4], r.value_len);
                    else r.value_len = 0;
                } else if (sz && f.dlc >= 8) {
                    r.sdo_size = le32(&f.data[4], 4);
                }
            };
            auto from_pending = [&]() {
                if (s.sdo_active) {
                    r.index = s.sdo_index;
                    r.sub = s.sdo_sub;
                    r.sdo_index_known = true;
                }
            };

            if (cs == 4) {  // abort, either direction
                r.sdo_type = SdoType::ABORT;
                read_mux();
                if (f.dlc >= 8) r.abort_code = le32(&f.data[4], 4);
                Issue is;
                is.severity = Severity::ERROR;
                is.type = IssueType::SDO_ABORT;
                is.t = f.t;
                is.row = row;
                is.node = node;
                is.code = r.abort_code;
                is.index = r.index;
                is.sub = r.sub;
                is.related_row = s.sdo_active ? static_cast<int64_t>(s.sdo_row) : -1;
                I.add_issue(&r, is);
                node_info[node].sdo_abort_count++;
                s.sdo_active = false;
                s.sdo_answered = true;
            } else if (req) {
                switch (cs) {
                    case 1:
                    case 2: {
                        if (s.sdo_active && !s.sdo_answered && timed) I.sdo_no_response(node);
                        r.sdo_type = cs == 1 ? SdoType::DOWNLOAD_INIT : SdoType::UPLOAD_INIT;
                        read_mux();
                        if (cs == 1) read_value();
                        s.sdo_active = true;
                        s.sdo_answered = false;
                        s.sdo_upload = cs == 2;
                        s.sdo_row = row;
                        s.sdo_t = f.t;
                        s.sdo_index = r.index;
                        s.sdo_sub = r.sub;
                        s.sdo_expedited = r.sdo_expedited;
                        s.sdo_value = r.value;
                        break;
                    }
                    case 0: r.sdo_type = SdoType::DOWNLOAD_SEGMENT; from_pending(); break;
                    case 3: r.sdo_type = SdoType::UPLOAD_SEGMENT; from_pending(); break;
                    case 5:
                    case 6: r.sdo_type = SdoType::BLOCK; read_mux(); break;
                    default: r.sdo_type = SdoType::INVALID; break;
                }
            } else {
                switch (cs) {
                    case 2:  // upload (read) response
                        r.sdo_type = SdoType::UPLOAD_INIT;
                        read_mux();
                        read_value();
                        s.sdo_answered = true;
                        if (r.sdo_expedited && r.value_len > 0) {
                            if (r.index == 0x1000 && r.sub == 0) {
                                node_info[node].device_type = r.value;
                                node_info[node].device_type_known = true;
                            }
                            if (axis_base(r.index) == 0x6041 && r.sub == 0 && I.drive[node])
                                I.on_statusword(f, r, row, words, node, static_cast<uint8_t>(axis_of(r.index)),
                                                static_cast<uint16_t>(r.value));
                        }
                        break;
                    case 3:  // download (write) response
                        r.sdo_type = SdoType::DOWNLOAD_INIT;
                        read_mux();
                        s.sdo_answered = true;
                        if (s.sdo_active && !s.sdo_upload && s.sdo_expedited && s.sdo_index == r.index &&
                            s.sdo_sub == r.sub)
                            I.apply_sdo_write(f, r, row, words, node, r.index, r.sub, s.sdo_value);
                        break;
                    case 0: r.sdo_type = SdoType::UPLOAD_SEGMENT; from_pending(); s.sdo_answered = true; break;
                    case 1: r.sdo_type = SdoType::DOWNLOAD_SEGMENT; from_pending(); s.sdo_answered = true; break;
                    case 5:
                    case 6: r.sdo_type = SdoType::BLOCK; read_mux(); s.sdo_answered = true; break;
                    default: r.sdo_type = SdoType::INVALID; break;
                }
            }
        }
    } else if (id >= 0x701 && id <= 0x77F) {
        r.kind = Kind::HEARTBEAT;
        node = static_cast<uint8_t>(id - 0x700);
        if (!f.rtr && f.dlc >= 1) {
            auto& s = st[node];
            r.hb_state = f.data[0] & 0x7F;
            if (s.seen_any_hb && timed) {
                double gap = f.t - s.last_hb_t;
                bool regular = s.last_hb_state != 0x00 && r.hb_state != 0x00;  // boot-up is not periodic
                if (regular) {
                    double period = I.hb_period(s);
                    if (period > 0 && gap > I.hb_limit(period)) {
                        Issue is;
                        is.severity = Severity::WARNING;
                        is.type = IssueType::HEARTBEAT_GAP;
                        is.t = s.last_hb_t;
                        is.row = s.last_hb_row;
                        is.node = node;
                        is.value = gap;
                        is.expected = period;
                        is.code = r.hb_state;
                        I.add_issue(nullptr, is);
                    } else {
                        s.periods.push_back(gap);
                        if (s.periods.size() > 15) s.periods.pop_front();
                    }
                }
            }
            if (r.hb_state == 0x00 && s.seen_any_hb) {
                Issue is;
                bool expected = timed && f.t - s.last_reset_cmd_t < 5.0;
                is.severity = expected ? Severity::INFO : Severity::WARNING;
                is.type = IssueType::NODE_REBOOT;
                is.t = f.t;
                is.row = row;
                is.node = node;
                is.code = expected ? 1 : 0;
                I.add_issue(&r, is);
                node_info[node].reboot_count++;
            }
            s.seen_any_hb = true;
            s.last_hb_t = f.t;
            s.last_hb_row = row;
            s.last_hb_state = r.hb_state;
            s.lost_reported = false;
            node_info[node].last_hb_state = r.hb_state;
            node_info[node].hb_count++;
            node_info[node].hb_period = I.hb_period(s);
        }
    } else if (id == 0x7E4 || id == 0x7E5) {
        r.kind = Kind::LSS;
    } else {
        r.kind = Kind::UNKNOWN;
    }

    r.node = node;
    if (node > 0 && node < 128) {
        NodeInfo& ni = node_info[node];
        auto& s = st[node];
        if (!s.seen) {
            s.seen = true;
            ni.first_seen = f.t;
        }
        ni.last_seen = f.t;
        ni.frame_count++;
        ni.kind_counts[static_cast<size_t>(r.kind)]++;
        I.check_node(node, f.t, false);
    }
}

void Analyzer::tick(double t) {
    Impl& I = *impl_;
    if (!I.timed) return;
    now_ = std::max(now_, t);
    for (int n = 1; n < 128; ++n) {
        auto& s = I.st[n];
        if (s.sdo_active && !s.sdo_answered && t - s.sdo_t > I.opt.sdo_timeout) I.sdo_no_response(static_cast<uint8_t>(n));
        I.check_node(static_cast<uint8_t>(n), t, false);
        I.check_hb_lost(static_cast<uint8_t>(n), t);
    }
}

void Analyzer::finish(double end_t) {
    Impl& I = *impl_;
    for (int n = 1; n < 128; ++n) {
        auto& s = I.st[n];
        if (I.timed && s.sdo_active && !s.sdo_answered && end_t - s.sdo_t > I.opt.sdo_timeout)
            I.sdo_no_response(static_cast<uint8_t>(n));
        I.check_node(static_cast<uint8_t>(n), end_t, true);
        I.check_hb_lost(static_cast<uint8_t>(n), end_t);
    }
    update_node_info();
}

void Analyzer::update_node_info() {
    Impl& I = *impl_;
    for (int n = 1; n < 128; ++n) {
        NodeInfo& ni = I.out.node_info[n];
        ni.is_drive = I.drive[n];
        ni.drive_forced = I.overrides.count(static_cast<uint8_t>(n)) > 0;
        if (I.drive[n] && ni.axis_count == 0) ni.axis_count = 1;
        if (!I.drive[n]) ni.axis_count = 0;
    }
}

}  // namespace col

#include "trace.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

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

namespace {

uint32_t le32(const uint8_t* p, size_t n) {
    uint32_t v = 0;
    for (size_t i = 0; i < n && i < 4; ++i) v |= static_cast<uint32_t>(p[i]) << (8 * i);
    return v;
}

uint32_t map_key(uint8_t node, bool tx, uint8_t num) {
    return (static_cast<uint32_t>(node) << 8) | (tx ? 0x10u : 0u) | num;
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

bool find_field(const std::vector<PdoMapEntry>& entries, uint16_t index, unsigned& off, unsigned& bits) {
    unsigned o = 0;
    for (const auto& e : entries) {
        if (e.index == index && e.sub == 0) {
            off = o;
            bits = e.bits;
            return true;
        }
        o += e.bits;
    }
    return false;
}

}  // namespace

struct Trace::NodeState {
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

    // CiA 402
    AxisState state = AxisState::UNKNOWN;
    uint16_t last_cw = 0;
    bool have_cw = false;
    CwCommand last_cmd = CwCommand::NONE;
    bool expect_active = false;
    bool expect_fault_cleared = false;  // fault reset: any non-fault state is fine
    AxisState expect_state = AxisState::UNKNOWN;
    double expect_deadline = 0.0;
    uint32_t expect_row = 0;
    CwCommand expect_cmd = CwCommand::NONE;

    // EMCY / NMT / heartbeat
    int64_t last_emcy_row = -1;
    double last_emcy_t = -1e9;
    double last_reset_cmd_t = -1e9;
    std::vector<std::pair<double, uint32_t>> hb;
    bool seen_any_hb = false;
};

Trace Trace::from_text(const std::string& text, const Options& opt) {
    Trace tr;
    tr.opt_ = opt;
    tr.parsed_ = parse_candump_text(text);
    tr.analyze();
    return tr;
}

Trace Trace::from_file(const std::string& path, const Options& opt) {
    Trace tr;
    tr.opt_ = opt;
    tr.parsed_ = parse_candump_file(path);
    tr.analyze();
    return tr;
}

void Trace::set_drive(uint8_t node, bool is_drive) { drive_override_[node] = is_drive; }
void Trace::clear_drive_override(uint8_t node) { drive_override_.erase(node); }

void Trace::set_base_mapping(uint8_t node, bool tx, uint8_t num, const std::vector<PdoMapEntry>& entries) {
    if (num < 1 || num > 4) return;
    base_mappings_[map_key(node, tx, num)] = entries;
}

void Trace::clear_base_mappings() { base_mappings_.clear(); }

uint32_t Trace::push_mapping(PdoMapping m) {
    mappings_.push_back(std::move(m));
    return static_cast<uint32_t>(mappings_.size() - 1);
}

void Trace::detect_drives(std::vector<bool>& drive) const {
    drive.assign(128, false);
    if (opt_.auto_detect_drives) {
        for (const auto& f : parsed_.frames) {
            if (f.ext || f.rtr || f.error || f.dlc < 4) continue;
            bool req = f.id >= 0x601 && f.id <= 0x67F;
            bool resp = f.id >= 0x581 && f.id <= 0x5FF;
            if (!req && !resp) continue;
            uint8_t node = static_cast<uint8_t>(f.id & 0x7F);
            uint8_t cs = f.data[0] >> 5;
            bool init = req ? (cs == 1 || cs == 2) : (cs == 2 || cs == 3);
            if (!init) continue;
            uint16_t index = static_cast<uint16_t>(f.data[1] | (f.data[2] << 8));
            if (index >= 0x6000 && index <= 0x67FF) drive[node] = true;
            // mapping the statusword/controlword into a PDO is just as clear a sign
            bool map_obj = (index >= 0x1600 && index <= 0x1603) || (index >= 0x1A00 && index <= 0x1A03);
            if (req && cs == 1 && map_obj && f.data[3] >= 1 && (f.data[0] & 0x02) && f.dlc >= 8) {
                uint16_t mapped = static_cast<uint16_t>(f.data[6] | (f.data[7] << 8));
                if (mapped == 0x6040 || mapped == 0x6041) drive[node] = true;
            }
            if (resp && cs == 2 && index == 0x1000 && (f.data[0] & 0x02) && f.dlc >= 6) {
                if ((le32(&f.data[4], 2) & 0xFFFF) == 402) drive[node] = true;
            }
        }
    }
    for (const auto& [key, entries] : base_mappings_) {
        uint8_t node = static_cast<uint8_t>(key >> 8);
        for (const auto& e : entries)
            if (node < 128 && (e.index == 0x6040 || e.index == 0x6041)) drive[node] = true;
    }
    for (const auto& [node, val] : drive_override_)
        if (node < 128) drive[node] = val;
}

void Trace::analyze() {
    const auto& frames = parsed_.frames;
    records_.assign(frames.size(), Record{});
    issues_.clear();
    mappings_.clear();
    node_info_.assign(128, NodeInfo{});
    for (int n = 0; n < 128; ++n) node_info_[n].node = static_cast<uint8_t>(n);
    timelines_.assign(128, {});

    std::vector<bool> drive;
    detect_drives(drive);
    std::vector<NodeState> st(128);
    std::vector<bool> node_seen(128, false);
    const bool timed = parsed_.has_timestamps;

    auto add_issue = [&](Issue is) {
        if (is.row < records_.size()) records_[is.row].has_issue = true;
        issues_.push_back(is);
    };

    // Initial mappings: EDS first, CiA 402 defaults for drives.
    for (int n = 1; n < 128; ++n) {
        for (int tx = 0; tx < 2; ++tx) {
            for (uint8_t num = 1; num <= 4; ++num) {
                PdoMapping m;
                m.node = static_cast<uint8_t>(n);
                m.tx = tx != 0;
                m.num = num;
                auto it = base_mappings_.find(map_key(m.node, m.tx, num));
                if (it != base_mappings_.end()) {
                    m.origin = MapOrigin::EDS;
                    m.entries = it->second;
                } else if (drive[n]) {
                    m.origin = MapOrigin::CIA402_DEFAULT;
                    m.entries = cia402_default(m.tx, num);
                } else {
                    continue;
                }
                uint32_t ref = push_mapping(std::move(m));
                (tx ? st[n].tpdo_ref : st[n].rpdo_ref)[num - 1] = ref;
                (tx ? st[n].edit_t : st[n].edit_r)[num - 1] = mappings_[ref].entries;
            }
        }
    }

    auto check_expectation = [&](uint8_t node, double t, bool at_end) {
        NodeState& s = st[node];
        if (!s.expect_active || !timed) return;
        bool reached = s.expect_fault_cleared ? (s.state != AxisState::FAULT && s.state != AxisState::UNKNOWN)
                                              : (s.state == s.expect_state);
        if (reached) {
            s.expect_active = false;
            return;
        }
        if (t > s.expect_deadline || at_end) {
            if (at_end && t <= s.expect_deadline) return;  // log ended too early to tell
            Issue is;
            is.severity = Severity::ERROR;
            is.type = s.expect_fault_cleared ? IssueType::AXIS_FAULT_RESET_FAILED : IssueType::AXIS_ENABLE_FAILED;
            is.t = frames[s.expect_row].t;
            is.row = s.expect_row;
            is.node = node;
            is.code = static_cast<uint32_t>(static_cast<int>(s.state));
            is.value = opt_.state_timeout;
            add_issue(is);
            s.expect_active = false;
        }
    };

    auto on_statusword = [&](uint8_t node, uint32_t row, uint16_t sw) {
        Record& r = records_[row];
        NodeState& s = st[node];
        r.has_statusword = true;
        r.statusword = sw;
        r.axis_state = decode_statusword(sw);
        if (r.axis_state != s.state) {
            timelines_[node].push_back({frames[row].t, row, r.axis_state, sw});
            if (r.axis_state == AxisState::FAULT || r.axis_state == AxisState::FAULT_REACTION_ACTIVE) {
                bool was_fault = s.state == AxisState::FAULT || s.state == AxisState::FAULT_REACTION_ACTIVE;
                if (!was_fault) {
                    Issue is;
                    is.severity = Severity::ERROR;
                    is.type = IssueType::AXIS_FAULT;
                    is.t = frames[row].t;
                    is.row = row;
                    is.node = node;
                    is.code = sw;
                    if (s.last_emcy_row >= 0 && (!timed || frames[row].t - s.last_emcy_t < 2.0))
                        is.related_row = s.last_emcy_row;
                    add_issue(is);
                }
            } else if (r.axis_state == AxisState::QUICK_STOP_ACTIVE) {
                Issue is;
                is.severity = Severity::WARNING;
                is.type = IssueType::AXIS_QUICK_STOP;
                is.t = frames[row].t;
                is.row = row;
                is.node = node;
                is.code = sw;
                add_issue(is);
            }
            s.state = r.axis_state;
            node_info_[node].axis_state = s.state;
        }
        check_expectation(node, frames[row].t, false);
    };

    auto on_controlword = [&](uint8_t node, uint32_t row, uint16_t cw) {
        Record& r = records_[row];
        NodeState& s = st[node];
        r.has_controlword = true;
        r.controlword = cw;
        r.cw_command = decode_controlword(cw, s.have_cw ? s.last_cw : 0);
        bool changed = !s.have_cw || cw != s.last_cw;
        s.last_cw = cw;
        s.have_cw = true;
        if (!changed || r.cw_command == CwCommand::NONE) return;
        s.last_cmd = r.cw_command;
        if (r.cw_command == CwCommand::ENABLE_OPERATION && s.state != AxisState::OPERATION_ENABLED) {
            s.expect_active = true;
            s.expect_fault_cleared = false;
            s.expect_state = AxisState::OPERATION_ENABLED;
            s.expect_deadline = frames[row].t + opt_.state_timeout;
            s.expect_row = row;
        } else if (r.cw_command == CwCommand::FAULT_RESET && s.state == AxisState::FAULT) {
            s.expect_active = true;
            s.expect_fault_cleared = true;
            s.expect_deadline = frames[row].t + opt_.state_timeout;
            s.expect_row = row;
        } else if (s.expect_active && !s.expect_fault_cleared && r.cw_command != CwCommand::ENABLE_OPERATION) {
            s.expect_active = false;  // the master changed its mind before the enable completed
        }
    };

    // Applies a confirmed SDO write (mapping changes, controlword over SDO).
    auto apply_sdo_write = [&](uint8_t node, uint32_t row, uint16_t index, uint8_t sub, uint32_t value) {
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
            uint32_t ref = push_mapping(std::move(m));
            (tx ? s.tpdo_ref : s.rpdo_ref)[num - 1] = ref;
        } else if (index == 0x6040 && sub == 0 && drive[node]) {
            on_controlword(node, row, static_cast<uint16_t>(value));
        }
    };

    auto sdo_no_response = [&](uint8_t node) {
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
        is.value = opt_.sdo_timeout;
        add_issue(is);
    };

    double last_error_frame_t = -1e9;
    bool error_issue_open = false;

    for (uint32_t i = 0; i < frames.size(); ++i) {
        const Frame& f = frames[i];
        Record& r = records_[i];
        const uint32_t id = f.id;

        if (f.error) {
            r.kind = Kind::ERROR_FRAME;
            if (!error_issue_open || !timed || f.t - last_error_frame_t > 1.0) {
                Issue is;
                is.severity = Severity::WARNING;
                is.type = IssueType::BUS_ERROR_FRAME;
                is.t = f.t;
                is.row = i;
                is.code = id;
                add_issue(is);
                error_issue_open = true;
            }
            last_error_frame_t = f.t;
            continue;
        }
        if (f.ext) {
            r.kind = Kind::UNKNOWN;
            continue;
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
                is.row = i;
                is.node = node;
                is.code = r.emcy_code;
                is.index = r.error_register;
                if (r.emcy_code == 0x0000) {
                    is.severity = Severity::INFO;
                    is.type = IssueType::EMCY_RESET;
                } else {
                    is.severity = Severity::ERROR;
                    is.type = IssueType::EMCY;
                    node_info_[node].emcy_count++;
                    st[node].last_emcy_row = i;
                    st[node].last_emcy_t = f.t;
                }
                add_issue(is);
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
                if (ref != UINT32_MAX && drive[node]) {
                    unsigned off, bits;
                    bool complete;
                    if (tx && find_field(mappings_[ref].entries, 0x6041, off, bits) && bits == 16) {
                        uint64_t v = extract_bits(f, off, bits, complete);
                        if (complete) on_statusword(node, i, static_cast<uint16_t>(v));
                    }
                    if (!tx && find_field(mappings_[ref].entries, 0x6040, off, bits) && bits == 16) {
                        uint64_t v = extract_bits(f, off, bits, complete);
                        if (complete) on_controlword(node, i, static_cast<uint16_t>(v));
                    }
                }
            }
        } else if ((id >= 0x581 && id <= 0x5FF) || (id >= 0x601 && id <= 0x67F)) {
            bool req = id >= 0x601;
            node = static_cast<uint8_t>(id & 0x7F);
            r.kind = req ? Kind::SDO_REQ : Kind::SDO_RESP;
            NodeState& s = st[node];
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
                    is.row = i;
                    is.node = node;
                    is.code = r.abort_code;
                    is.index = r.index;
                    is.sub = r.sub;
                    is.related_row = s.sdo_active ? static_cast<int64_t>(s.sdo_row) : -1;
                    add_issue(is);
                    node_info_[node].sdo_abort_count++;
                    s.sdo_active = false;
                    s.sdo_answered = true;
                } else if (req) {
                    switch (cs) {
                        case 1:
                        case 2: {
                            if (s.sdo_active && !s.sdo_answered && timed) sdo_no_response(node);
                            r.sdo_type = cs == 1 ? SdoType::DOWNLOAD_INIT : SdoType::UPLOAD_INIT;
                            read_mux();
                            if (cs == 1) read_value();
                            s.sdo_active = true;
                            s.sdo_answered = false;
                            s.sdo_upload = cs == 2;
                            s.sdo_row = i;
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
                                    node_info_[node].device_type = r.value;
                                    node_info_[node].device_type_known = true;
                                }
                                if (r.index == 0x6041 && r.sub == 0 && drive[node])
                                    on_statusword(node, i, static_cast<uint16_t>(r.value));
                            }
                            break;
                        case 3:  // download (write) response
                            r.sdo_type = SdoType::DOWNLOAD_INIT;
                            read_mux();
                            s.sdo_answered = true;
                            if (s.sdo_active && !s.sdo_upload && s.sdo_expedited && s.sdo_index == r.index &&
                                s.sdo_sub == r.sub)
                                apply_sdo_write(node, i, r.index, r.sub, s.sdo_value);
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
                NodeState& s = st[node];
                r.hb_state = f.data[0] & 0x7F;
                if (r.hb_state == 0x00 && s.seen_any_hb) {
                    Issue is;
                    bool expected = timed && f.t - s.last_reset_cmd_t < 5.0;
                    is.severity = expected ? Severity::INFO : Severity::WARNING;
                    is.type = IssueType::NODE_REBOOT;
                    is.t = f.t;
                    is.row = i;
                    is.node = node;
                    is.code = expected ? 1 : 0;
                    add_issue(is);
                    node_info_[node].reboot_count++;
                }
                s.seen_any_hb = true;
                s.hb.emplace_back(f.t, i);
                node_info_[node].last_hb_state = r.hb_state;
                node_info_[node].hb_count++;
            }
        } else if (id == 0x7E4 || id == 0x7E5) {
            r.kind = Kind::LSS;
        } else {
            r.kind = Kind::UNKNOWN;
        }

        r.node = node;
        if (node > 0 && node < 128) {
            NodeInfo& ni = node_info_[node];
            if (!node_seen[node]) {
                node_seen[node] = true;
                ni.first_seen = f.t;
            }
            ni.last_seen = f.t;
            ni.frame_count++;
            ni.kind_counts[static_cast<size_t>(r.kind)]++;
            check_expectation(node, f.t, false);
        }
    }

    // ---- end-of-log checks --------------------------------------------
    const double end_t = duration();
    for (int n = 1; n < 128; ++n) {
        NodeState& s = st[n];
        if (timed && s.sdo_active && !s.sdo_answered && end_t - s.sdo_t > opt_.sdo_timeout) sdo_no_response(static_cast<uint8_t>(n));
        check_expectation(static_cast<uint8_t>(n), end_t, true);

        if (!timed || s.hb.size() < 4) continue;
        std::vector<double> gaps, periodic;
        for (size_t k = 1; k < s.hb.size(); ++k) {
            gaps.push_back(s.hb[k].first - s.hb[k - 1].first);
            if (records_[s.hb[k - 1].second].hb_state != 0x00 && records_[s.hb[k].second].hb_state != 0x00)
                periodic.push_back(gaps.back());
        }
        if (periodic.size() < 3) continue;
        std::vector<double> sorted = periodic;
        std::nth_element(sorted.begin(), sorted.begin() + sorted.size() / 2, sorted.end());
        double period = sorted[sorted.size() / 2];
        if (period <= 0) continue;
        node_info_[n].hb_period = period;
        double limit = std::max(period * opt_.hb_gap_factor, period + 0.02);
        for (size_t k = 0; k < gaps.size(); ++k) {
            if (gaps[k] > limit) {
                // boot-up is not periodic, and a boot-up after the gap is reported as a reboot
                const Record& prev = records_[s.hb[k].second];
                const Record& next = records_[s.hb[k + 1].second];
                if (prev.hb_state == 0x00 || next.hb_state == 0x00) continue;
                Issue is;
                is.severity = Severity::WARNING;
                is.type = IssueType::HEARTBEAT_GAP;
                is.t = s.hb[k].first;
                is.row = s.hb[k].second;
                is.node = static_cast<uint8_t>(n);
                is.value = gaps[k];
                is.expected = period;
                is.code = next.hb_state;
                add_issue(is);
            }
        }
        double silent = end_t - s.hb.back().first;
        if (silent > limit && silent > 3 * period) {
            Issue is;
            is.severity = Severity::ERROR;
            is.type = IssueType::HEARTBEAT_LOST;
            is.t = s.hb.back().first;
            is.row = s.hb.back().second;
            is.node = static_cast<uint8_t>(n);
            is.value = silent;
            is.expected = period;
            add_issue(is);
        }
    }

    for (auto& is : issues_) {
        if (is.type != IssueType::AXIS_FAULT || is.related_row >= 0) continue;
        for (uint32_t k = is.row + 1; k < records_.size(); ++k) {
            if (timed && frames[k].t - frames[is.row].t > 0.2) break;
            if (!timed && k - is.row > 50) break;
            const Record& rk = records_[k];
            if (rk.kind == Kind::EMCY && rk.node == is.node && rk.emcy_code != 0) {
                is.related_row = k;
                break;
            }
        }
    }

    for (int n = 1; n < 128; ++n) node_info_[n].is_drive = drive[n];
    for (const auto& [node, val] : drive_override_)
        if (node < 128) node_info_[node].drive_forced = true;

    if (parsed_.skipped_lines > 0) {
        Issue is;
        is.severity = Severity::WARNING;
        is.type = IssueType::PARSE_ERRORS;
        is.code = parsed_.skipped_lines;
        is.value = parsed_.first_skipped_line;
        issues_.insert(issues_.begin(), is);
    }

    std::stable_sort(issues_.begin(), issues_.end(), [](const Issue& a, const Issue& b) {
        if (a.type == IssueType::PARSE_ERRORS) return b.type != IssueType::PARSE_ERRORS;
        if (b.type == IssueType::PARSE_ERRORS) return false;
        return a.row < b.row;
    });
}

std::vector<NodeInfo> Trace::nodes() const {
    std::vector<NodeInfo> out;
    for (const auto& ni : node_info_)
        if (ni.node > 0 && (ni.frame_count > 0 || ni.drive_forced)) out.push_back(ni);
    return out;
}

const std::vector<StatePoint>& Trace::axis_timeline(uint8_t node) const {
    static const std::vector<StatePoint> empty;
    if (node >= timelines_.size()) return empty;
    return timelines_[node];
}

std::vector<PdoField> Trace::pdo_fields(size_t row) const {
    std::vector<PdoField> out;
    const Record& r = records_.at(row);
    if (r.map_ref == UINT32_MAX) return out;
    const Frame& f = parsed_.frames.at(row);
    unsigned off = 0;
    for (const auto& e : mappings_[r.map_ref].entries) {
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

std::vector<uint32_t> Trace::kind_counts() const {
    std::vector<uint32_t> c(static_cast<size_t>(Kind::COUNT_), 0);
    for (const auto& r : records_) c[static_cast<size_t>(r.kind)]++;
    return c;
}

std::vector<uint32_t> Trace::filter(uint32_t kind_mask, int node, bool issues_only, int index) const {
    std::vector<uint32_t> out;
    out.reserve(records_.size());
    for (uint32_t i = 0; i < records_.size(); ++i) {
        const Record& r = records_[i];
        if (!(kind_mask & (1u << static_cast<unsigned>(r.kind)))) continue;
        if (node >= 0 && r.node != node) continue;
        if (issues_only && !r.has_issue) continue;
        if (index >= 0) {
            bool hit = r.sdo_index_known && r.index == index;
            if (!hit && r.map_ref != UINT32_MAX) {
                for (const auto& e : mappings_[r.map_ref].entries)
                    if (e.index == index) { hit = true; break; }
            }
            if (!hit) continue;
        }
        out.push_back(i);
    }
    return out;
}

}  // namespace col

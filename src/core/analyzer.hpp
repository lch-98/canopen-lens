// Frame-by-frame CANopen analysis shared by offline logs (Trace) and live
// decoding (LiveDecoder). The analyzer only ever looks at the current frame;
// everything it needs from the past is kept in its own per-node state.
#pragma once

#include <map>
#include <vector>

#include "types.hpp"

namespace col {

struct Options {
    double sdo_timeout = 1.0;       // s without an SDO answer before it counts as lost
    double state_timeout = 1.0;     // s a CiA 402 command may take to take effect
    double hb_gap_factor = 2.5;     // gap > factor * normal period => warning
    bool auto_detect_drives = true; // treat nodes as CiA 402 when the log shows it
};

using BaseMappings = std::map<uint32_t, std::vector<PdoMapEntry>>;  // key: node<<8 | tx<<4 | num

inline uint32_t map_key(uint8_t node, bool tx, uint8_t num) {
    return (static_cast<uint32_t>(node) << 8) | (tx ? 0x10u : 0u) | num;
}

// Evidence a single frame gives about a node being a CiA 402 drive:
// +1 = yes, -1 = no (device type of another profile), 0 = nothing.
int drive_evidence(const Frame& f, uint8_t& node);

AxisState decode_statusword(uint16_t sw);
CwCommand decode_controlword(uint16_t cw, uint16_t previous);
uint64_t extract_bits(const Frame& f, unsigned bit_off, unsigned bits, bool& complete);

std::vector<PdoField> decode_pdo_fields(const Frame& f, const PdoMapping& m);

// Everything the analysis produces besides the per-frame Record.
struct Results {
    std::vector<Issue> issues;
    std::vector<NodeInfo> node_info;                  // indexed by node-ID (0..127)
    std::vector<std::vector<StatePoint>> timelines;   // node * kMaxAxes + axis
    std::vector<PdoMapping> mappings;
};

class Analyzer {
public:
    // `drive` holds the initial drive decision per node (from a pre-scan of a
    // whole log, or empty for live decoding); overrides always win.
    Analyzer(const Options& opt, Results& out, const std::map<uint8_t, bool>& overrides,
             const BaseMappings& base, std::vector<bool> drive, bool timed);
    ~Analyzer();
    Analyzer(const Analyzer&) = delete;
    Analyzer& operator=(const Analyzer&) = delete;

    // Decodes one frame into `rec`; statuswords/controlwords are appended to `words`.
    void process(const Frame& f, Record& rec, uint32_t row, std::vector<AxisWord>& words);

    // Live use: time-based checks (SDO timeouts, commands that did not take
    // effect, heartbeats that stopped) without waiting for the next frame.
    void tick(double t);

    // End of a log: reports what is still pending.
    void finish(double end_t);

    // Copies drive flags / axis counts into Results::node_info (finish() does this too).
    void update_node_info();

    bool is_drive(uint8_t node) const;
    double now() const { return now_; }

private:
    struct NodeState;
    struct Impl;
    Impl* impl_;
    double now_ = 0.0;
};

}  // namespace col

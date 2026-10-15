// A loaded log: raw frames plus everything derived from them.
#pragma once

#include <map>
#include <string>
#include <vector>

#include "parser.hpp"
#include "types.hpp"

namespace col {

struct Options {
    double sdo_timeout = 1.0;       // s without an SDO answer before it counts as lost
    double state_timeout = 1.0;     // s a CiA 402 command may take to take effect
    double hb_gap_factor = 2.5;     // gap > factor * normal period => warning
    bool auto_detect_drives = true; // treat nodes as CiA 402 when the log shows it
};

class Trace {
public:
    static Trace from_text(const std::string& text, const Options& opt = {});
    static Trace from_file(const std::string& path, const Options& opt = {});

    // Re-runs decoding and diagnostics, e.g. after mappings were supplied by an EDS.
    void analyze();

    // Overrides automatic CiA 402 detection for one node.
    void set_drive(uint8_t node, bool is_drive);
    void clear_drive_override(uint8_t node);

    // PDO mapping known from outside the log (EDS / DCF). Used until the log
    // itself reconfigures the mapping over SDO.
    void set_base_mapping(uint8_t node, bool tx, uint8_t num, const std::vector<PdoMapEntry>& entries);
    void clear_base_mappings();

    Options& options() { return opt_; }

    // --- results -------------------------------------------------------
    size_t size() const { return parsed_.frames.size(); }
    const Frame& frame(size_t i) const { return parsed_.frames.at(i); }
    const Record& record(size_t i) const { return records_.at(i); }
    const std::vector<Issue>& issues() const { return issues_; }
    std::vector<NodeInfo> nodes() const;
    const std::vector<StatePoint>& axis_timeline(uint8_t node) const;
    const PdoMapping& mapping(uint32_t ref) const { return mappings_.at(ref); }
    size_t mapping_count() const { return mappings_.size(); }
    std::vector<PdoField> pdo_fields(size_t row) const;
    const std::vector<std::string>& interfaces() const { return parsed_.interfaces; }
    double duration() const { return parsed_.frames.empty() ? 0.0 : parsed_.frames.back().t; }
    double t0() const { return parsed_.t0; }
    bool has_timestamps() const { return parsed_.has_timestamps; }
    uint32_t skipped_lines() const { return parsed_.skipped_lines; }
    const std::string& format() const { return parsed_.format; }
    std::vector<uint32_t> kind_counts() const;

    // Row indices matching all given criteria. kind_mask is a bit set over Kind,
    // node < 0 means any node, index < 0 means any object index.
    std::vector<uint32_t> filter(uint32_t kind_mask, int node, bool issues_only, int index) const;

private:
    struct NodeState;
    void detect_drives(std::vector<bool>& drive) const;
    uint32_t push_mapping(PdoMapping m);

    Options opt_;
    ParseResult parsed_;
    std::vector<Record> records_;
    std::vector<Issue> issues_;
    std::vector<NodeInfo> node_info_;          // indexed by node-ID (0..127)
    std::vector<std::vector<StatePoint>> timelines_;
    std::vector<PdoMapping> mappings_;
    std::map<uint8_t, bool> drive_override_;
    std::map<uint32_t, std::vector<PdoMapEntry>> base_mappings_;  // key: node<<8 | tx<<4 | num
};

AxisState decode_statusword(uint16_t sw);
CwCommand decode_controlword(uint16_t cw, uint16_t previous);

}  // namespace col

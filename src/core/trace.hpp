// A loaded log (Trace) and a live decoder fed one frame at a time (LiveDecoder).
#pragma once

#include <map>
#include <memory>
#include <string>
#include <vector>

#include "analyzer.hpp"
#include "parser.hpp"
#include "types.hpp"

namespace col {

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
    const std::vector<Issue>& issues() const { return res_.issues; }
    std::vector<NodeInfo> nodes() const;
    const std::vector<StatePoint>& axis_timeline(uint8_t node, uint8_t axis = 0) const;
    std::vector<AxisWord> axis_words(size_t row) const;
    uint8_t axis_count(uint8_t node) const { return node < res_.node_info.size() ? res_.node_info[node].axis_count : 0; }
    const PdoMapping& mapping(uint32_t ref) const { return res_.mappings.at(ref); }
    size_t mapping_count() const { return res_.mappings.size(); }
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
    Options opt_;
    ParseResult parsed_;
    std::vector<Record> records_;
    std::vector<AxisWord> words_;
    Results res_;
    std::map<uint8_t, bool> drive_override_;
    BaseMappings base_mappings_;
};

// Decodes frames as they arrive from a live bus. Only the newest frame is kept,
// so memory stays constant however long it runs; findings accumulate in issues().
class LiveDecoder {
public:
    explicit LiveDecoder(const Options& opt = {});

    void set_drive(uint8_t node, bool is_drive);
    void set_base_mapping(uint8_t node, bool tx, uint8_t num, const std::vector<PdoMapEntry>& entries);
    // Forgets all state (keeps drive overrides and base mappings).
    void reset();

    // `t` is an absolute time in seconds (e.g. python-can's msg.timestamp).
    // Returns the number of findings added by this frame (and the time-based
    // checks it triggered); they are the last entries of issues().
    size_t feed(double t, uint32_t id, const uint8_t* data, size_t len, bool ext, bool rtr, bool error, bool fd);
    // Time-based checks while the bus is silent. Returns the number of new findings.
    size_t tick(double t);

    const Frame& last_frame() const { return frame_; }
    const Record& last_record() const { return record_; }
    const std::vector<AxisWord>& last_words() const { return words_; }
    std::vector<PdoField> last_pdo_fields() const;
    uint64_t frame_count() const { return count_; }

    const std::vector<Issue>& issues() const { return res_.issues; }
    std::vector<NodeInfo> nodes();
    const std::vector<StatePoint>& axis_timeline(uint8_t node, uint8_t axis = 0) const;
    uint8_t axis_count(uint8_t node) const { return node < res_.node_info.size() ? res_.node_info[node].axis_count : 0; }
    const PdoMapping& mapping(uint32_t ref) const { return res_.mappings.at(ref); }
    double t0() const { return t0_; }
    Options& options() { return opt_; }

private:
    Options opt_;
    std::map<uint8_t, bool> drive_override_;
    BaseMappings base_mappings_;
    Results res_;
    std::unique_ptr<Analyzer> analyzer_;
    Frame frame_;
    Record record_;
    std::vector<AxisWord> words_;
    uint64_t count_ = 0;
    double t0_ = 0.0;
    bool started_ = false;
};

}  // namespace col

#include "trace.hpp"

#include <algorithm>
#include <cstring>

namespace col {

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

void Trace::analyze() {
    const auto& frames = parsed_.frames;

    // A whole log is available, so drives are known before decoding starts.
    std::vector<bool> drive(128, false), negative(128, false);
    if (opt_.auto_detect_drives) {
        for (const auto& f : frames) {
            uint8_t node = 0;
            int ev = drive_evidence(f, node);
            if (ev > 0) drive[node] = true;
            if (ev < 0) negative[node] = true;
        }
        for (int n = 0; n < 128; ++n)
            if (negative[n]) drive[n] = false;
    }

    records_.assign(frames.size(), Record{});
    words_.clear();
    Analyzer an(opt_, res_, drive_override_, base_mappings_, drive, parsed_.has_timestamps);
    for (uint32_t i = 0; i < frames.size(); ++i) an.process(frames[i], records_[i], i, words_);
    an.finish(duration());

    for (const auto& is : res_.issues)
        if (is.row < records_.size()) records_[is.row].has_issue = true;

    if (parsed_.skipped_lines > 0) {
        Issue is;
        is.severity = Severity::WARNING;
        is.type = IssueType::PARSE_ERRORS;
        is.code = parsed_.skipped_lines;
        is.value = parsed_.first_skipped_line;
        res_.issues.insert(res_.issues.begin(), is);
    }
    std::stable_sort(res_.issues.begin(), res_.issues.end(), [](const Issue& a, const Issue& b) {
        if (a.type == IssueType::PARSE_ERRORS) return b.type != IssueType::PARSE_ERRORS;
        if (b.type == IssueType::PARSE_ERRORS) return false;
        return a.row < b.row;
    });
}

std::vector<NodeInfo> Trace::nodes() const {
    std::vector<NodeInfo> out;
    for (const auto& ni : res_.node_info)
        if (ni.node > 0 && (ni.frame_count > 0 || ni.drive_forced)) out.push_back(ni);
    return out;
}

static const std::vector<StatePoint>& timeline_of(const Results& r, uint8_t node, uint8_t axis) {
    static const std::vector<StatePoint> empty;
    size_t k = static_cast<size_t>(node) * kMaxAxes + axis;
    if (axis >= kMaxAxes || k >= r.timelines.size()) return empty;
    return r.timelines[k];
}

const std::vector<StatePoint>& Trace::axis_timeline(uint8_t node, uint8_t axis) const {
    return timeline_of(res_, node, axis);
}

std::vector<AxisWord> Trace::axis_words(size_t row) const {
    const Record& r = records_.at(row);
    return std::vector<AxisWord>(words_.begin() + r.words_off, words_.begin() + r.words_off + r.words_count);
}

std::vector<PdoField> Trace::pdo_fields(size_t row) const {
    const Record& r = records_.at(row);
    if (r.map_ref == UINT32_MAX) return {};
    return decode_pdo_fields(parsed_.frames.at(row), res_.mappings[r.map_ref]);
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
                for (const auto& e : res_.mappings[r.map_ref].entries)
                    if (e.index == index) { hit = true; break; }
            }
            if (!hit) continue;
        }
        out.push_back(i);
    }
    return out;
}

// ------------------------------------------------------------------ LiveDecoder

LiveDecoder::LiveDecoder(const Options& opt) : opt_(opt) { reset(); }

void LiveDecoder::set_drive(uint8_t node, bool is_drive) {
    drive_override_[node] = is_drive;
    reset();
}

void LiveDecoder::set_base_mapping(uint8_t node, bool tx, uint8_t num, const std::vector<PdoMapEntry>& entries) {
    if (num < 1 || num > 4) return;
    base_mappings_[map_key(node, tx, num)] = entries;
    reset();
}

void LiveDecoder::reset() {
    res_ = Results{};
    analyzer_ = std::make_unique<Analyzer>(opt_, res_, drive_override_, base_mappings_, std::vector<bool>(128, false), true);
    frame_ = Frame{};
    record_ = Record{};
    words_.clear();
    count_ = 0;
    started_ = false;
    t0_ = 0.0;
}

size_t LiveDecoder::feed(double t, uint32_t id, const uint8_t* data, size_t len, bool ext, bool rtr, bool error, bool fd) {
    if (!started_) {
        started_ = true;
        t0_ = t;
    }
    size_t before = res_.issues.size();
    frame_ = Frame{};
    frame_.t = t - t0_;
    frame_.id = id & 0x1FFFFFFFu;
    frame_.ext = ext;
    frame_.rtr = rtr;
    frame_.error = error;
    frame_.fd = fd || len > 8;
    frame_.line = 0;
    size_t n = std::min(len, frame_.data.size());
    if (!rtr && n) std::memcpy(frame_.data.data(), data, n);
    frame_.dlc = static_cast<uint8_t>(rtr ? std::min<size_t>(len, 15) : n);
    record_ = Record{};
    words_.clear();
    analyzer_->process(frame_, record_, static_cast<uint32_t>(count_), words_);
    record_.words_off = 0;  // words_ holds only this frame's entries
    analyzer_->tick(frame_.t);
    ++count_;
    return res_.issues.size() - before;
}

size_t LiveDecoder::tick(double t) {
    if (!started_) return 0;
    size_t before = res_.issues.size();
    analyzer_->tick(t - t0_);
    return res_.issues.size() - before;
}

std::vector<PdoField> LiveDecoder::last_pdo_fields() const {
    if (record_.map_ref == UINT32_MAX) return {};
    return decode_pdo_fields(frame_, res_.mappings[record_.map_ref]);
}

std::vector<NodeInfo> LiveDecoder::nodes() {
    analyzer_->update_node_info();
    std::vector<NodeInfo> out;
    for (const auto& ni : res_.node_info)
        if (ni.node > 0 && (ni.frame_count > 0 || ni.drive_forced)) out.push_back(ni);
    return out;
}

const std::vector<StatePoint>& LiveDecoder::axis_timeline(uint8_t node, uint8_t axis) const {
    return timeline_of(res_, node, axis);
}

}  // namespace col

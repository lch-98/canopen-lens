#include "parser.hpp"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace col {
namespace {

int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool parse_hex_u32(std::string_view s, uint32_t& out) {
    if (s.empty() || s.size() > 8) return false;
    uint32_t v = 0;
    for (char c : s) {
        int h = hexval(c);
        if (h < 0) return false;
        v = (v << 4) | static_cast<uint32_t>(h);
    }
    out = v;
    return true;
}

// Reads hex byte pairs, ignoring '.' separators. Returns false on odd/invalid input.
bool parse_hex_bytes(std::string_view s, Frame& f) {
    size_t n = 0;
    int hi = -1;
    for (char c : s) {
        if (c == '.') continue;
        int h = hexval(c);
        if (h < 0) return false;
        if (hi < 0) {
            hi = h;
        } else {
            if (n >= f.data.size()) return false;
            f.data[n++] = static_cast<uint8_t>((hi << 4) | h);
            hi = -1;
        }
    }
    if (hi >= 0) return false;
    f.dlc = static_cast<uint8_t>(n);
    return true;
}

void split_ws(std::string_view line, std::vector<std::string_view>& out) {
    out.clear();
    size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() && (line[i] == ' ' || line[i] == '\t')) ++i;
        size_t j = i;
        while (j < line.size() && line[j] != ' ' && line[j] != '\t') ++j;
        if (j > i) out.push_back(line.substr(i, j - i));
        i = j;
    }
}

// Splits "(1760500000.123456)" into whole seconds and fraction so that
// relative times keep microsecond precision even for epoch timestamps.
struct Stamp {
    long long sec = 0;
    double frac = 0.0;
};

bool parse_timestamp(std::string_view tok, Stamp& ts) {
    if (tok.size() < 3 || tok.front() != '(' || tok.back() != ')') return false;
    std::string_view v = tok.substr(1, tok.size() - 2);
    size_t dot = v.find('.');
    std::string_view whole = v.substr(0, dot);
    if (whole.empty()) return false;
    long long sec = 0;
    for (char c : whole) {
        if (c < '0' || c > '9') return false;
        sec = sec * 10 + (c - '0');
    }
    double frac = 0.0;
    if (dot != std::string_view::npos) {
        double scale = 0.1;
        for (char c : v.substr(dot + 1)) {
            if (c < '0' || c > '9') return false;
            frac += (c - '0') * scale;
            scale *= 0.1;
        }
    }
    ts.sec = sec;
    ts.frac = frac;
    return true;
}

void set_id(Frame& f, std::string_view id_tok, uint32_t id) {
    f.ext = id_tok.size() > 3;
    if (f.ext && (id & 0x20000000u)) f.error = true;  // CAN_ERR_FLAG
    f.id = id & 0x1FFFFFFFu;
}

// "123#11223344", "123#R", "123#R4", "123##1AABBCC" (CAN FD)
bool parse_log_body(std::string_view tok, Frame& f) {
    size_t hash = tok.find('#');
    if (hash == std::string_view::npos || hash == 0) return false;
    std::string_view id_tok = tok.substr(0, hash);
    uint32_t id;
    if (!parse_hex_u32(id_tok, id)) return false;
    set_id(f, id_tok, id);
    std::string_view rest = tok.substr(hash + 1);
    if (!rest.empty() && rest[0] == '#') {  // CAN FD: flags nibble then data
        f.fd = true;
        if (rest.size() < 2 || hexval(rest[1]) < 0) return false;
        return parse_hex_bytes(rest.substr(2), f);
    }
    if (!rest.empty() && (rest[0] == 'R' || rest[0] == 'r')) {
        f.rtr = true;
        f.dlc = 0;
        if (rest.size() > 1) {
            int h = hexval(rest[1]);
            if (h >= 0) f.dlc = static_cast<uint8_t>(h);
        }
        return true;
    }
    return parse_hex_bytes(rest, f);
}

// tokens after the interface: [extra...] ID [dlc] b0 b1 ... or "remote request"
bool parse_console_body(const std::vector<std::string_view>& tk, size_t start, Frame& f) {
    for (size_t k = start; k + 1 < tk.size(); ++k) {
        std::string_view d = tk[k + 1];
        if (d.size() < 3 || d.front() != '[' || d.back() != ']') continue;
        uint32_t id;
        if (!parse_hex_u32(tk[k], id)) continue;
        set_id(f, tk[k], id);
        std::string dl(d.substr(1, d.size() - 2));
        char* end = nullptr;
        long dlc = std::strtol(dl.c_str(), &end, 10);
        if (!end || *end != '\0' || dlc < 0 || dlc > 64) return false;
        if (dlc > 8) f.fd = true;
        size_t i = k + 2;
        if (i < tk.size() && tk[i] == "remote") {
            f.rtr = true;
            f.dlc = static_cast<uint8_t>(dlc);
            return true;
        }
        size_t n = 0;
        for (; i < tk.size() && n < static_cast<size_t>(dlc); ++i, ++n) {
            std::string_view b = tk[i];
            if (b.size() != 2 || hexval(b[0]) < 0 || hexval(b[1]) < 0) return false;
            f.data[n] = static_cast<uint8_t>((hexval(b[0]) << 4) | hexval(b[1]));
        }
        if (n != static_cast<size_t>(dlc)) return false;
        f.dlc = static_cast<uint8_t>(dlc);
        return true;
    }
    return false;
}

}  // namespace

ParseResult parse_candump_text(const std::string& text) {
    ParseResult r;
    std::vector<std::string_view> tk;
    std::vector<Stamp> raw_t;
    size_t pos = 0;
    uint32_t line_no = 0;
    bool any_log = false, any_console = false, any_missing_ts = false;

    while (pos <= text.size()) {
        size_t nl = text.find('\n', pos);
        if (nl == std::string::npos) nl = text.size();
        std::string_view line(text.data() + pos, nl - pos);
        pos = nl + 1;
        ++line_no;
        if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
        split_ws(line, tk);
        if (tk.empty()) {
            if (nl == text.size()) break;
            continue;
        }

        Frame f;
        f.line = line_no;
        size_t i = 0;
        Stamp t;
        bool has_t = parse_timestamp(tk[0], t);
        if (has_t) ++i;

        bool ok = false;
        if (i + 1 < tk.size()) {
            std::string_view iface = tk[i];
            if (tk[i + 1].find('#') != std::string_view::npos) {
                ok = parse_log_body(tk[i + 1], f);
                if (ok) any_log = true;
            } else {
                ok = parse_console_body(tk, i + 1, f);
                if (ok) any_console = true;
            }
            if (ok) {
                uint16_t idx = 0;
                for (; idx < r.interfaces.size(); ++idx)
                    if (r.interfaces[idx] == iface) break;
                if (idx == r.interfaces.size()) r.interfaces.emplace_back(iface);
                f.iface = idx;
            }
        }
        if (!ok) {
            if (r.skipped_lines == 0) r.first_skipped_line = line_no;
            ++r.skipped_lines;
        } else {
            if (!has_t) any_missing_ts = true;
            raw_t.push_back(has_t ? t : Stamp{});
            r.frames.push_back(f);
        }
        if (nl == text.size()) break;
    }

    r.has_timestamps = !r.frames.empty() && !any_missing_ts;
    r.format = any_log && any_console ? "candump-mixed" : any_log ? "candump-log" : "candump-console";

    if (r.has_timestamps) {
        // `candump -t d` prints the delta to the previous frame. Detect it by
        // counting how often time goes backwards and integrate if needed.
        auto rel = [&](size_t k) {
            return static_cast<double>(raw_t[k].sec - raw_t[0].sec) + (raw_t[k].frac - raw_t[0].frac);
        };
        // Absolute/relative stamps (-t a / -t z / -l) keep rising; delta stamps
        // (-t d) repeat and fall back all the time.
        size_t not_rising = 0;
        for (size_t k = 1; k < raw_t.size(); ++k)
            if (rel(k) <= rel(k - 1)) ++not_rising;
        bool delta_mode = raw_t.size() > 4 && not_rising * 10 > raw_t.size() * 3;
        r.t0 = static_cast<double>(raw_t[0].sec) + raw_t[0].frac;
        if (delta_mode) {
            double acc = 0.0;
            for (size_t k = 0; k < r.frames.size(); ++k) {
                if (k > 0) acc += static_cast<double>(raw_t[k].sec) + raw_t[k].frac;
                r.frames[k].t = acc;
            }
            r.format += "-delta";
        } else {
            for (size_t k = 0; k < r.frames.size(); ++k) r.frames[k].t = rel(k);
        }
    }
    return r;
}

ParseResult parse_candump_file(const std::string& path) {
    std::ifstream in(std::filesystem::u8path(path), std::ios::binary);
    if (!in) throw std::runtime_error("cannot open file: " + path);
    std::ostringstream ss;
    ss << in.rdbuf();
    return parse_candump_text(ss.str());
}

}  // namespace col

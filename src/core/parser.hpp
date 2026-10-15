// Log file parsers. Each parser turns text into a list of Frame objects;
// everything after that is format independent.
#pragma once

#include <string>
#include <vector>

#include "types.hpp"

namespace col {

struct ParseResult {
    std::vector<Frame> frames;
    std::vector<std::string> interfaces;   // e.g. "can0"
    double t0 = 0.0;                      // absolute timestamp of the first frame
    bool has_timestamps = false;
    uint32_t skipped_lines = 0;           // non-empty lines that were not understood
    uint32_t first_skipped_line = 0;
    std::string format;                   // "candump-log", "candump-console", ...
};

// Parses output of `candump -l` (log file) and of `candump [-t a|z] can0`
// (console output). Formats can be mixed line by line.
ParseResult parse_candump_text(const std::string& text);

// Reads a whole file and calls parse_candump_text.
ParseResult parse_candump_file(const std::string& path);

}  // namespace col

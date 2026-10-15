// Common data structures shared by the parser, decoder and analyzer.
#pragma once

#include <array>
#include <climits>
#include <cstdint>
#include <string>
#include <vector>

namespace col {

// One raw CAN frame as read from a log file.
struct Frame {
    double t = 0.0;          // seconds, relative to the first frame
    uint32_t id = 0;         // CAN identifier (11 or 29 bit)
    uint8_t dlc = 0;         // payload length in bytes (0..64)
    bool rtr = false;        // remote transmission request
    bool ext = false;        // 29-bit identifier
    bool fd = false;         // CAN FD frame
    bool error = false;      // error frame reported by the driver
    uint16_t iface = 0;      // index into Trace::interfaces
    uint32_t line = 0;       // 1-based line number in the source file
    std::array<uint8_t, 64> data{};
};

// What a frame means in CANopen terms (CiA 301 predefined connection set).
enum class Kind : uint8_t {
    NMT,
    SYNC,
    EMCY,
    TIME,
    TPDO,
    RPDO,
    SDO_REQ,   // client -> server (0x600 + node)
    SDO_RESP,  // server -> client (0x580 + node)
    HEARTBEAT,
    LSS,
    ERROR_FRAME,
    UNKNOWN,
    COUNT_
};

enum class SdoType : uint8_t {
    NONE,
    DOWNLOAD_INIT,     // write request / response
    UPLOAD_INIT,       // read request / response
    DOWNLOAD_SEGMENT,
    UPLOAD_SEGMENT,
    ABORT,
    BLOCK,
    INVALID
};

// CiA 402 power state machine states.
enum class AxisState : int8_t {
    UNKNOWN = -1,
    NOT_READY_TO_SWITCH_ON = 0,
    SWITCH_ON_DISABLED,
    READY_TO_SWITCH_ON,
    SWITCHED_ON,
    OPERATION_ENABLED,
    QUICK_STOP_ACTIVE,
    FAULT_REACTION_ACTIVE,
    FAULT
};

// CiA 402 controlword commands.
enum class CwCommand : int8_t {
    NONE = -1,
    SHUTDOWN = 0,
    SWITCH_ON,           // also "disable operation" (same bit pattern)
    ENABLE_OPERATION,
    DISABLE_VOLTAGE,
    QUICK_STOP,
    FAULT_RESET
};

// Decoded meaning of a single frame. Plain fields so it stays cheap to copy
// into Python; text is produced on the Python side so it can be localized.
struct Record {
    Kind kind = Kind::UNKNOWN;
    uint8_t node = 0;          // CANopen node-ID, 0 when not applicable
    uint8_t pdo_num = 0;       // 1..4 for PDOs

    // NMT
    uint8_t nmt_cmd = 0;
    uint8_t nmt_target = 0;

    // Heartbeat
    uint8_t hb_state = 0;

    // SDO
    SdoType sdo_type = SdoType::NONE;
    uint16_t index = 0;
    uint8_t sub = 0;
    bool sdo_expedited = false;
    uint8_t value_len = 0;     // bytes of `value` that are valid
    uint32_t value = 0;
    uint32_t abort_code = 0;
    uint32_t sdo_size = 0;     // announced size for segmented transfers
    bool sdo_index_known = false;

    // EMCY
    uint16_t emcy_code = 0;
    uint8_t error_register = 0;

    // CiA 402 (set when this frame carries a statusword / controlword)
    bool has_statusword = false;
    uint16_t statusword = 0;
    AxisState axis_state = AxisState::UNKNOWN;
    bool has_controlword = false;
    uint16_t controlword = 0;
    CwCommand cw_command = CwCommand::NONE;

    bool has_issue = false;
    uint32_t map_ref = UINT32_MAX;  // PDO mapping version used to decode this frame
};

enum class Severity : uint8_t { INFO = 0, WARNING, ERROR };

enum class IssueType : uint8_t {
    SDO_ABORT,
    SDO_NO_RESPONSE,
    EMCY,
    EMCY_RESET,
    HEARTBEAT_GAP,
    HEARTBEAT_LOST,
    NODE_REBOOT,
    AXIS_FAULT,
    AXIS_QUICK_STOP,
    AXIS_ENABLE_FAILED,
    AXIS_FAULT_RESET_FAILED,
    BUS_ERROR_FRAME,
    PARSE_ERRORS
};

struct Issue {
    Severity severity = Severity::INFO;
    IssueType type = IssueType::EMCY;
    double t = 0.0;
    uint32_t row = 0;          // frame index the issue points at
    uint8_t node = 0;
    uint32_t code = 0;         // abort code, EMCY code, state, ...
    uint16_t index = 0;        // object index when relevant
    uint8_t sub = 0;
    double value = 0.0;        // e.g. gap length in seconds
    double expected = 0.0;     // e.g. normal heartbeat period
    int64_t related_row = -1;  // e.g. the EMCY frame that explains a fault
};

struct PdoMapEntry {
    uint16_t index = 0;
    uint8_t sub = 0;
    uint8_t bits = 0;
};

enum class MapOrigin : uint8_t { NONE = 0, CIA402_DEFAULT, EDS, LOG_SDO };

struct PdoMapping {
    uint8_t node = 0;
    bool tx = true;            // TPDO (device -> master) or RPDO
    uint8_t num = 1;
    MapOrigin origin = MapOrigin::NONE;
    uint32_t since_row = 0;    // first frame this version applies to
    std::vector<PdoMapEntry> entries;
};

struct PdoField {
    uint16_t index = 0;
    uint8_t sub = 0;
    uint8_t bits = 0;
    uint64_t raw = 0;
    bool complete = true;      // false if the frame was too short
};

struct StatePoint {
    double t = 0.0;
    uint32_t row = 0;
    AxisState state = AxisState::UNKNOWN;
    uint16_t statusword = 0;
};

struct NodeInfo {
    uint8_t node = 0;
    uint32_t frame_count = 0;
    std::array<uint32_t, static_cast<size_t>(Kind::COUNT_)> kind_counts{};
    double first_seen = 0.0;
    double last_seen = 0.0;
    int last_hb_state = -1;    // -1 = no heartbeat seen
    uint32_t hb_count = 0;
    double hb_period = 0.0;    // median interval, 0 if unknown
    bool is_drive = false;     // treated as a CiA 402 device
    bool drive_forced = false; // set by the user rather than detected
    uint32_t device_type = 0;  // object 0x1000 if it was read
    bool device_type_known = false;
    AxisState axis_state = AxisState::UNKNOWN;
    uint32_t emcy_count = 0;
    uint32_t sdo_abort_count = 0;
    uint32_t reboot_count = 0;
};

}  // namespace col

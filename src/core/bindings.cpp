// Python bindings for the C++ core (module canopen_lens._core).
#include <cstdio>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/stl_bind.h>

#include "parser.hpp"
#include "trace.hpp"

namespace py = pybind11;
using namespace col;

PYBIND11_MAKE_OPAQUE(std::vector<uint32_t>);

PYBIND11_MODULE(_core, m) {
    m.doc() = "C++ core of canopen-lens: candump parsing, CANopen decoding and diagnostics";

    py::bind_vector<std::vector<uint32_t>>(m, "IndexList", py::buffer_protocol());

    py::enum_<Kind>(m, "Kind")
        .value("NMT", Kind::NMT)
        .value("SYNC", Kind::SYNC)
        .value("EMCY", Kind::EMCY)
        .value("TIME", Kind::TIME)
        .value("TPDO", Kind::TPDO)
        .value("RPDO", Kind::RPDO)
        .value("SDO_REQ", Kind::SDO_REQ)
        .value("SDO_RESP", Kind::SDO_RESP)
        .value("HEARTBEAT", Kind::HEARTBEAT)
        .value("LSS", Kind::LSS)
        .value("ERROR_FRAME", Kind::ERROR_FRAME)
        .value("UNKNOWN", Kind::UNKNOWN);

    py::enum_<SdoType>(m, "SdoType")
        .value("NONE", SdoType::NONE)
        .value("DOWNLOAD_INIT", SdoType::DOWNLOAD_INIT)
        .value("UPLOAD_INIT", SdoType::UPLOAD_INIT)
        .value("DOWNLOAD_SEGMENT", SdoType::DOWNLOAD_SEGMENT)
        .value("UPLOAD_SEGMENT", SdoType::UPLOAD_SEGMENT)
        .value("ABORT", SdoType::ABORT)
        .value("BLOCK", SdoType::BLOCK)
        .value("INVALID", SdoType::INVALID);

    py::enum_<AxisState>(m, "AxisState")
        .value("UNKNOWN", AxisState::UNKNOWN)
        .value("NOT_READY_TO_SWITCH_ON", AxisState::NOT_READY_TO_SWITCH_ON)
        .value("SWITCH_ON_DISABLED", AxisState::SWITCH_ON_DISABLED)
        .value("READY_TO_SWITCH_ON", AxisState::READY_TO_SWITCH_ON)
        .value("SWITCHED_ON", AxisState::SWITCHED_ON)
        .value("OPERATION_ENABLED", AxisState::OPERATION_ENABLED)
        .value("QUICK_STOP_ACTIVE", AxisState::QUICK_STOP_ACTIVE)
        .value("FAULT_REACTION_ACTIVE", AxisState::FAULT_REACTION_ACTIVE)
        .value("FAULT", AxisState::FAULT);

    py::enum_<CwCommand>(m, "CwCommand")
        .value("NONE", CwCommand::NONE)
        .value("SHUTDOWN", CwCommand::SHUTDOWN)
        .value("SWITCH_ON", CwCommand::SWITCH_ON)
        .value("ENABLE_OPERATION", CwCommand::ENABLE_OPERATION)
        .value("DISABLE_VOLTAGE", CwCommand::DISABLE_VOLTAGE)
        .value("QUICK_STOP", CwCommand::QUICK_STOP)
        .value("FAULT_RESET", CwCommand::FAULT_RESET);

    py::enum_<Severity>(m, "Severity")
        .value("INFO", Severity::INFO)
        .value("WARNING", Severity::WARNING)
        .value("ERROR", Severity::ERROR);

    py::enum_<IssueType>(m, "IssueType")
        .value("SDO_ABORT", IssueType::SDO_ABORT)
        .value("SDO_NO_RESPONSE", IssueType::SDO_NO_RESPONSE)
        .value("EMCY", IssueType::EMCY)
        .value("EMCY_RESET", IssueType::EMCY_RESET)
        .value("HEARTBEAT_GAP", IssueType::HEARTBEAT_GAP)
        .value("HEARTBEAT_LOST", IssueType::HEARTBEAT_LOST)
        .value("NODE_REBOOT", IssueType::NODE_REBOOT)
        .value("AXIS_FAULT", IssueType::AXIS_FAULT)
        .value("AXIS_QUICK_STOP", IssueType::AXIS_QUICK_STOP)
        .value("AXIS_ENABLE_FAILED", IssueType::AXIS_ENABLE_FAILED)
        .value("AXIS_FAULT_RESET_FAILED", IssueType::AXIS_FAULT_RESET_FAILED)
        .value("BUS_ERROR_FRAME", IssueType::BUS_ERROR_FRAME)
        .value("PARSE_ERRORS", IssueType::PARSE_ERRORS);

    py::enum_<MapOrigin>(m, "MapOrigin")
        .value("NONE", MapOrigin::NONE)
        .value("CIA402_DEFAULT", MapOrigin::CIA402_DEFAULT)
        .value("EDS", MapOrigin::EDS)
        .value("LOG_SDO", MapOrigin::LOG_SDO);

    py::class_<Frame>(m, "Frame")
        .def_readonly("t", &Frame::t)
        .def_readonly("id", &Frame::id)
        .def_readonly("dlc", &Frame::dlc)
        .def_readonly("rtr", &Frame::rtr)
        .def_readonly("ext", &Frame::ext)
        .def_readonly("fd", &Frame::fd)
        .def_readonly("error", &Frame::error)
        .def_readonly("iface", &Frame::iface)
        .def_readonly("line", &Frame::line)
        .def_property_readonly("data", [](const Frame& f) {
            return py::bytes(reinterpret_cast<const char*>(f.data.data()), f.rtr ? 0 : f.dlc);
        });

    py::class_<Record>(m, "Record")
        .def_readonly("kind", &Record::kind)
        .def_readonly("node", &Record::node)
        .def_readonly("pdo_num", &Record::pdo_num)
        .def_readonly("nmt_cmd", &Record::nmt_cmd)
        .def_readonly("nmt_target", &Record::nmt_target)
        .def_readonly("hb_state", &Record::hb_state)
        .def_readonly("sdo_type", &Record::sdo_type)
        .def_readonly("index", &Record::index)
        .def_readonly("sub", &Record::sub)
        .def_readonly("sdo_expedited", &Record::sdo_expedited)
        .def_readonly("value_len", &Record::value_len)
        .def_readonly("value", &Record::value)
        .def_readonly("abort_code", &Record::abort_code)
        .def_readonly("sdo_size", &Record::sdo_size)
        .def_readonly("sdo_index_known", &Record::sdo_index_known)
        .def_readonly("emcy_code", &Record::emcy_code)
        .def_readonly("error_register", &Record::error_register)
        .def_readonly("has_statusword", &Record::has_statusword)
        .def_readonly("statusword", &Record::statusword)
        .def_readonly("axis_state", &Record::axis_state)
        .def_readonly("has_controlword", &Record::has_controlword)
        .def_readonly("controlword", &Record::controlword)
        .def_readonly("cw_command", &Record::cw_command)
        .def_readonly("has_issue", &Record::has_issue)
        .def_property_readonly("map_ref", [](const Record& r) -> py::object {
            if (r.map_ref == UINT32_MAX) return py::none();
            return py::int_(r.map_ref);
        });

    py::class_<Issue>(m, "Issue")
        .def_readonly("severity", &Issue::severity)
        .def_readonly("type", &Issue::type)
        .def_readonly("t", &Issue::t)
        .def_readonly("row", &Issue::row)
        .def_readonly("node", &Issue::node)
        .def_readonly("code", &Issue::code)
        .def_readonly("index", &Issue::index)
        .def_readonly("sub", &Issue::sub)
        .def_readonly("value", &Issue::value)
        .def_readonly("expected", &Issue::expected)
        .def_property_readonly("related_row", [](const Issue& i) -> py::object {
            if (i.related_row < 0) return py::none();
            return py::int_(i.related_row);
        });

    py::class_<PdoMapEntry>(m, "PdoMapEntry")
        .def(py::init([](uint16_t index, uint8_t sub, uint8_t bits) { return PdoMapEntry{index, sub, bits}; }),
             py::arg("index"), py::arg("sub"), py::arg("bits"))
        .def_readonly("index", &PdoMapEntry::index)
        .def_readonly("sub", &PdoMapEntry::sub)
        .def_readonly("bits", &PdoMapEntry::bits)
        .def("__repr__", [](const PdoMapEntry& e) {
            char buf[48];
            std::snprintf(buf, sizeof buf, "PdoMapEntry(0x%04X:%02X, %u bit)", e.index, e.sub, e.bits);
            return std::string(buf);
        });

    py::class_<PdoMapping>(m, "PdoMapping")
        .def_readonly("node", &PdoMapping::node)
        .def_readonly("tx", &PdoMapping::tx)
        .def_readonly("num", &PdoMapping::num)
        .def_readonly("origin", &PdoMapping::origin)
        .def_readonly("since_row", &PdoMapping::since_row)
        .def_readonly("entries", &PdoMapping::entries);

    py::class_<PdoField>(m, "PdoField")
        .def_readonly("index", &PdoField::index)
        .def_readonly("sub", &PdoField::sub)
        .def_readonly("bits", &PdoField::bits)
        .def_readonly("raw", &PdoField::raw)
        .def_readonly("complete", &PdoField::complete);

    py::class_<StatePoint>(m, "StatePoint")
        .def_readonly("t", &StatePoint::t)
        .def_readonly("row", &StatePoint::row)
        .def_readonly("state", &StatePoint::state)
        .def_readonly("statusword", &StatePoint::statusword);

    py::class_<NodeInfo>(m, "NodeInfo")
        .def_readonly("node", &NodeInfo::node)
        .def_readonly("frame_count", &NodeInfo::frame_count)
        .def_property_readonly("kind_counts", [](const NodeInfo& n) {
            py::dict d;
            for (size_t k = 0; k < n.kind_counts.size(); ++k)
                if (n.kind_counts[k]) d[py::cast(static_cast<Kind>(k))] = n.kind_counts[k];
            return d;
        })
        .def_readonly("first_seen", &NodeInfo::first_seen)
        .def_readonly("last_seen", &NodeInfo::last_seen)
        .def_readonly("last_hb_state", &NodeInfo::last_hb_state)
        .def_readonly("hb_count", &NodeInfo::hb_count)
        .def_readonly("hb_period", &NodeInfo::hb_period)
        .def_readonly("is_drive", &NodeInfo::is_drive)
        .def_readonly("drive_forced", &NodeInfo::drive_forced)
        .def_readonly("device_type", &NodeInfo::device_type)
        .def_readonly("device_type_known", &NodeInfo::device_type_known)
        .def_readonly("axis_state", &NodeInfo::axis_state)
        .def_readonly("emcy_count", &NodeInfo::emcy_count)
        .def_readonly("sdo_abort_count", &NodeInfo::sdo_abort_count)
        .def_readonly("reboot_count", &NodeInfo::reboot_count);

    py::class_<Options>(m, "Options")
        .def(py::init<>())
        .def_readwrite("sdo_timeout", &Options::sdo_timeout)
        .def_readwrite("state_timeout", &Options::state_timeout)
        .def_readwrite("hb_gap_factor", &Options::hb_gap_factor)
        .def_readwrite("auto_detect_drives", &Options::auto_detect_drives);

    py::class_<Trace>(m, "Trace")
        .def_static(
            "from_bytes",
            [](py::bytes data, const Options& opt) {
                std::string s = data;  // copy while holding the GIL
                py::gil_scoped_release release;
                return Trace::from_text(s, opt);
            },
            py::arg("data"), py::arg("options") = Options{})
        .def_static(
            "from_text",
            [](const std::string& text, const Options& opt) {
                py::gil_scoped_release release;
                return Trace::from_text(text, opt);
            },
            py::arg("text"), py::arg("options") = Options{})
        .def("analyze", &Trace::analyze, py::call_guard<py::gil_scoped_release>())
        .def("set_drive", &Trace::set_drive, py::arg("node"), py::arg("is_drive"))
        .def("clear_drive_override", &Trace::clear_drive_override, py::arg("node"))
        .def("set_base_mapping", &Trace::set_base_mapping, py::arg("node"), py::arg("tx"), py::arg("num"),
             py::arg("entries"))
        .def("clear_base_mappings", &Trace::clear_base_mappings)
        .def_property_readonly("options", [](Trace& t) -> Options& { return t.options(); },
                               py::return_value_policy::reference_internal)
        .def("__len__", &Trace::size)
        .def("frame", &Trace::frame, py::arg("row"), py::return_value_policy::copy)
        .def("record", &Trace::record, py::arg("row"), py::return_value_policy::copy)
        .def_property_readonly("issues", &Trace::issues)
        .def_property_readonly("nodes", &Trace::nodes)
        .def("axis_timeline", &Trace::axis_timeline, py::arg("node"))
        .def("mapping", &Trace::mapping, py::arg("ref"), py::return_value_policy::copy)
        .def_property_readonly("mapping_count", &Trace::mapping_count)
        .def("pdo_fields", &Trace::pdo_fields, py::arg("row"))
        .def_property_readonly("interfaces", &Trace::interfaces)
        .def_property_readonly("duration", &Trace::duration)
        .def_property_readonly("t0", &Trace::t0)
        .def_property_readonly("has_timestamps", &Trace::has_timestamps)
        .def_property_readonly("skipped_lines", &Trace::skipped_lines)
        .def_property_readonly("format", &Trace::format)
        .def_property_readonly("kind_counts",
                               [](const Trace& t) {
                                   auto c = t.kind_counts();
                                   py::dict d;
                                   for (size_t k = 0; k < c.size(); ++k) d[py::cast(static_cast<Kind>(k))] = c[k];
                                   return d;
                               })
        .def(
            "filter",
            [](const Trace& t, py::object kinds, int node, bool issues_only, int index) {
                uint32_t mask = 0xFFFFFFFFu;
                if (!kinds.is_none()) {
                    mask = 0;
                    for (auto k : kinds) mask |= 1u << static_cast<unsigned>(k.cast<Kind>());
                }
                py::gil_scoped_release release;
                return t.filter(mask, node, issues_only, index);
            },
            py::arg("kinds") = py::none(), py::arg("node") = -1, py::arg("issues_only") = false,
            py::arg("index") = -1);

    m.def("decode_statusword", &decode_statusword, py::arg("statusword"));
    m.def("decode_controlword", &decode_controlword, py::arg("controlword"), py::arg("previous") = 0);
}

"""
C++ core of canopen-lens: candump parsing, CANopen decoding and diagnostics
"""
from __future__ import annotations
import collections.abc
import typing
__all__: list[str] = ['AxisState', 'AxisWord', 'CwCommand', 'Frame', 'IndexList', 'Issue', 'IssueType', 'Kind', 'LiveDecoder', 'MapOrigin', 'NodeInfo', 'Options', 'PdoField', 'PdoMapEntry', 'PdoMapping', 'Record', 'SdoType', 'Severity', 'StatePoint', 'Trace', 'decode_controlword', 'decode_statusword']
class IndexList:
    __hash__: typing.ClassVar[None] = None
    def __bool__(self) -> bool:
        """
        Check whether the list is nonempty
        """
    def __buffer__(self, flags):
        """
        Return a buffer object that exposes the underlying memory of the object.
        """
    def __contains__(self, x: typing.SupportsInt | typing.SupportsIndex) -> bool:
        """
        Return true the container contains ``x``
        """
    @typing.overload
    def __delitem__(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        """
        Delete the list elements at index ``i``
        """
    @typing.overload
    def __delitem__(self, arg0: slice) -> None:
        """
        Delete list elements using a slice object
        """
    def __eq__(self, arg0: IndexList) -> bool:
        ...
    @typing.overload
    def __getitem__(self, s: slice) -> IndexList:
        """
        Retrieve list elements using a slice object
        """
    @typing.overload
    def __getitem__(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    @typing.overload
    def __init__(self, arg0: collections.abc.Buffer) -> None:
        ...
    @typing.overload
    def __init__(self) -> None:
        ...
    @typing.overload
    def __init__(self, arg0: IndexList) -> None:
        """
        Copy constructor
        """
    @typing.overload
    def __init__(self, arg0: collections.abc.Iterable) -> None:
        ...
    def __iter__(self) -> collections.abc.Iterator[int]:
        ...
    def __len__(self) -> int:
        ...
    def __ne__(self, arg0: IndexList) -> bool:
        ...
    def __release_buffer__(self, buffer):
        """
        Release the buffer object that exposes the underlying memory of the object.
        """
    def __repr__(self) -> str:
        """
        Return the canonical string representation of this list.
        """
    @typing.overload
    def __setitem__(self, arg0: typing.SupportsInt | typing.SupportsIndex, arg1: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @typing.overload
    def __setitem__(self, arg0: slice, arg1: IndexList) -> None:
        """
        Assign list elements using a slice object
        """
    def append(self, x: typing.SupportsInt | typing.SupportsIndex) -> None:
        """
        Add an item to the end of the list
        """
    def clear(self) -> None:
        """
        Clear the contents
        """
    def count(self, x: typing.SupportsInt | typing.SupportsIndex) -> int:
        """
        Return the number of times ``x`` appears in the list
        """
    @typing.overload
    def extend(self, L: IndexList) -> None:
        """
        Extend the list by appending all the items in the given list
        """
    @typing.overload
    def extend(self, L: collections.abc.Iterable) -> None:
        """
        Extend the list by appending all the items in the given list
        """
    def insert(self, i: typing.SupportsInt | typing.SupportsIndex, x: typing.SupportsInt | typing.SupportsIndex) -> None:
        """
        Insert an item at a given position.
        """
    @typing.overload
    def pop(self) -> int:
        """
        Remove and return the last item
        """
    @typing.overload
    def pop(self, i: typing.SupportsInt | typing.SupportsIndex) -> int:
        """
        Remove and return the item at index ``i``
        """
    def remove(self, x: typing.SupportsInt | typing.SupportsIndex) -> None:
        """
        Remove the first item from the list whose value is x. It is an error if there is no such item.
        """
class Kind:
    """
    Members:
    
      NMT
    
      SYNC
    
      EMCY
    
      TIME
    
      TPDO
    
      RPDO
    
      SDO_REQ
    
      SDO_RESP
    
      HEARTBEAT
    
      LSS
    
      ERROR_FRAME
    
      UNKNOWN
    """
    EMCY: typing.ClassVar[Kind]
    ERROR_FRAME: typing.ClassVar[Kind]
    HEARTBEAT: typing.ClassVar[Kind]
    LSS: typing.ClassVar[Kind]
    NMT: typing.ClassVar[Kind]
    RPDO: typing.ClassVar[Kind]
    SDO_REQ: typing.ClassVar[Kind]
    SDO_RESP: typing.ClassVar[Kind]
    SYNC: typing.ClassVar[Kind]
    TIME: typing.ClassVar[Kind]
    TPDO: typing.ClassVar[Kind]
    UNKNOWN: typing.ClassVar[Kind]
    __members__: typing.ClassVar[dict[str, Kind]]
    @typing.overload
    def __eq__(self, other: Kind) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: Kind) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class SdoType:
    """
    Members:
    
      NONE
    
      DOWNLOAD_INIT
    
      UPLOAD_INIT
    
      DOWNLOAD_SEGMENT
    
      UPLOAD_SEGMENT
    
      ABORT
    
      BLOCK
    
      INVALID
    """
    ABORT: typing.ClassVar[SdoType]
    BLOCK: typing.ClassVar[SdoType]
    DOWNLOAD_INIT: typing.ClassVar[SdoType]
    DOWNLOAD_SEGMENT: typing.ClassVar[SdoType]
    INVALID: typing.ClassVar[SdoType]
    NONE: typing.ClassVar[SdoType]
    UPLOAD_INIT: typing.ClassVar[SdoType]
    UPLOAD_SEGMENT: typing.ClassVar[SdoType]
    __members__: typing.ClassVar[dict[str, SdoType]]
    @typing.overload
    def __eq__(self, other: SdoType) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: SdoType) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class AxisState:
    """
    Members:
    
      UNKNOWN
    
      NOT_READY_TO_SWITCH_ON
    
      SWITCH_ON_DISABLED
    
      READY_TO_SWITCH_ON
    
      SWITCHED_ON
    
      OPERATION_ENABLED
    
      QUICK_STOP_ACTIVE
    
      FAULT_REACTION_ACTIVE
    
      FAULT
    """
    FAULT: typing.ClassVar[AxisState]
    FAULT_REACTION_ACTIVE: typing.ClassVar[AxisState]
    NOT_READY_TO_SWITCH_ON: typing.ClassVar[AxisState]
    OPERATION_ENABLED: typing.ClassVar[AxisState]
    QUICK_STOP_ACTIVE: typing.ClassVar[AxisState]
    READY_TO_SWITCH_ON: typing.ClassVar[AxisState]
    SWITCHED_ON: typing.ClassVar[AxisState]
    SWITCH_ON_DISABLED: typing.ClassVar[AxisState]
    UNKNOWN: typing.ClassVar[AxisState]
    __members__: typing.ClassVar[dict[str, AxisState]]
    @typing.overload
    def __eq__(self, other: AxisState) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: AxisState) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class CwCommand:
    """
    Members:
    
      NONE
    
      SHUTDOWN
    
      SWITCH_ON
    
      ENABLE_OPERATION
    
      DISABLE_VOLTAGE
    
      QUICK_STOP
    
      FAULT_RESET
    """
    DISABLE_VOLTAGE: typing.ClassVar[CwCommand]
    ENABLE_OPERATION: typing.ClassVar[CwCommand]
    FAULT_RESET: typing.ClassVar[CwCommand]
    NONE: typing.ClassVar[CwCommand]
    QUICK_STOP: typing.ClassVar[CwCommand]
    SHUTDOWN: typing.ClassVar[CwCommand]
    SWITCH_ON: typing.ClassVar[CwCommand]
    __members__: typing.ClassVar[dict[str, CwCommand]]
    @typing.overload
    def __eq__(self, other: CwCommand) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: CwCommand) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Severity:
    """
    Members:
    
      INFO
    
      WARNING
    
      ERROR
    """
    ERROR: typing.ClassVar[Severity]
    INFO: typing.ClassVar[Severity]
    WARNING: typing.ClassVar[Severity]
    __members__: typing.ClassVar[dict[str, Severity]]
    @typing.overload
    def __eq__(self, other: Severity) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: Severity) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class IssueType:
    """
    Members:
    
      SDO_ABORT
    
      SDO_NO_RESPONSE
    
      EMCY
    
      EMCY_RESET
    
      HEARTBEAT_GAP
    
      HEARTBEAT_LOST
    
      NODE_REBOOT
    
      AXIS_FAULT
    
      AXIS_QUICK_STOP
    
      AXIS_ENABLE_FAILED
    
      AXIS_FAULT_RESET_FAILED
    
      BUS_ERROR_FRAME
    
      PARSE_ERRORS
    """
    AXIS_ENABLE_FAILED: typing.ClassVar[IssueType]
    AXIS_FAULT: typing.ClassVar[IssueType]
    AXIS_FAULT_RESET_FAILED: typing.ClassVar[IssueType]
    AXIS_QUICK_STOP: typing.ClassVar[IssueType]
    BUS_ERROR_FRAME: typing.ClassVar[IssueType]
    EMCY: typing.ClassVar[IssueType]
    EMCY_RESET: typing.ClassVar[IssueType]
    HEARTBEAT_GAP: typing.ClassVar[IssueType]
    HEARTBEAT_LOST: typing.ClassVar[IssueType]
    NODE_REBOOT: typing.ClassVar[IssueType]
    PARSE_ERRORS: typing.ClassVar[IssueType]
    SDO_ABORT: typing.ClassVar[IssueType]
    SDO_NO_RESPONSE: typing.ClassVar[IssueType]
    __members__: typing.ClassVar[dict[str, IssueType]]
    @typing.overload
    def __eq__(self, other: IssueType) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: IssueType) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class MapOrigin:
    """
    Members:
    
      NONE
    
      CIA402_DEFAULT
    
      EDS
    
      LOG_SDO
    """
    CIA402_DEFAULT: typing.ClassVar[MapOrigin]
    EDS: typing.ClassVar[MapOrigin]
    LOG_SDO: typing.ClassVar[MapOrigin]
    NONE: typing.ClassVar[MapOrigin]
    __members__: typing.ClassVar[dict[str, MapOrigin]]
    @typing.overload
    def __eq__(self, other: MapOrigin) -> bool:
        ...
    @typing.overload
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    @typing.overload
    def __ne__(self, other: MapOrigin) -> bool:
        ...
    @typing.overload
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Frame:
    @property
    def data(self) -> bytes:
        ...
    @property
    def dlc(self) -> int:
        ...
    @property
    def error(self) -> bool:
        ...
    @property
    def ext(self) -> bool:
        ...
    @property
    def fd(self) -> bool:
        ...
    @property
    def id(self) -> int:
        ...
    @property
    def iface(self) -> int:
        ...
    @property
    def line(self) -> int:
        ...
    @property
    def rtr(self) -> bool:
        ...
    @property
    def t(self) -> float:
        ...
class Record:
    @property
    def abort_code(self) -> int:
        ...
    @property
    def axis_state(self) -> AxisState:
        ...
    @property
    def controlword(self) -> int:
        ...
    @property
    def cw_axis(self) -> int:
        ...
    @property
    def cw_command(self) -> CwCommand:
        ...
    @property
    def emcy_code(self) -> int:
        ...
    @property
    def error_register(self) -> int:
        ...
    @property
    def has_controlword(self) -> bool:
        ...
    @property
    def has_issue(self) -> bool:
        ...
    @property
    def has_statusword(self) -> bool:
        ...
    @property
    def hb_state(self) -> int:
        ...
    @property
    def index(self) -> int:
        ...
    @property
    def kind(self) -> Kind:
        ...
    @property
    def map_ref(self) -> typing.Any:
        ...
    @property
    def nmt_cmd(self) -> int:
        ...
    @property
    def nmt_target(self) -> int:
        ...
    @property
    def node(self) -> int:
        ...
    @property
    def pdo_num(self) -> int:
        ...
    @property
    def sdo_expedited(self) -> bool:
        ...
    @property
    def sdo_index_known(self) -> bool:
        ...
    @property
    def sdo_size(self) -> int:
        ...
    @property
    def sdo_type(self) -> SdoType:
        ...
    @property
    def statusword(self) -> int:
        ...
    @property
    def sub(self) -> int:
        ...
    @property
    def sw_axis(self) -> int:
        ...
    @property
    def value(self) -> int:
        ...
    @property
    def value_len(self) -> int:
        ...
    @property
    def words_count(self) -> int:
        ...
class Issue:
    @property
    def axis(self) -> int:
        ...
    @property
    def code(self) -> int:
        ...
    @property
    def expected(self) -> float:
        ...
    @property
    def index(self) -> int:
        ...
    @property
    def node(self) -> int:
        ...
    @property
    def related_code(self) -> int:
        ...
    @property
    def related_row(self) -> typing.Any:
        ...
    @property
    def row(self) -> int:
        ...
    @property
    def severity(self) -> Severity:
        ...
    @property
    def sub(self) -> int:
        ...
    @property
    def t(self) -> float:
        ...
    @property
    def type(self) -> IssueType:
        ...
    @property
    def value(self) -> float:
        ...
class AxisWord:
    @property
    def axis(self) -> int:
        ...
    @property
    def command(self) -> CwCommand:
        ...
    @property
    def is_statusword(self) -> bool:
        ...
    @property
    def state(self) -> AxisState:
        ...
    @property
    def word(self) -> int:
        ...
class PdoMapEntry:
    def __init__(self, index: typing.SupportsInt | typing.SupportsIndex, sub: typing.SupportsInt | typing.SupportsIndex, bits: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __repr__(self) -> str:
        ...
    @property
    def bits(self) -> int:
        ...
    @property
    def index(self) -> int:
        ...
    @property
    def sub(self) -> int:
        ...
class PdoMapping:
    @property
    def entries(self) -> list[PdoMapEntry]:
        ...
    @property
    def node(self) -> int:
        ...
    @property
    def num(self) -> int:
        ...
    @property
    def origin(self) -> MapOrigin:
        ...
    @property
    def since_row(self) -> int:
        ...
    @property
    def tx(self) -> bool:
        ...
class PdoField:
    @property
    def bits(self) -> int:
        ...
    @property
    def complete(self) -> bool:
        ...
    @property
    def index(self) -> int:
        ...
    @property
    def raw(self) -> int:
        ...
    @property
    def sub(self) -> int:
        ...
class StatePoint:
    @property
    def row(self) -> int:
        ...
    @property
    def state(self) -> AxisState:
        ...
    @property
    def statusword(self) -> int:
        ...
    @property
    def t(self) -> float:
        ...
class NodeInfo:
    @property
    def axis_count(self) -> int:
        ...
    @property
    def axis_state(self) -> AxisState:
        ...
    @property
    def axis_states(self) -> list[AxisState]:
        ...
    @property
    def device_type(self) -> int:
        ...
    @property
    def device_type_known(self) -> bool:
        ...
    @property
    def drive_forced(self) -> bool:
        ...
    @property
    def emcy_count(self) -> int:
        ...
    @property
    def first_seen(self) -> float:
        ...
    @property
    def frame_count(self) -> int:
        ...
    @property
    def hb_count(self) -> int:
        ...
    @property
    def hb_period(self) -> float:
        ...
    @property
    def is_drive(self) -> bool:
        ...
    @property
    def kind_counts(self) -> dict:
        ...
    @property
    def last_hb_state(self) -> int:
        ...
    @property
    def last_seen(self) -> float:
        ...
    @property
    def node(self) -> int:
        ...
    @property
    def reboot_count(self) -> int:
        ...
    @property
    def sdo_abort_count(self) -> int:
        ...
class Options:
    auto_detect_drives: bool
    def __init__(self) -> None:
        ...
    @property
    def hb_gap_factor(self) -> float:
        ...
    @hb_gap_factor.setter
    def hb_gap_factor(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def sdo_timeout(self) -> float:
        ...
    @sdo_timeout.setter
    def sdo_timeout(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def state_timeout(self) -> float:
        ...
    @state_timeout.setter
    def state_timeout(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
class Trace:
    @staticmethod
    def from_bytes(data: bytes, options: Options = ...) -> Trace:
        ...
    @staticmethod
    def from_text(text: str, options: Options = ...) -> Trace:
        ...
    def __len__(self) -> int:
        ...
    def analyze(self) -> None:
        ...
    def axis_count(self, node: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def axis_timeline(self, node: typing.SupportsInt | typing.SupportsIndex, axis: typing.SupportsInt | typing.SupportsIndex = 0) -> list[StatePoint]:
        ...
    def axis_words(self, row: typing.SupportsInt | typing.SupportsIndex) -> list[AxisWord]:
        ...
    def clear_base_mappings(self) -> None:
        ...
    def clear_drive_override(self, node: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def filter(self, kinds: typing.Any = None, node: typing.SupportsInt | typing.SupportsIndex = -1, issues_only: bool = False, index: typing.SupportsInt | typing.SupportsIndex = -1) -> IndexList:
        ...
    def frame(self, row: typing.SupportsInt | typing.SupportsIndex) -> Frame:
        ...
    def mapping(self, ref: typing.SupportsInt | typing.SupportsIndex) -> PdoMapping:
        ...
    def pdo_fields(self, row: typing.SupportsInt | typing.SupportsIndex) -> list[PdoField]:
        ...
    def record(self, row: typing.SupportsInt | typing.SupportsIndex) -> Record:
        ...
    def set_base_mapping(self, node: typing.SupportsInt | typing.SupportsIndex, tx: bool, num: typing.SupportsInt | typing.SupportsIndex, entries: collections.abc.Sequence[PdoMapEntry]) -> None:
        ...
    def set_drive(self, node: typing.SupportsInt | typing.SupportsIndex, is_drive: bool) -> None:
        ...
    @property
    def duration(self) -> float:
        ...
    @property
    def format(self) -> str:
        ...
    @property
    def has_timestamps(self) -> bool:
        ...
    @property
    def interfaces(self) -> list[str]:
        ...
    @property
    def issues(self) -> list[Issue]:
        ...
    @property
    def kind_counts(self) -> dict:
        ...
    @property
    def mapping_count(self) -> int:
        ...
    @property
    def nodes(self) -> list[NodeInfo]:
        ...
    @property
    def options(self) -> Options:
        ...
    @property
    def skipped_lines(self) -> int:
        ...
    @property
    def t0(self) -> float:
        ...
class LiveDecoder:
    def __init__(self, options: Options = ...) -> None:
        ...
    def axis_count(self, node: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def axis_timeline(self, node: typing.SupportsInt | typing.SupportsIndex, axis: typing.SupportsInt | typing.SupportsIndex = 0) -> list[StatePoint]:
        ...
    def feed(self, t: typing.SupportsFloat | typing.SupportsIndex, id: typing.SupportsInt | typing.SupportsIndex, data: bytes = b'', is_extended: bool = False, is_remote: bool = False, is_error: bool = False, is_fd: bool = False) -> int:
        ...
    def issues_from(self, start: typing.SupportsInt | typing.SupportsIndex) -> list[Issue]:
        ...
    def last_frame(self) -> Frame:
        ...
    def last_pdo_fields(self) -> list[PdoField]:
        ...
    def last_record(self) -> Record:
        ...
    def last_words(self) -> list[AxisWord]:
        ...
    def mapping(self, ref: typing.SupportsInt | typing.SupportsIndex) -> PdoMapping:
        ...
    def reset(self) -> None:
        ...
    def set_base_mapping(self, node: typing.SupportsInt | typing.SupportsIndex, tx: bool, num: typing.SupportsInt | typing.SupportsIndex, entries: collections.abc.Sequence[PdoMapEntry]) -> None:
        ...
    def set_drive(self, node: typing.SupportsInt | typing.SupportsIndex, is_drive: bool) -> None:
        ...
    def tick(self, t: typing.SupportsFloat | typing.SupportsIndex) -> int:
        ...
    @property
    def frame_count(self) -> int:
        ...
    @property
    def issue_count(self) -> int:
        ...
    @property
    def issues(self) -> list[Issue]:
        ...
    @property
    def nodes(self) -> list[NodeInfo]:
        ...
    @property
    def options(self) -> Options:
        ...
    @property
    def t0(self) -> float:
        ...
def decode_controlword(controlword: typing.SupportsInt | typing.SupportsIndex, previous: typing.SupportsInt | typing.SupportsIndex = 0) -> CwCommand:
    ...
def decode_statusword(statusword: typing.SupportsInt | typing.SupportsIndex) -> AxisState:
    ...

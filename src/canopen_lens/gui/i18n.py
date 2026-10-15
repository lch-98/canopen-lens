"""UI strings for the GUI (Korean / English)."""

from __future__ import annotations

_STRINGS: dict[str, tuple[str, str]] = {
    "app_title": ("CANopen Lens", "CANopen Lens"),
    "open": ("로그 열기", "Open log"),
    "open_sample": ("예제 로그 열어보기", "Try the sample log"),
    "drop_title": ("candump 로그 파일을 여기에 끌어다 놓으세요", "Drop a candump log file here"),
    "drop_sub": ("또는 아래 버튼으로 파일을 고르세요. `candump -l can0` 로 만든 .log 파일과\n"
                 "`candump can0` 화면 출력을 저장한 텍스트 파일을 모두 읽을 수 있습니다.",
                 "or pick a file below. Both `candump -l can0` .log files and saved\n"
                 "`candump can0` console output are supported."),
    "loading": ("로그를 읽는 중…", "Reading log…"),
    "load_failed": ("로그를 열지 못했습니다", "Could not open the log"),
    "no_frames": ("candump 형식의 CAN 프레임을 찾지 못했습니다. 파일 형식을 확인하세요.",
                  "No candump frames found. Please check the file format."),
    "language": ("English", "한국어"),
    "frames": ("프레임", "frames"),
    "duration": ("길이", "duration"),
    "errors": ("오류", "Errors"),
    "warnings": ("경고", "Warnings"),
    "nodes": ("노드", "Nodes"),
    "no_issues": ("발견된 문제가 없습니다 👍", "No problems found 👍"),
    "tab_issues": ("진단 결과", "Diagnosis"),
    "tab_nodes": ("노드", "Nodes"),
    "tab_frames": ("전체 프레임", "All frames"),
    "tab_timeline": ("상태 타임라인", "State timeline"),
    "col_no": ("#", "#"),
    "col_time": ("시간(s)", "Time (s)"),
    "col_node": ("노드", "Node"),
    "col_kind": ("종류", "Type"),
    "col_id": ("COB-ID", "COB-ID"),
    "col_data": ("데이터", "Data"),
    "col_meaning": ("해석", "Meaning"),
    "filter_all_nodes": ("모든 노드", "All nodes"),
    "filter_issues": ("문제 있는 프레임만", "Only frames with problems"),
    "filter_index": ("오브젝트 (예: 6041)", "Object (e.g. 6041)"),
    "filter_types": ("종류", "Types"),
    "shown": ("표시", "shown"),
    "details": ("자세히", "Details"),
    "select_frame": ("프레임이나 진단 항목을 선택하면 여기에 쉬운 설명이 나옵니다.",
                     "Select a frame or a finding to see a plain-language explanation here."),
    "go_to_frame": ("해당 프레임으로 이동", "Go to frame"),
    "go_to_related": ("관련 프레임으로 이동", "Go to related frame"),
    "what_to_check": ("확인할 것", "What to check"),
    "node_drive": ("CiA 402 드라이브", "CiA 402 drive"),
    "node_generic": ("일반 노드", "Generic node"),
    "node_treat_drive": ("CiA 402 드라이브로 해석", "Decode as CiA 402 drive"),
    "node_eds": ("EDS 지정…", "Assign EDS…"),
    "node_eds_remove": ("EDS 해제", "Remove EDS"),
    "node_eds_none": ("EDS 없음", "No EDS"),
    "node_nmt": ("NMT 상태", "NMT state"),
    "node_axis": ("축 상태", "Axis state"),
    "node_hb": ("하트비트 주기", "Heartbeat period"),
    "node_counts": ("프레임 수", "Frames"),
    "node_problems": ("문제", "Problems"),
    "node_device_type": ("장치 종류(0x1000)", "Device type (0x1000)"),
    "node_none_hb": ("하트비트 없음", "no heartbeat"),
    "eds_filter": ("EDS / DCF 파일 (*.eds *.dcf *.EDS *.DCF);;모든 파일 (*)", "EDS / DCF files (*.eds *.dcf *.EDS *.DCF);;All files (*)"),
    "log_filter": ("candump 로그 (*.log *.txt *.candump);;모든 파일 (*)", "candump logs (*.log *.txt *.candump);;All files (*)"),
    "timeline_axis": ("축 상태", "Axis state"),
    "timeline_nmt": ("NMT", "NMT"),
    "timeline_empty": ("타임라인으로 보여줄 하트비트나 드라이브 상태가 없습니다.", "Nothing to draw: no heartbeats or drive states found."),
    "timeline_hint": ("막대를 클릭하면 해당 시점의 프레임으로 이동합니다. 빨간 삼각형은 진단 항목입니다.",
                      "Click a bar to jump to that moment. Red triangles mark findings."),
    "no_hb_period": ("하트비트 끊김", "no heartbeat"),
    "kind_help_title": ("이 종류는?", "About this type"),
    "settings": ("설정", "Settings"),
    "reload": ("다시 분석", "Re-analyze"),
}


class Tr:
    def __init__(self, lang: str = "ko"):
        self.lang = lang

    def __call__(self, key: str) -> str:
        ko, en = _STRINGS[key]
        return ko if self.lang == "ko" else en

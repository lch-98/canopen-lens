"""UI strings for the GUI (Korean / English)."""

from __future__ import annotations

_STRINGS: dict[str, tuple[str, str]] = {
    "app_title": ("CANopen Lens", "CANopen Lens"),
    "tab_overview": ("요약", "Overview"),
    "verdict_ok": ("문제 없음", "All good"),
    "verdict_warning": ("주의", "Warnings"),
    "verdict_error": ("확인 필요", "Needs attention"),
    "ov_nodes": ("장치(노드)별 상태", "Status of each device (node)"),
    "ov_todo": ("먼저 확인할 것", "Check these first"),
    "ov_todo_hint": ("중요한 순서대로 정리했습니다. 같은 문제가 여러 번 나온 경우 한 번만 보여줍니다.",
                     "Most important first. Repeated identical problems are shown once."),
    "ov_info": ("참고 정보", "For your information"),
    "ov_none": ("확인할 문제가 없습니다. 모든 장치가 정상적으로 통신했습니다.",
                "Nothing to check. Every device communicated normally."),
    "what": ("무슨 일이 있었나요?", "What happened?"),
    "why": ("왜 중요한가요?", "Why does it matter?"),
    "steps": ("이렇게 확인해 보세요", "How to check"),
    "times": ("{}번 발생 ({:.2f}초 ~ {:.2f}초)", "{} times ({:.2f} s – {:.2f} s)"),
    "time_once": ("{:.2f}초", "at {:.2f} s"),
    "show_frame": ("이 시점의 메시지 보기", "Show the messages"),
    "show_timeline": ("타임라인에서 보기", "Show on timeline"),
    "occurrences": ("발생한 곳", "Occurrences"),
    "more_occ": ("외 {}건", "and {} more"),
    "plain": ("쉽게 말하면", "In plain words"),
    "raw_cols": ("원본 데이터 보기 (COB-ID, 바이트)", "Show raw data (COB-ID, bytes)"),
    "export": ("결과 저장", "Save results"),
    "export_txt": ("읽기 쉬운 보고서 (.txt)", "Readable report (.txt)"),
    "export_json": ("진단 결과 JSON (.json)", "Findings as JSON (.json)"),
    "export_csv": ("해석한 전체 메시지 표 (.csv, 엑셀)", "All decoded messages (.csv, Excel)"),
    "export_done": ("저장했습니다: {}", "Saved: {}"),
    "glossary": ("용어 설명", "Glossary"),
    "close": ("닫기", "Close"),
    "glossary_title": ("CANopen 용어를 쉽게 설명합니다", "CANopen terms in plain words"),
    "help": ("사용 방법", "How to use"),
    "help_html": (
        "<h3>CANopen Lens 사용 방법</h3>"
        "<p><b>1. 로그 저장하기</b><br>리눅스나 라즈베리파이에서 <code>candump -l can0</code>을 실행하고, 문제가 생기는 동작을 한 뒤 Ctrl+C로 멈춥니다. "
        "<code>candump-날짜.log</code> 파일이 생깁니다.</p>"
        "<p><b>2. 열기</b><br>파일을 창에 끌어다 놓거나 <b>로그 열기</b>를 누릅니다.</p>"
        "<p><b>3. 요약부터 보기</b><br><b>요약</b> 화면에 전체 판정, 장치별 상태, 먼저 확인할 문제가 나옵니다. "
        "각 문제에는 무슨 일이 있었는지, 왜 중요한지, 무엇을 확인하면 되는지가 적혀 있습니다.</p>"
        "<p><b>4. 자세히 보기</b><br><b>이 시점의 메시지 보기</b>를 누르면 그 순간 주고받은 메시지가 한 줄씩 쉬운 말로 풀려 있습니다. "
        "<b>상태 타임라인</b>에서는 각 장치와 모터 축의 상태가 시간에 따라 어떻게 바뀌었는지 색으로 볼 수 있습니다.</p>"
        "<p><b>5. 더 정확하게</b><br>장치 제조사의 EDS 파일이 있으면 <b>노드</b> 탭에서 지정하세요. 값의 이름과 단위가 정확해집니다.</p>"
        "<p>모르는 용어는 <b>용어 설명</b> 버튼을 누르면 볼 수 있습니다.</p>",
        "<h3>How to use CANopen Lens</h3>"
        "<p><b>1. Record a log</b><br>On Linux or a Raspberry Pi run <code>candump -l can0</code>, reproduce the problem, then stop with Ctrl+C. "
        "A <code>candump-DATE.log</code> file is created.</p>"
        "<p><b>2. Open it</b><br>Drop the file on the window or click <b>Open log</b>.</p>"
        "<p><b>3. Start with the overview</b><br>The <b>Overview</b> shows the verdict, the status of each device and the problems to check first, "
        "each with what happened, why it matters and what to check.</p>"
        "<p><b>4. Dig deeper</b><br><b>Show the messages</b> jumps to the messages around a problem, each explained in plain words. "
        "The <b>State timeline</b> shows how each device and motor axis changed state over time.</p>"
        "<p><b>5. Be more precise</b><br>If you have the vendor's EDS file, assign it in the <b>Nodes</b> tab for exact names and units.</p>"
        "<p>Unknown words are explained under <b>Glossary</b>.</p>"),
    "welcome_steps": (
        "① 장비에서 <code>candump -l can0</code>으로 로그를 저장하세요 &nbsp;→&nbsp; ② 파일을 여기에 놓으세요 &nbsp;→&nbsp; ③ 요약 화면에서 문제와 해결 방법을 확인하세요",
        "① Record with <code>candump -l can0</code> &nbsp;→&nbsp; ② drop the file here &nbsp;→&nbsp; ③ read the overview for problems and fixes"),
    "chip_pdo": ("실시간 데이터", "Process data"),
    "chip_sdo": ("설정 읽기·쓰기", "Settings"),
    "chip_emcy": ("비상 알림", "Emergency"),
    "chip_nmt": ("상태 명령", "Commands"),
    "chip_hb": ("생존 신호", "Heartbeat"),
    "chip_sync": ("동기 신호", "Sync"),
    "chip_etc": ("기타", "Other"),
    "errors_kinds": ("오류 항목", "Errors"),
    "warnings_kinds": ("경고 항목", "Warnings"),
    "frame_findings": ("이 메시지에서 발견된 문제", "Problems found in this message"),

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
    "timeline_axis_n": ("축 {}", "Axis {}"),
    "timeline_nmt": ("NMT", "NMT"),
    "node_axis_n": ("축 {} 상태", "Axis {} state"),
    "node_axes": ("축 수", "Axes"),
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

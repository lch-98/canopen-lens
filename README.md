# CANopen Lens

**Open a `candump` log and see, in plain language, what every CANopen frame means and what went wrong.**

CANopen Lens is a desktop viewer for people who are new to CANopen (and a fast triage tool for people who are not).
Drop in a log recorded with `candump` and it will:

- **Decode every frame** — NMT, SYNC, EMCY, PDO, SDO (expedited, segmented, abort), heartbeat — into a one-line explanation.
- **Track CiA 402 drives** — decode controlword commands and statusword states and draw each axis' state machine on a timeline.
- **Use your EDS files** — object names, data types and the PDO mapping come from the EDS; PDO remapping done over SDO inside the log is followed automatically.
- **Diagnose problems** — SDO aborts (with the reason and what to check), SDO requests without an answer, EMCY codes, heartbeat gaps and lost nodes, unexpected reboots, drive faults and failed enable / fault-reset sequences, bus error frames.

The UI is available in **Korean and English** (one click to switch).

The decoding core is written in C++ (pybind11), so a log with two million frames loads in about a second on a desktop PC; the GUI is PySide6.

## Install

```bash
pip install "canopen-lens[gui]"
```

Prebuilt wheels are provided for Linux x86_64, Linux aarch64 (Raspberry Pi 4/5 with a 64-bit OS) and Windows x64, Python 3.9–3.14.
Leave out `[gui]` if you only want the Python API / command line report.

## Use

### GUI

```bash
canopen-lens                 # opens the window — drag a log file onto it
canopen-lens robot.log       # opens a log directly
canopen-lens --en robot.log  # start in English
```

No log at hand? Click **Try the sample log**: it contains two CiA 402 drives and an I/O module with an SDO abort,
an over-current fault, a failed fault reset, a heartbeat gap and a node that disappears.

### Recording a log

```bash
candump -l can0              # writes candump-YYYY-MM-DD_HHMMSS.log  (recommended)
candump -t a can0 > log.txt  # console output with absolute timestamps also works
```

### Command line report

```bash
canopen-lens report robot.log --lang en -v
canopen-lens report robot.log --eds 1=drive.eds --eds 2=drive.eds --min-severity warning
```

`--fail-on-error` makes the command exit with status 1 when errors are found, which is handy in test benches.

### Python API

```python
from canopen_lens import open_log, Kind

log = open_log("robot.log", eds={1: "drive.eds"})
for issue in log.issues:
    title, what_to_check = log.issue_text(issue, lang="en")
    print(f"{issue.t:8.3f}s  {title}")

for row in log.trace.filter(kinds=[Kind.EMCY]):
    print(log.summary(int(row), "en"))

for p in log.trace.axis_timeline(1):      # CiA 402 state changes of node 1
    print(p.t, p.state)
```

## How decoding works

| Step | Where | Notes |
|---|---|---|
| Parse `candump` text | C++ | `-l` log format and console format, with or without timestamps (`-t a/z/d`), RTR, CAN FD, error frames |
| Classify by COB-ID | C++ | CiA 301 predefined connection set |
| Follow SDO transfers | C++ | Values, segmented transfers, abort codes, missing answers |
| Track PDO mapping | C++ | EDS → mapping written over SDO in the log → CiA 402 default mapping |
| CiA 402 state machine | C++ | Nodes count as drives when the log or EDS shows it (device type 402, access to `0x6000–0x67FF`, statusword/controlword in a PDO); this can be overridden per node |
| Explanations | Python | All wording lives in `describe.py` (Korean/English) |

## Limitations (v0.1)

- Only `candump` input. PCAN `.trc` is planned next.
- PDOs are assumed to use the default COB-IDs (`0x180 + node`, …); custom COB-IDs set through `0x1400/0x1800` are not followed yet.
- Multi-axis devices (CiA 402-2, axis offset `0x800`) are decoded as a single axis.
- Diagnosis is heuristic. It tells you where to look; the device manual has the final word.

## Development

```bash
git clone https://github.com/lch-98/canopen-lens
cd canopen-lens
pip install -e ".[gui,test]"
pytest
python tests/make_sample.py   # regenerate the sample log
```

## License

MIT

---

## 한국어 소개

`candump` 로그 파일을 끌어다 놓으면 CANopen 프레임 하나하나가 **무슨 뜻인지**, **어디서 문제가 생겼는지**를 쉬운 말로 보여주는 데스크톱 프로그램입니다.

- 모든 프레임(NMT, SYNC, EMCY, PDO, SDO, 하트비트)을 한 줄 설명으로 해석합니다.
- CiA 402 드라이브의 컨트롤워드 명령과 스테이터스워드 상태를 해석하고, 축 상태 변화를 타임라인으로 보여줍니다.
- EDS 파일을 지정하면 오브젝트 이름·데이터 타입·PDO 매핑을 그대로 사용하고, 로그 안에서 SDO로 바꾼 매핑도 자동으로 따라갑니다.
- SDO 실패 원인과 확인할 것, 응답 없는 SDO, EMCY 코드, 하트비트 끊김, 예상치 못한 재부팅, 드라이브 폴트, Enable·폴트 리셋 실패, 버스 에러 프레임을 자동으로 찾아 줍니다.

```bash
pip install "canopen-lens[gui]"
canopen-lens            # 창을 열고 로그 파일을 끌어다 놓기
```

로그는 `candump -l can0`으로 저장하는 것을 권장합니다. 화면 상단의 **English / 한국어** 버튼으로 언어를 바꿀 수 있습니다.

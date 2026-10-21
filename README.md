# CANopen Lens

**Give it a `candump` log and it tells you, in plain words, what happened on your CANopen network and what to check — as a desktop app and as a Python library.**

[한국어 설명서 (Korean)](README.ko.md)

```bash
pip install "canopen-lens[gui]"    # the desktop app (recommended)
canopen-lens                       # opens the window
```

> `pip install canopen-lens` on its own installs only the Python library and the `canopen-lens report` command line.
> 한국어: 창(GUI)으로 쓰려면 위처럼 `pip install "canopen-lens[gui]"`로 설치하세요. `[gui]` 없이 설치하면 라이브러리와 명령줄 기능만 들어갑니다.

![Overview screen](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/overview_en.png)

Made so that someone new to CANopen can find a root cause from a single log, without knowing CAN IDs or bytes:

- **A verdict** – "Problems found – 3 kinds of error, 1 kind of warning"
- **The status of every device** – "Node 5 (CiA 402 drive): had problems but recovered · Axis 2: faulted 1 time but recovered to Enabled"
- **What to check first** – every problem explained as *What happened? / Why does it matter? / How to check*

The UI and all explanations are available in **English and Korean**.

---

## Install

### 1. Download the app (no Python needed)

Get the file for your computer from [Releases](https://github.com/lch-98/canopen-lens/releases), unpack it and run it.

| System | File | Run |
|---|---|---|
| Windows 10/11 | `CANopenLens-…-windows-x64.zip` | double-click `CANopenLens\CANopenLens.exe` |
| Linux (Ubuntu 22.04+ and similar) | `CANopenLens-…-linux-x86_64.tar.gz` | `CANopenLens/CANopenLens` |
| Raspberry Pi 4/5 (64-bit OS) | `CANopenLens-…-linux-aarch64.tar.gz` | `CANopenLens/CANopenLens` |

### 2. pip (Python 3.9+)

```bash
pip install "canopen-lens[gui]"     # app + library
pip install canopen-lens            # library and command line only (servers, headless Pi)
```

Prebuilt wheels are published for Windows x64, Linux x86_64 and Linux aarch64, so no C++ compiler is needed.
Run `canopen-lens` to open the window.

---

## Five-minute guide

1. **Record a log** on the Linux PC or Raspberry Pi attached to the machine: `candump -l can0`, reproduce the problem, stop with `Ctrl+C`. (Saved console output such as `candump -t a can0 > log.txt` works too.)
2. **Open it** – drop the file on the window. No log yet? Pick an example under **Try the sample log**: a mixed network with many problems, or a two-wheel AMR (ros2_canopen master + STM32 two-axis drive) from boot-time PDO configuration to an E-stop and recovery.
3. **Read the overview** – the colour at the top is the verdict; below it are the status of each device and the problems to check first, most important first. Repeats of the same problem are shown once with a count.
4. **Dig deeper** – **Show the messages** jumps to the moment of a problem, with every message explained in one line.
5. **Live monitor** – the **Live monitor** tab connects to a USB-CAN adapter or SocketCAN and shows messages and problems as they happen (`socketcan`, `pcan`, `kvaser`, `ixxat`, `vector`, `slcan`, `gs_usb`). No hardware? Pick **Demo** to replay the sample log in real time. Everything received is recorded and can be saved as a candump file or opened in log analysis with one click.
6. **State timeline** – how each device and motor axis changed state over time. Red is a fault, a gap means the device went silent. Click a bar to jump there.

Unknown words are explained under **Glossary**. **Save results** writes a readable report (.txt), JSON or an Excel-friendly CSV.

---

## What it finds

| Finding | In plain words |
|---|---|
| SDO failed | The device refused a setting; the abort code is explained together with where to look |
| No SDO answer | The device did not reply; check node-ID, power and wiring in that order |
| Emergency (EMCY) | The device reported an error; the code is turned into readable text |
| Heartbeat gap / stopped | The device went quiet for longer than its normal period, or never came back |
| Unexpected restart | The device rebooted without a reset command (power dip, watchdog, …) |
| Drive fault | A motor drive stopped with a fault; the EMCY at the same moment is linked as the likely cause |
| Enable did not work | Enable operation was sent but the drive never turned on (wrong order, motor power, STO) |
| Fault reset did not work | A reset was sent but the fault stayed (its cause is still there) |
| Quick stop | The drive entered quick stop |
| CAN bus errors | Corrupted traffic on the wires (termination, bit rate, cabling) |

Verdicts: **✔ OK** – nothing went wrong · **▲ recovered** – something went wrong but was fine again at the end of the log · **✖ needs attention** – still wrong at the end (fault, silent device) or a setting was not applied.

---

## How a log is analysed

```
(1760500002.000250) can0 185#3702180220030000
 └ time               └ port └ ID └ data bytes
```

1. **Who sent what.** CANopen IDs are "message type + node-ID": `0x185` = `0x180` (TPDO1, real-time data from a device) + node 5.
2. **Where the values are.** Which values sit where inside a PDO (the PDO mapping) is taken from, in this order: SDO configuration found earlier in the log → the EDS you attach → the CiA 402 default (assumed, axis 1 only).
3. **Values into words.** Here: axis 1 statusword + axis 2 statusword + axis 1 actual velocity →
   `TPDO1: Axis 1 state: Enabled (SW 0x0237), Axis 2 state: Fault (SW 0x0218), Axis 1 Velocity actual value=800`.
4. **Following the story.** SDO questions are paired with answers; each node's heartbeat period is learned and late heartbeats are flagged; every CiA 402 axis gets its own state machine, commands are checked against the state that follows, and EMCY messages around a fault are linked to it.
5. **Grouping.** Identical findings are collapsed and sorted by importance.

Clicking a message shows a **byte-by-byte** breakdown. For `582#4300100092010200`: `43` = command byte (binary `010 0 00 1 1`: read reply, value inside the frame, 4 bytes), `00 10` = index `0x1000` read back to front (CANopen sends the least significant byte first), `00` = sub-index, `92 01 02 00` = `0x00020192`: profile `0x0192` = 402 (drive), additional info `0x0002` = servo drive.

**Not CANopen?** `candump` records every frame regardless of protocol. If a log has no heartbeat/NMT/SDO/EMCY/SYNC at all, or mostly 29-bit IDs (J1939, vendor protocols), the overview says so instead of pretending, and shows a protocol-independent **traffic by ID** table (count, period, largest gap, DLC).

Decoding runs in C++; a two-million-frame log opens in one to two seconds on an ordinary PC, and only the rows on screen are turned into text, so large logs stay responsive.

---

## Using it from Python

```python
from canopen_lens import open_log, Kind

log = open_log("robot.log", eds={1: "drive.eds"})   # EDS optional

print(log.report("en"))                  # the whole readable report

h = log.health("en")                     # verdict, per-node status, grouped findings
for group in log.grouped_issues():
    ex = log.explain(group.first, "en")
    print(ex.title, group.count, ex.steps)

df = log.to_dataframe("en")              # pandas (pip install pandas)
log.to_csv("frames.csv")                 # UTF-8 with BOM, opens cleanly in Excel
log.to_json("result.json")

for row in log.trace.filter(kinds=[Kind.EMCY], node=2):
    print(log.summary(int(row), "en"))
for p in log.trace.axis_timeline(5, axis=1):  # node 5, axis 2
    print(p.t, p.state)
```

### Live bus (python-can)

```python
import can
from canopen_lens import LiveDecoder

dec = LiveDecoder(eds={1: "drive.eds"})
with can.Bus(interface="socketcan", channel="can0") as bus:
    dec.run(bus, lang="en")              # prints findings the moment they happen
```

Or push frames yourself with `dec.feed(t, can_id, data)`. Only the newest frame is kept, so memory stays flat however long it runs.

### Command line / CI

```bash
canopen-lens report robot.log                          # readable report
canopen-lens report robot.log --brief --fail-on-error  # exit code 1 on errors
canopen-lens report robot.log --format json -o result.json
canopen-lens report robot.log --format csv -o frames.csv
canopen-lens live --channel can0 -v                    # pip install "canopen-lens[live]"
```

Type hints are included for IDE completion.

---

## Limitations

- Log files must be in `candump` format; PCAN `.trc` is next (the live monitor can use PCAN adapters directly).
- PDOs are assumed to use the default COB-IDs (`0x180 + node`, …); COB-IDs changed through `0x1400`/`0x1800` are not followed yet.
- Axes 2–8 of multi-axis drives are decoded when the EDS or the log provides their PDO mapping.
- Findings are guidance based on what the log shows; the device manual has the final word.
- The Python API may still change before 1.0.

## Development

```bash
git clone https://github.com/lch-98/canopen-lens
cd canopen-lens
pip install -e ".[gui,test,pandas,live]"
pytest
python tests/make_sample.py      # regenerate the mixed-network example
python tests/make_amr_sample.py  # regenerate the two-wheel AMR example
```

Releases: see [RELEASING.md](RELEASING.md).

## License

MIT

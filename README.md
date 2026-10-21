# CANopen Lens

**Give it a `candump` log and it tells you, in plain words, what happened on your CANopen network and what to check — as a desktop app and as a Python library.**

[한국어 설명서 (Korean)](README.ko.md)

```bash
pip install "canopen-lens[gui]"    # the desktop app (recommended)
canopen-lens                       # opens the window
```

> `pip install canopen-lens` on its own installs only the Python library and the command line (`canopen-lens your.log`).
> 한국어: 창(GUI)으로 쓰려면 위처럼 `pip install "canopen-lens[gui]"`로 설치하세요. `[gui]` 없이 설치하면 라이브러리와 명령줄 기능만 들어갑니다.

![Overview screen](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/overview_en.png)

Made so that someone new to CANopen can find a root cause from a single log, without knowing CAN IDs or bytes:

- **A one-line verdict** – "Needs attention · unresolved 3 · recovered 2 · warnings 2"
- **A list of problems** – messages that belong to one event (fault, EMCY, failed resets …) become one row, e.g. "Node 2 · Stopped: over current → recovered on reset #2"
- **Details on demand** – click a row for *What happened / Check first / Why it matters*

The app and the command line both speak **English and Korean**.

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
2. **Open it** – drop the file on the window or press **Open log**. No log yet? Pick one under **Examples**: a mixed network with many problems, or a two-wheel AMR (ros2_canopen master + STM32 two-axis drive) from boot-time PDO configuration to an E-stop and recovery.
3. **Read the summary** – the card at the top is the verdict, the table below is the list of problems. **Unresolved** (red, still wrong at the end of the log) comes first, then **Recovered** (teal, went wrong but came back). **Warnings** (amber) are folded away until you open them. Every device's state is listed on the right.
4. **Dig deeper** – click a row and the details open on the right: what happened in time order and three things to check first. **Show messages at this moment** jumps to the **Messages** page, with every message explained in one line. To attach an EDS or decode a device as a CiA 402 drive, use the **⋯** button next to it in the device list.
5. **Live** – the **Live** page connects to a USB-CAN adapter or SocketCAN and shows messages and problems as they happen (`socketcan`, `pcan`, `kvaser`, `ixxat`, `vector`, `slcan`, `gs_usb`). No hardware? Pick **Demo** to replay the sample log in real time. Everything received is recorded and can be saved as a candump file or opened in log analysis with one click.
6. **Timeline** – how each device and motor axis changed state over time. Red is a fault, a gap means the device went silent. Click a bar to jump there; Ctrl+wheel or dragging over a range zooms in on short events.

Unknown words are explained under **Glossary**. **Save results** writes a readable report (.txt), JSON or an Excel-friendly CSV.

![Problem details](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/detail_en.png)

---

## Command line

The same summary works over SSH, on a server or on a headless Raspberry Pi. Give it a log file:

```bash
canopen-lens examples              # copy the two example logs into this folder
canopen-lens sample_cia402.log     # summary
```

```
✖ Needs attention   unresolved 3  recovered 2  warnings 2  OK 1
  sample_cia402.log · 6.0 s · 5,304 messages · 5 nodes

Unresolved
   1  Node 4           No answer — the device seems to be missing                0.27 s
   2  Node 3           Went silent and never came back                           5.41 s
   3  Node 2           A setting was not applied                                 0.26 s

Recovered
   4  Node 5 · axis 2  Stopped: motor blocked → recovered after a reset          1.99 s
   5  Node 2           Stopped: continuous over current → recovered on reset #2  2.99 s

Warnings  Node 3 silent 0.7 s · 1 CAN bus error(s)
OK        Node 1

Details       canopen-lens sample_cia402.log -d 1
Save          canopen-lens sample_cia402.log -s result.csv
```

The last lines are the next command to type. Pass a number to `-d` to see that problem in detail:

```
$ canopen-lens sample_cia402.log -d 4
4  Recovered  Node 5 · axis 2 · Stopped: motor blocked → recovered after a reset
   Cause: Motor blocked (EMCY 0x7121)

   What happened
   1.990 s  Fault — motor torque switched off
   1.990 s  Cause reported: Motor blocked · EMCY 0x7121
   2.490 s  Fault cleared
   2.690 s  Running again

   Check first
   1. Look up 0x7121 in the device manual's error table
   2. Read the drive error code (0x683F) for the exact cause
   3. Remove the cause, then fault reset → 0x06 → 0x07 → 0x0F

   Why it matters  A faulted drive turns motor torque off and ignores motion commands until the fault is reset.
   Messages        #1512 #1515 #1988 #1993 #2179
```

| Command | What it does |
|---|---|
| `canopen-lens robot.log` | summary |
| `canopen-lens robot.log -d 1` | problem 1 in detail (`-d 1,4` and `-d all` work too) |
| `canopen-lens robot.log -s result.txt` | save; the extension picks the format: `.txt` report · `.csv` messages (Excel) · `.json` findings |
| `canopen-lens robot.log --eds 1=drive.eds` | attach an EDS to node 1 (repeat for more nodes) |
| `canopen-lens robot.log --check` | exit status 1 if a problem is unresolved (test benches, CI) |
| `canopen-lens live can0` | watch a bus live (`pip install "canopen-lens[live]"`; options: `canopen-lens live -h`) |
| `canopen-lens` | open the window |

The language follows the computer's setting; use `--lang en` / `--lang ko` or the `CANOPEN_LENS_LANG` environment variable to change it. `--no-color` (or `NO_COLOR=1`) turns colours off.

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

Every problem ends up in one of three states: **Unresolved** – still wrong at the end of the log (fault, silent device) or a setting was not applied · **Recovered** – something went wrong but was fine again at the end · **Warning** – nothing stopped, but it can become a problem if it keeps happening (late heartbeats, CAN bus errors). The verdict follows from them: **✖ Needs attention** if anything is unresolved, **▲ Problems occurred, all recovered** if every problem recovered, **▲ No real problems** if there are only warnings, **✔ No problems found** otherwise.

A drive that stops leaves several messages behind: the fault, the EMCY at the same moment, failed resets, the successful reset, running again. These are grouped into **one incident** (fault and EMCY on the same node within 0.1 s; resets after it are numbered), so one event is not shown as five problems.

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

ov = log.overview("en")                  # the same summary as the app and the command line
print(ov.headline, ov.counts)            # "Needs attention", {"open": 3, "recovered": 2, …}
for inc in ov.incidents:                 # grouped incidents, most important first
    print(inc.number, inc.status, inc.where, inc.title)

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

### Test benches / CI

```bash
canopen-lens robot.log --check -s result.json   # exit status 1 if a problem is unresolved, findings as JSON
```

`summary`, `incidents` and `devices` in `result.json` hold the same verdict and problem list as the app.
The pre-0.5 `canopen-lens report …` command still works.

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

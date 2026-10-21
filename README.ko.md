# CANopen Lens

**`candump` 로그를 넣으면, CANopen 통신에서 무슨 일이 있었는지와 무엇을 확인해야 하는지를 쉬운 말로 알려주는 프로그램이자 Python 라이브러리입니다.**

[English README](README.md)

```bash
pip install "canopen-lens[gui]"    # 창(GUI)으로 쓰는 프로그램 (권장)
canopen-lens                       # 창 열기
```

> `[gui]` 없이 `pip install canopen-lens`만 하면 Python 라이브러리와 명령줄(`canopen-lens 로그.log`)만 설치됩니다.
> 이미 그렇게 설치했다면 위 명령을 한 번 더 실행하면 됩니다.

![요약 화면](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/overview_ko.png)

CANopen을 처음 다루는 사람도 로그 하나로 원인을 찾을 수 있게 만들었습니다.
CAN ID나 바이트를 몰라도 됩니다. 프로그램이 이렇게 정리해 줍니다.

- **한 줄 판정** – "확인이 필요합니다 · 해결 안 됨 3 · 회복 2 · 경고 2"
- **문제 목록** – 같은 사건에서 나온 메시지(폴트, EMCY, 리셋 실패…)를 한 줄로 묶습니다. 예: "노드 2 · 과전류로 멈춤 → 두 번째 리셋에서 회복"
- **자세히 보기** – 한 줄을 누르면 *무슨 일이 있었나요 / 먼저 확인할 것 / 왜 중요한가요*가 나옵니다

창(GUI)과 명령줄 모두 **한국어와 영어**를 지원합니다.

---

## 설치

### 1. 앱 내려받기 (Python 필요 없음)

[Releases](https://github.com/lch-98/canopen-lens/releases) 페이지에서 내 컴퓨터에 맞는 파일을 받아 압축을 풀고 실행합니다.

| 운영체제 | 파일 | 실행 |
|---|---|---|
| Windows 10/11 | `CANopenLens-…-windows-x64.zip` | `CANopenLens\CANopenLens.exe` 더블클릭 |
| Linux (Ubuntu 22.04 이상 등) | `CANopenLens-…-linux-x86_64.tar.gz` | `CANopenLens/CANopenLens` |
| 라즈베리파이 4/5 (64비트 OS) | `CANopenLens-…-linux-aarch64.tar.gz` | `CANopenLens/CANopenLens` |

### 2. pip으로 설치 (Python 3.9 이상)

```bash
pip install "canopen-lens[gui]"     # 프로그램 + 라이브러리
pip install canopen-lens            # 라이브러리와 명령어만 (GUI 없는 서버·라즈베리파이용)
```

미리 컴파일된 패키지가 올라가 있어서 C++ 컴파일러가 필요 없습니다 (Windows x64, Linux x86_64, Linux aarch64).
설치 후 `canopen-lens`를 입력하면 창이 열립니다.

---

## 5분 사용법

**① 로그 저장하기** — 장비에 연결된 리눅스 PC나 라즈베리파이에서:

```bash
candump -l can0
```

문제가 생기는 동작을 한 번 해 본 뒤 `Ctrl+C`로 멈추면 `candump-날짜_시간.log` 파일이 생깁니다.
(`candump -t a can0 > log.txt`처럼 화면 출력을 저장한 파일도 읽을 수 있습니다.)

**② 열기** — 파일을 창에 끌어다 놓거나 오른쪽 위 **로그 열기**를 누릅니다. 로그가 없으면 **예제**에서 골라 보세요.

| 예제 | 내용 |
|---|---|
| 여러 장치 예제 | 드라이브 3대 + I/O 모듈. SDO 실패, EMCY, 폴트 해제 실패, 하트비트 끊김 등 여러 문제가 들어 있습니다 |
| 2륜 AMR 예제 | ros2_canopen 마스터(노드 2) + STM32 2축 드라이브(노드 1, 오른쪽 바퀴 = 축 1, 왼쪽 바퀴 = 축 2). 부팅 때 마스터가 SDO로 PDO 번호표(COB-ID)와 매핑을 설정하는 과정(끄기 → 매핑 → 켜기), 두 바퀴 운전 허가, 주행, 비상정지로 두 축이 함께 Fault가 됐다가 복구되는 과정이 들어 있습니다 |

**③ 요약 읽기** — 맨 위 카드가 전체 판정이고, 아래 표가 문제 목록입니다. **해결 안 됨**(빨강, 로그가 끝날 때까지 남은 문제)이 맨 위, **회복**(청록, 중간에 났다가 돌아온 문제)이 그다음입니다. **경고**(주황)는 접혀 있어서 눌러야 펼쳐집니다. 오른쪽에는 장치마다 상태가 한 줄씩 나옵니다.

**④ 자세히 보기** — 문제 한 줄을 누르면 오른쪽에 설명이 열립니다. 시간 순서로 무슨 일이 있었는지, 먼저 확인할 것 세 가지가 나오고, **이 시점 메시지 보기**를 누르면 **메시지** 화면에서 그 순간 오간 메시지가 한 줄씩 쉬운 말로 풀려 있습니다.

![문제 자세히 보기](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/detail_ko.png)

![메시지 해석 화면](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/frames_ko.png)

장치에 EDS 파일을 붙이거나 CiA 402 드라이브로 해석하게 하려면, 오른쪽 장치 목록에서 그 장치의 **⋯** 버튼을 누릅니다.

**⑤ 실시간** — 위쪽 **실시간** 화면에서 USB-CAN 어댑터나 SocketCAN에 직접 연결해, 메시지와 문제를 생기는 즉시 볼 수 있습니다. 장비가 없으면 **데모**를 골라 예제 로그를 실제 시간으로 재생해 보세요. 받은 메시지는 모두 기록되어, **기록 저장**으로 candump 파일로 남기거나 **로그 분석으로 열기**로 바로 자세히 분석할 수 있습니다.

| 연결 방식 | 채널 예시 | 참고 |
|---|---|---|
| socketcan | `can0` | 리눅스·라즈베리파이. 속도는 `sudo ip link set can0 up type can bitrate 500000`로 미리 설정 |
| pcan | `PCAN_USBBUS1` | PEAK 드라이버 필요 |
| kvaser / ixxat / vector | `0` | 각 제조사 드라이버 필요 |
| slcan | `COM3`, `/dev/ttyACM0` | CANable 등 시리얼 방식 어댑터 |
| gs_usb | `0` | candleLight 펌웨어 어댑터 |

![실시간 모니터](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/live_ko.png)

**⑥ 타임라인** — 장치와 모터 축의 상태가 시간에 따라 어떻게 바뀌었는지 색 막대로 보여줍니다. 빨간 구간이 폴트, 빈 구간이 통신이 끊긴 시간입니다. 막대를 누르면 그 시점의 메시지로 이동하고, Ctrl+마우스 휠이나 드래그로 짧은 구간을 확대할 수 있습니다.

![상태 타임라인](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/timeline_ko.png)

모르는 용어는 오른쪽 위 **용어 설명**에서 볼 수 있습니다. 결과는 **결과 저장**으로 보고서(.txt), JSON, 엑셀용 CSV로 저장할 수 있습니다.

---

## 명령줄에서 쓰기

창이 없는 서버나 라즈베리파이, SSH 접속에서도 같은 내용을 볼 수 있습니다. 로그 파일 이름만 넣으면 됩니다.

```bash
canopen-lens examples                 # 예제 로그 2개를 지금 폴더에 받기
canopen-lens sample_cia402.log        # 요약
```

```
✖ 확인이 필요합니다   해결 안 됨 3  회복 2  경고 2  정상 1
  sample_cia402.log · 6.0초 · 메시지 5,304개 · 노드 5개

해결 안 됨
   1  노드 4         응답 없음 — 버스에 없는 것으로 보임    0.27초
   2  노드 3         통신이 끊긴 뒤 돌아오지 않음           5.41초
   3  노드 2         설정이 적용되지 않음                   0.26초

회복됨
   4  노드 5 · 축 2  모터 구속으로 멈춤 → 리셋 후 회복      1.99초
   5  노드 2         과전류로 멈춤 → 두 번째 리셋에서 회복  2.99초

경고      노드 3 통신 0.7초 끊김 · CAN 선 오류 1회
정상      노드 1

자세히 보기   canopen-lens sample_cia402.log -d 1
결과 저장     canopen-lens sample_cia402.log -s 결과.csv
```

맨 아래 줄이 다음에 칠 명령입니다. 앞의 번호를 `-d`에 넣으면 그 문제를 자세히 봅니다.

```
$ canopen-lens sample_cia402.log -d 4
4  회복됨  노드 5 · 축 2 · 모터 구속으로 멈춤 → 리셋 후 회복
   원인: 모터 구속 (회전 불가) (EMCY 0x7121)

   무슨 일이 있었나요
   1.990초  Fault로 정지 — 모터 토크가 꺼짐
   1.990초  원인 보고: 모터 구속 (회전 불가) · EMCY 0x7121
   2.490초  Fault가 풀림
   2.690초  다시 운전

   먼저 확인할 것
   1. 장치 매뉴얼의 오류 코드표에서 0x7121 항목 찾기
   2. 드라이브 에러 코드(0x683F)를 읽어 자세한 원인 확인
   3. 원인을 없앤 뒤 Fault reset → 0x06 → 0x07 → 0x0F 순서로 다시 운전

   왜 중요한가요  Fault 상태의 드라이브는 모터 토크를 끄고 명령을 받지 않습니다. 해제하기 전까지 움직이지 않습니다.
   근거 메시지    #1512 #1515 #1988 #1993 #2179
```

| 명령 | 하는 일 |
|---|---|
| `canopen-lens 로그.log` | 요약 |
| `canopen-lens 로그.log -d 1` | 1번 문제 자세히 (`-d 1,4`, `-d all`도 됨) |
| `canopen-lens 로그.log -s 결과.txt` | 저장. 확장자로 형식이 정해집니다: `.txt` 보고서 · `.csv` 메시지 표(엑셀) · `.json` 진단 결과 |
| `canopen-lens 로그.log --eds 1=drive.eds` | 노드 1에 EDS 연결 (여러 번 쓸 수 있음) |
| `canopen-lens 로그.log --check` | 해결 안 된 문제가 있으면 종료 코드 1 (테스트 벤치·CI용) |
| `canopen-lens live can0` | 실시간 감시 (`pip install "canopen-lens[live]"`, 자세한 옵션은 `canopen-lens live -h`) |
| `canopen-lens` | 창(GUI) 열기 |

언어는 컴퓨터 설정을 따릅니다. 바꾸려면 `--lang en` / `--lang ko`를 붙이거나 환경 변수 `CANOPEN_LENS_LANG`을 설정하세요. 색이 필요 없으면 `--no-color`(또는 `NO_COLOR=1`)를 붙입니다.

---

## 결과는 이렇게 읽으면 됩니다

### 세 가지 상태

| 표시 | 뜻 |
|---|---|
| **해결 안 됨** (빨강) | 로그가 끝날 때까지 남아 있던 문제입니다. 폴트 상태로 끝났거나, 통신이 끊긴 채 돌아오지 않았거나, 설정값이 적용되지 않았습니다 |
| **회복** (청록) | 중간에 문제가 있었지만 로그가 끝날 때는 정상으로 돌아왔습니다. 원인은 확인해 두는 것이 좋습니다 |
| **경고** (주황) | 당장 멈추지는 않았지만 반복되면 문제가 될 수 있는 것들입니다 (하트비트 지연, CAN 선 오류 등) |

맨 위 판정은 이 셋으로 정해집니다. 해결 안 됨이 하나라도 있으면 **✖ 확인이 필요합니다**, 모두 회복됐으면 **▲ 문제가 있었지만 모두 회복됐습니다**, 경고만 있으면 **▲ 큰 문제는 없습니다**, 아무것도 없으면 **✔ 문제가 없습니다**입니다.

### 하나의 사건으로 묶는 방법

드라이브 하나가 멈추면 로그에는 여러 메시지가 함께 남습니다. 폴트, 같은 순간의 EMCY, 실패한 리셋, 성공한 리셋, 다시 운전. 이것을 따로 보여주면 문제가 다섯 개처럼 보이기 때문에 하나로 묶습니다.

- 같은 노드에서 0.1초 안에 일어난 폴트와 EMCY → 한 사건 (원인 = EMCY)
- 그 뒤의 리셋 실패 → "첫 번째 리셋 실패"로 사건 안에 기록
- 폴트가 풀리고 다시 운전 상태가 되면 → **회복**, 끝까지 안 풀리면 → **해결 안 됨**
- 같은 노드에서 반복된 SDO 무응답, 같은 오브젝트에 대한 같은 SDO 거절 → 각각 한 사건

### 자동으로 찾아주는 문제

| 문제 | 쉽게 말하면 |
|---|---|
| 설정값 읽기/쓰기(SDO) 실패 | 마스터가 보낸 설정을 장치가 거절했습니다. 거절 이유(중단 코드)를 설명하고 확인할 곳을 알려줍니다 |
| SDO 응답 없음 | 장치에 물어봤는데 대답이 없습니다. 노드 번호·전원·배선 순서로 확인하게 안내합니다 |
| 비상 메시지(EMCY) | 장치가 스스로 오류를 알렸습니다. 오류 코드를 사람이 읽을 수 있는 말로 바꿔 줍니다 |
| 생존 신호(하트비트) 끊김 | 평소 주기보다 오래 신호가 없었거나, 로그 끝까지 돌아오지 않았습니다 |
| 예상치 못한 재시작 | 리셋 명령이 없었는데 장치가 다시 켜졌습니다 (전원 저하, 워치독 등) |
| 드라이브 폴트 | 모터 드라이브가 오류로 멈췄습니다. 같은 시점의 EMCY를 찾아 원인 후보로 묶어 줍니다 |
| 운전 허가 실패 | Enable 명령을 보냈는데 드라이브가 켜지지 않았습니다 (순서 오류, 주전원, STO 등) |
| 폴트 리셋 실패 | 리셋을 보냈는데도 폴트가 그대로입니다 (원인이 남아 있음) |
| 급정지 | 드라이브가 Quick stop 상태로 들어갔습니다 |
| CAN 통신선 오류 | 선 위의 신호가 깨졌습니다 (종단저항, 통신 속도, 배선) |

---

## 로그를 어떻게 해석하나요? (데이터 분석 방법)

로그 한 줄은 이렇게 생겼습니다.

```
(1760500002.000250) can0 185#3702180220030000
 └ 시간              └ 포트 └ ID └ 데이터(바이트)
```

프로그램은 이 한 줄을 다음 순서로 풀어냅니다.

1. **누가 무엇을 보냈는지 알아냅니다.** CANopen에서는 ID가 "메시지 종류 + 노드 번호"로 정해져 있습니다. `0x185`는 `0x180`(TPDO1, 장치가 보내는 실시간 데이터) + 5(노드 번호)이므로 *노드 5가 보낸 실시간 상태 데이터*입니다.

2. **데이터의 구성을 찾습니다.** 실시간 데이터(PDO) 8바이트 안에 무엇이 어떤 순서로 들어 있는지는 장치마다 다릅니다. 이 구성표(PDO 매핑)를 다음 순서로 찾습니다.
   - 로그 앞부분에서 마스터가 SDO로 매핑을 설정한 기록 (가장 정확)
   - 지정한 EDS 파일
   - CiA 402 드라이브의 표준 기본값 (추정, 축 1만)

3. **값을 사람의 말로 바꿉니다.** 위 예시는 매핑이 "축 1 스테이터스워드(16비트) + 축 2 스테이터스워드(16비트) + 축 1 실제 속도(32비트)"이므로
   `TPDO1: 축 1 상태: 운전 중 (SW 0x0237), 축 2 상태: 폴트 (SW 0x0218), 축 1 실제 속도=800`
   으로 해석됩니다.

4. **앞뒤 흐름을 따라갑니다.** 한 줄만 봐서는 알 수 없는 것들을 시간 순서로 추적합니다.
   - SDO 질문과 대답을 짝지어 거절됐는지, 대답이 없는지 확인합니다
   - 노드마다 하트비트 주기를 스스로 계산해서 평소보다 늦으면 알려줍니다
   - CiA 402 드라이브는 축마다 상태 변화(대기 → 준비 → 스위치 온 → 운전 중, 폴트)를 기록하고, 마스터의 명령 뒤에 상태가 제대로 바뀌었는지 확인합니다
   - 폴트 직전·직후의 EMCY를 찾아 원인 후보로 연결합니다

5. **같은 문제를 묶어서 중요한 순서로 보여줍니다.**

### 바이트를 직접 읽는 법 (SDO 예시)

메시지를 누르면 오른쪽에 **바이트별 풀이**가 나옵니다. 예제 로그 8행을 예로 들면 이렇습니다.

```
(…) can0 582#4300100092010200
```

| 바이트 | 뜻 |
|---|---|
| `582` (ID) | `0x580` + 2 → **노드 2가 보낸 SDO 응답** |
| `43` | 명령 바이트. 2진수 `010 0 00 1 1` → 앞 3비트 `2` = 읽기 응답, `e=1` 값이 이 프레임 안에 있음, `s=1` 크기 표시, `n=0` 뒤 4바이트를 모두 사용 |
| `00 10` | 오브젝트 인덱스. **작은 자리 바이트가 먼저** 오므로 거꾸로 읽어 `0x1000` (장치 종류) |
| `00` | 서브인덱스 0 |
| `92 01 02 00` | 값. 거꾸로 읽으면 `0x00020192` = 131474 |

![바이트별 풀이](https://raw.githubusercontent.com/lch-98/canopen-lens/main/docs/bytes_ko.png)

장치 종류 `0x00020192`는 두 부분으로 나눠 읽습니다. 아래 16비트 `0x0192` = 402는 **CiA 402(드라이브) 프로파일**, 위 16비트 `0x0002`는 프로파일이 정한 추가 정보로 CiA 402에서는 **서보 드라이브**를 뜻합니다. 이 응답을 보고 노드 2를 드라이브로 판단합니다.

### CANopen이 아닌 로그를 넣으면

`candump`는 프로토콜과 상관없이 버스의 모든 프레임을 기록합니다. 자동차 CAN이나 J1939처럼 CANopen을 따르지 않는 장비의 로그도 열 수는 있지만, CANopen은 ID 번호에 의미를 정해 둔 약속이라 다른 프로토콜의 ID를 CANopen으로 읽으면 엉뚱한 해석이 나옵니다 (예: 자동차의 `0x316` 메시지가 "노드 22의 RPDO2"로 보임).

그래서 로그가 CANopen처럼 보이지 않으면 먼저 알려줍니다.

- 29비트 ID가 절반 이상이면 → "CANopen 통신이 아닌 것 같습니다" (J1939·제조사 고유 프로토콜 가능성)
- 하트비트·NMT·SDO·EMCY·SYNC가 하나도 없으면 → "CANopen 통신이 아닐 수 있습니다"

이때도 프로토콜과 상관없는 **ID별 통계**(ID마다 개수, 평균 주기, 최대 간격, 데이터 길이)는 그대로 보여줍니다. 주기 메시지가 끊긴 구간이나 버스 에러 프레임은 CANopen이 아니어도 찾을 수 있습니다.

해석은 C++로 작성되어 있어서, 200만 줄짜리 로그도 일반 PC에서 1~2초 안에 열립니다. 화면에 보이는 줄만 그때그때 문장으로 바꾸기 때문에 큰 로그에서도 창이 느려지지 않습니다.

---

## Python에서 쓰기

GUI 없이 라이브러리로 필요한 부분만 가져다 쓸 수 있습니다.

### 진단 결과 받기

```python
from canopen_lens import open_log

log = open_log("robot.log", eds={1: "drive.eds"})   # EDS는 선택

print(log.report("ko"))                 # 사람이 읽는 보고서 전체

ov = log.overview("ko")                 # 화면·명령줄과 같은 요약
print(ov.headline, ov.counts)           # "확인이 필요합니다", {"open": 3, "recovered": 2, …}
for inc in ov.incidents:                # 묶인 사건, 중요한 순서
    print(inc.number, inc.status, inc.where, inc.title)
    for ev in inc.events:
        print(f"  {ev.t:.3f}s", ev.text)

h = log.health("ko")
print(h.level, h.headline)             # "error", "문제가 발견되었습니다 – …"
for node in h.nodes:
    print(node.headline, node.details)

for group in log.grouped_issues():     # 같은 문제는 묶어서
    ex = log.explain(group.first, "ko")
    print(ex.title, group.count)
    print(ex.what, ex.why, ex.steps)
```

### 데이터 분석 (pandas · 엑셀)

```python
df = log.to_dataframe("ko")            # pip install pandas
faults = df[df["axis_state"] == "FAULT"]

log.to_csv("frames.csv")               # 엑셀에서 한글이 깨지지 않는 CSV
log.to_json("result.json")             # 다른 프로그램에 넘길 진단 결과
```

### 원하는 메시지만 골라 보기

```python
from canopen_lens import Kind

for row in log.trace.filter(kinds=[Kind.EMCY], node=2):
    print(log.summary(int(row), "ko"))

for p in log.trace.axis_timeline(5, axis=1):   # 노드 5, 축 2의 상태 변화
    print(f"{p.t:.3f}s", p.state)
```

### 실시간으로 버스 감시하기 (python-can)

```python
import can
from canopen_lens import LiveDecoder

dec = LiveDecoder(eds={1: "drive.eds"})
with can.Bus(interface="socketcan", channel="can0") as bus:
    dec.run(bus, lang="ko")            # 문제가 생기는 순간 화면에 출력
```

`feed()`로 직접 프레임을 넣을 수도 있고(`dec.feed(t, can_id, data)`), 최근 프레임만 기억하므로 오래 켜 둬도 메모리가 늘지 않습니다.

### 테스트 벤치·CI에서

```bash
canopen-lens robot.log --check -s result.json   # 해결 안 된 문제가 있으면 종료 코드 1, 결과는 JSON으로
```

`result.json`의 `summary`·`incidents`·`devices`에 화면과 같은 판정과 문제 목록이 들어 있습니다.
0.4 이전의 `canopen-lens report …` 명령도 그대로 쓸 수 있습니다.

타입 힌트가 포함되어 있어 IDE 자동완성이 됩니다.

---

## 현재 한계

- 로그 파일은 `candump` 형식만 읽습니다. PCAN `.trc`는 다음 버전에 추가할 예정입니다 (실시간 모니터는 PCAN 어댑터에 바로 연결할 수 있습니다).
- 실시간 모니터는 화면에 최근 메시지 5,000개만 보여줍니다. 전체 기록은 파일로 남습니다.
- PDO는 표준 ID(`0x180 + 노드 번호` 등)를 쓴다고 가정합니다. `0x1400`/`0x1800`으로 ID를 바꾼 경우는 아직 따라가지 않습니다.
- 다축 드라이브의 축 2~8은 EDS나 로그 안의 매핑 설정이 있어야 해석합니다.
- 진단은 로그에 보이는 정황을 바탕으로 한 안내입니다. 최종 판단은 장치 매뉴얼을 기준으로 해 주세요.
- 1.0 전까지는 Python API가 조금씩 바뀔 수 있습니다.

## 개발

```bash
git clone https://github.com/lch-98/canopen-lens
cd canopen-lens
pip install -e ".[gui,test,pandas,live]"
pytest
python tests/make_sample.py      # 여러 장치 예제 다시 만들기
python tests/make_amr_sample.py  # 2륜 AMR 예제 다시 만들기
```

배포 방법은 [RELEASING.md](RELEASING.md)를 참고하세요.

## 라이선스

MIT

"""PySide6 desktop GUI. Install with `pip install "canopen-lens[gui]"`."""

import importlib.util
import sys

_NOT_INSTALLED = """\
canopen-lens: 창(GUI) 화면에 필요한 PySide6가 설치되어 있지 않습니다.
지금은 라이브러리와 명령줄 기능만 설치된 상태입니다.

  창으로 보려면      pip install "canopen-lens[gui]"
  지금 바로 쓰려면   canopen-lens report 로그파일.log

The desktop app needs PySide6, which is not installed yet
(`pip install canopen-lens` installs only the library and the command line).

  To get the app     pip install "canopen-lens[gui]"
  Right now          canopen-lens report your.log
"""

_LOAD_FAILED = """\
canopen-lens: PySide6는 설치되어 있지만 불러오지 못했습니다.
PySide6 is installed but could not be loaded:

  {exc}

Linux에서는 보통 Qt가 쓰는 시스템 라이브러리가 없어서 생깁니다 / On Linux this usually means
system libraries used by Qt are missing:

  sudo apt install libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libxcb-cursor0

화면이 없는 환경(SSH, 서버)이라면 명령줄 기능을 쓰세요 / Without a screen (SSH, server):

  canopen-lens report 로그파일.log
"""


def _show(text: str) -> None:
    """Prints the message; when started without a console (canopen-lens-gui on Windows),
    shows it in a message box instead so the user is not left with nothing."""
    if sys.stderr is not None:
        print(text, file=sys.stderr)
        return
    if sys.platform.startswith("win"):  # pragma: no cover
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, "CANopen Lens", 0x30)
        except Exception:
            pass


def main(argv=None):
    try:
        from .app import main as _main
    except ImportError as exc:
        if importlib.util.find_spec("PySide6") is None:
            _show(_NOT_INSTALLED)
        else:
            _show(_LOAD_FAILED.format(exc=exc))
        raise SystemExit(1)
    return _main(argv)

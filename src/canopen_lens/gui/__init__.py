"""PySide6 desktop GUI. Install with `pip install "canopen-lens[gui]"`."""

import importlib.util
import sys

_NOT_INSTALLED = {
    "ko": """\
canopen-lens: 창(GUI) 화면에 필요한 PySide6가 설치되어 있지 않습니다.
지금은 라이브러리와 명령줄 기능만 설치된 상태입니다.

  창으로 보려면      pip install "canopen-lens[gui]"
  지금 바로 쓰려면   canopen-lens 로그파일.log   (예제: canopen-lens examples)
""",
    "en": """\
canopen-lens: the desktop app needs PySide6, which is not installed yet
(`pip install canopen-lens` installs only the library and the command line).

  To get the app     pip install "canopen-lens[gui]"
  Right now          canopen-lens your.log   (examples: canopen-lens examples)
""",
}

# one line in the other language, for people whose computer language is not their own
_OTHER = {
    "ko": "English: the window needs PySide6 → pip install \"canopen-lens[gui]\" · more: canopen-lens --lang en\n",
    "en": "한국어: 창 화면에는 PySide6가 필요합니다 → pip install \"canopen-lens[gui]\" · 자세히: canopen-lens --lang ko\n",
}

_LOAD_FAILED = {
    "ko": """\
canopen-lens: PySide6는 설치되어 있지만 불러오지 못했습니다.

  {exc}

Linux에서는 보통 Qt가 쓰는 시스템 라이브러리가 없어서 생깁니다:

  sudo apt install libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libxcb-cursor0

화면이 없는 환경(SSH, 서버)이라면 명령줄로 보세요:   canopen-lens 로그파일.log
""",
    "en": """\
canopen-lens: PySide6 is installed but could not be loaded:

  {exc}

On Linux this usually means system libraries used by Qt are missing:

  sudo apt install libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libxcb-cursor0

Without a screen (SSH, server), use the command line:   canopen-lens your.log
""",
}


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


def _lang(argv) -> str:
    from ..cli import default_lang

    args = list(argv or [])
    for k, a in enumerate(args):
        if a in ("--lang=ko", "--ko") or (a == "--lang" and args[k + 1:k + 2] == ["ko"]):
            return "ko"
        if a in ("--lang=en", "--en") or (a == "--lang" and args[k + 1:k + 2] == ["en"]):
            return "en"
    return default_lang()


def main(argv=None):
    try:
        from .app import main as _main
    except ImportError as exc:
        lang = _lang(sys.argv if argv is None else argv)
        if importlib.util.find_spec("PySide6") is None:
            _show(_NOT_INSTALLED[lang] + "\n" + _OTHER[lang])
        else:
            _show(_LOAD_FAILED[lang].format(exc=exc))
        raise SystemExit(1)
    return _main(argv)

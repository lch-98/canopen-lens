"""PySide6 desktop GUI. Install with `pip install canopen-lens[gui]`."""


def main(argv=None):
    try:
        from .app import main as _main
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "The GUI needs PySide6. Install it with:\n    pip install \"canopen-lens[gui]\"\n" f"({exc})"
        )
    return _main(argv)

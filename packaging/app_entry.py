"""Entry point for the standalone (PyInstaller) build of the GUI."""

import sys

from canopen_lens.gui.app import main

if __name__ == "__main__":
    sys.exit(main())

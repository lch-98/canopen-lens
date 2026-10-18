# PyInstaller spec for the standalone CANopen Lens app.
#   pip install pyinstaller ".[gui]"
#   pyinstaller packaging/canopen-lens.spec
# Output: dist/CANopenLens/ (run CANopenLens or CANopenLens.exe inside it)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
datas = collect_data_files("canopen_lens", includes=["examples/*.log", "py.typed"])

# Only the Qt parts the GUI uses; keeps the download much smaller.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml",
    "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtSvg",
    "tkinter", "pandas", "numpy",
]
# python-can loads its interface drivers by name at runtime, so bundle them all
hidden = ["canopen_lens._core"] + collect_submodules("can.interfaces") + collect_submodules("can.io")

a = Analysis(
    [str(root / "packaging" / "app_entry.py")],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CANopenLens",
    console=False,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CANopenLens")

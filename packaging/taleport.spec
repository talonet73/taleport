# PyInstaller spec: one-folder, windowed build of TALeport.
# Run through packaging/build.ps1 (it builds the UI and the icon first).

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent  # noqa: F821 (defined by PyInstaller)
VERSION = re.search(
    r'__version__ = "([^"]+)"', (ROOT / "backend" / "taleport" / "__init__.py").read_text()
).group(1)

# Version resource of TALeport.exe (Properties → Details in Windows).
numbers = ", ".join([*VERSION.split("."), "0"][:4])
OUTPUT = ROOT / "packaging" / "output"
OUTPUT.mkdir(exist_ok=True)
(OUTPUT / "version_info.txt").write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({numbers}), prodvers=({numbers})),
  kids=[
    StringFileInfo([StringTable("040904B0", [
      StringStruct("CompanyName", "TALeport"),
      StringStruct("FileDescription", "TALeport"),
      StringStruct("FileVersion", "{VERSION}"),
      StringStruct("InternalName", "taleport"),
      StringStruct("LegalCopyright", "MIT License"),
      StringStruct("OriginalFilename", "TALeport.exe"),
      StringStruct("ProductName", "TALeport"),
      StringStruct("ProductVersion", "{VERSION}"),
    ])]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])]),
  ],
)
""",
    encoding="utf-8",
)

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend"),
    (str(ROOT / "assets" / "brand"), "assets/brand"),
    *collect_data_files("taleport"),  # migrations, prompt templates, resources (i18n, stopwords…)
    *collect_data_files("yake"),
    *copy_metadata("apscheduler"),  # triggers are looked up through entry points
]

hiddenimports = [
    *collect_submodules("uvicorn"),
    *collect_submodules("apscheduler.triggers"),
    "keyring.backends.Windows",
    "pystray._win32",
    "webview.platforms.edgechromium",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "respx", "ruff", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TALeport",
    icon=str(ROOT / "assets" / "brand" / "taleport.ico"),
    version=str(OUTPUT / "version_info.txt"),
    console=False,
    upx=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="TALeport",
)

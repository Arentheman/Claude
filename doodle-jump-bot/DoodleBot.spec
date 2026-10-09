# Сборка одного файла DoodleBot.exe:  pyinstaller DoodleBot.spec
# (на Windows с установленными пакетами из requirements.txt + pyinstaller)
a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=[("templates/*.png", "templates")],
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32"],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="DoodleBot",
    console=False,
    upx=False,
)

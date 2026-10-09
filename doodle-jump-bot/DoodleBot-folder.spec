# Сборка папкой (без самораспаковки — антивирусы реже ругаются):
#   pyinstaller DoodleBot-folder.spec   ->  dist\DoodleBot\DoodleBot.exe
a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=[("templates/*.png", "templates")],
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32"],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="DoodleBot", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="DoodleBot", upx=False)

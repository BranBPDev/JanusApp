# -*- mode: python ; coding: utf-8 -*-
# Un único .exe (onefile): no genera carpetas auxiliares junto al ejecutable.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/assets', 'app/assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'test'],
    noarchive=False,
)

# Las traducciones de Qt pesan mucho y la app no las usa.
a.datas = [d for d in a.datas if 'translations' not in d[0].replace('\\', '/').split('/')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JanusApp',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='app/assets/logo.ico',
)

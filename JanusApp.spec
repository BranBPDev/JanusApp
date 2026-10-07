# -*- mode: python ; coding: utf-8 -*-
# Modo carpeta (onedir): arranque rápido y listo para librerías pesadas (numpy, trimesh, open3d...).

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
    [],
    exclude_binaries=True,
    name='JanusApp',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='app/assets/logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='JanusApp',
)

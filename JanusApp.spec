# -*- mode: python ; coding: utf-8 -*-
# Un único .exe (onefile). Se descartan los componentes de Qt que la aplicación no usa para reducir la descarga.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/assets', 'app/assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'numpy.f2py', 'PIL.ImageTk'],
    noarchive=False,
)

_DROP_FILES = {
    'opengl32sw.dll', 'qt6pdf.dll', 'qt6svg.dll', 'qt6quick.dll', 'qt6qml.dll', 'qt6qmlmodels.dll',
    'qt6qmlworkerscript.dll', 'qt6virtualkeyboard.dll', 'qpdf.dll', 'qsvg.dll', 'qsvgicon.dll',
    'qdirect2d.dll', 'qminimal.dll', 'qoffscreen.dll', 'qtvirtualkeyboardplugin.dll',
}


def _keep(entry):
    name = entry[0].replace('\\', '/').lower()
    return name.rsplit('/', 1)[-1] not in _DROP_FILES and 'translations' not in name.split('/')


a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]

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

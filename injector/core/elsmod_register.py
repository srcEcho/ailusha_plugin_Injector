""".elsmod file association — Windows registry (HKCU, no admin required)

Standard approach:
  - Only register in frozen mode (compiled EXE).  Dev mode has no
    real executable to associate — sys.executable would point to python.exe.
  - The EXE path comes from sys.executable (Nuitka) or sys.argv[0] (PyInstaller).
  - UserChoice (Windows 8+ hash) is deleted on a best-effort basis.
"""

import ctypes
import os
import sys
import winreg

ELSMOD_PROGID = "ElushaPlugin.elsmod"


def _is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def _get_exe_path() -> str:
    """Return the absolute path to the compiled EXE, or '' in dev mode."""
    if not _is_frozen():
        return ""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller: sys.executable is the temp bootloader
        return os.path.abspath(sys.argv[0])
    # Nuitka: sys.executable IS the real EXE
    return os.path.abspath(sys.executable)


def register():
    """Register .elsmod -> ElushaInjector.exe.  No-op in dev mode."""
    exe_path = _get_exe_path()
    if not exe_path:
        return  # dev mode — nothing to associate

    # Best-effort: clear UserChoice hash that locks a previous "Open with"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.elsmod",
            0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        try:
            winreg.DeleteValue(key, "UserChoice")
        except OSError:
            pass
        winreg.CloseKey(key)
    except OSError:
        pass

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Classes\.elsmod") as k:
        winreg.SetValue(k, "", winreg.REG_SZ, ELSMOD_PROGID)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          rf"Software\Classes\{ELSMOD_PROGID}\DefaultIcon") as k:
        winreg.SetValue(k, "", winreg.REG_SZ, f'"{exe_path}",0')

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          rf"Software\Classes\{ELSMOD_PROGID}\shell\open\command") as k:
        winreg.SetValue(k, "", winreg.REG_SZ, f'"{exe_path}" "%1"')

    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


def unregister():
    """Remove the .elsmod association (Classes + FileExts)."""
    # HKCU Classes
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.elsmod")
    except OSError:
        pass

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell\open\command")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell\open")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\DefaultIcon")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}")
    except OSError:
        pass

    # FileExts (UserChoice etc.)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.elsmod",
            0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "UserChoice")
        except OSError:
            pass
        try:
            winreg.DeleteValue(key, "Application")
        except OSError:
            pass
        winreg.CloseKey(key)
    except OSError:
        pass

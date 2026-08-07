""".elsmod file association — Windows registry (HKCU, no admin required)"""
import ctypes
import os
import sys
import winreg


ELSMOD_PROGID = "ElushaPlugin.elsmod"


def _get_exe_path() -> str:
    """Get the absolute path to this executable.

    Handles PyInstaller (sys.executable is in TEMP, use sys.argv[0]),
    Nuitka (sys.executable is the actual EXE), and dev mode.
    Always returns an absolute path regardless of CWD or launch method."""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller: sys.executable is the bootloader in TEMP
            # sys.argv[0] is the real EXE path
            return os.path.abspath(sys.argv[0])
        # Nuitka: sys.executable IS the compiled EXE — always reliable
        return os.path.abspath(sys.executable)
    # Dev mode: use the Python interpreter
    return os.path.abspath(sys.executable)


def register():
    """Register .elsmod -> ElushaInjector.exe association."""
    exe_path = _get_exe_path()

    # Remove UserChoice hash (Windows 8+) that locks the association
    # when the user previously set a default via "Open with". Without this,
    # the HKCU Classes keys below have no effect.
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.elsmod",
            0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        try:
            winreg.DeleteValue(key, "UserChoice")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except FileNotFoundError:
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

    # Notify system
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


def unregister():
    """Remove .elsmod association."""
    # Clean HKCU Classes
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.elsmod")
    except FileNotFoundError:
        pass
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{ELSMOD_PROGID}",
                             0, winreg.KEY_READ)
        winreg.CloseKey(key)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}\DefaultIcon")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{ELSMOD_PROGID}")
    except FileNotFoundError:
        pass

    # Clean FileExts (UserChoice + OpenWithProgids)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.elsmod",
            0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "UserChoice")
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteValue(key, "Application")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass

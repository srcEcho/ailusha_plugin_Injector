""".elsmod file association — Windows registry (HKCU, no admin required)"""
import ctypes
import sys
import winreg


ELSMOD_PROGID = "ElushaPlugin.elsmod"


def register():
    """Register .elsmod → ElushaInjector.exe association."""
    exe_path = sys.executable

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

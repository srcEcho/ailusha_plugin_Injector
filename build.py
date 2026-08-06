"""PyInstaller build script for Elusha Injector."""
import os
import subprocess
import sys
import shutil

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "injector")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
EMBED_DIR = os.path.join(PROJECT_ROOT, "output")


def ensure_embedded_files():
    """Ensure version.dll and UninstallElusha.exe exist in output/."""
    os.makedirs(EMBED_DIR, exist_ok=True)

    dll = os.path.join(EMBED_DIR, "version.dll")
    if not os.path.exists(dll):
        src = os.path.join(PROJECT_ROOT, "src", "mainline")
        print(f"WARNING: {dll} not found. Place compiled version.dll in output/")
        print(f"  Compile: gcc -shared -s -Os -static -Wl,--kill-at -o version.dll version_proxy_v36_final.c -lkernel32")

    uninstaller = os.path.join(EMBED_DIR, "UninstallElusha.exe")
    if not os.path.exists(uninstaller):
        print(f"Building UninstallElusha.exe...")
        uninstaller_py = os.path.join(PROJECT_ROOT, "uninstaller.py")
        uninst_icon = os.path.join(PROJECT_ROOT, "injector", "Uninstall_logo.ico")
        uninst_cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--windowed",
            "--name", "UninstallElusha",
            "--distpath", EMBED_DIR,
            "--workpath", os.path.join(BUILD_DIR, "uninstaller"),
            "--specpath", BUILD_DIR,
        ]
        if os.path.exists(uninst_icon):
            uninst_cmd.append(f"--icon={uninst_icon}")
        uninst_cmd.append(uninstaller_py)
        subprocess.run(uninst_cmd, check=True)
        # Clean up
        for d in [os.path.join(BUILD_DIR, "uninstaller")]:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)


def build_injector():
    """Build ElushaInjector.exe with PyInstaller."""
    print("Building ElushaInjector.exe...")

    # Collect embedded files
    add_data = []
    for fn in ["version.dll", "UninstallElusha.exe"]:
        fp = os.path.join(EMBED_DIR, fn)
        if os.path.exists(fp):
            add_data.append(f"--add-data={fp};.")

    # Icon — PyInstaller resolves relative to specpath, use absolute
    icon_path = os.path.abspath(os.path.join(PROJECT_ROOT, "injector", "Injector_logo.ico"))
    icon_flag = [f"--icon={icon_path}"] if os.path.exists(icon_path) else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", "ElushaInjector",
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", BUILD_DIR,
        "--hidden-import", "darkdetect",
    ] + icon_flag + add_data + [
        os.path.join(PROJECT_ROOT, "run.py")
    ]

    subprocess.run(cmd, check=True)
    print(f"\nBuild complete: {os.path.join(DIST_DIR, 'ElushaInjector.exe')}")


if __name__ == "__main__":
    ensure_embedded_files()
    build_injector()

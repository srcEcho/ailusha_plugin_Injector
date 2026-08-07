"""Build script — hybrid Nuitka + PyInstaller approach.

Strategy:
  - Nuitka  → game-dir components (avoids EnigmaVB detection)
  - PyInstaller → installer onefile (mature, single-file, no Enigma concern)

Pipeline:
  1. UninstallElusha.exe  (Nuitka standalone, small tkinter app)
  2. ElushaInjector/      (Nuitka standalone, PySide6 GUI)
  3. ElushaInstaller.exe  (PyInstaller onefile, bundles entire ElushaInjector/)
"""
import subprocess
import os
import shutil
import sys

PROJECT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(PROJECT, "dist")
TMP = os.path.join(DIST, "_tmp")


def run(cmd, desc):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"{'='*60}")
    print(f"  {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=PROJECT)
    if r.returncode != 0:
        print(f"\nERROR: {desc} failed (exit {r.returncode})")
        sys.exit(1)


def main():
    # Clean previous outputs
    for d in ["build", "dist"]:
        p = os.path.join(PROJECT, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    # ── Step 1: UninstallElusha.exe (standalone, ~8 MB) ──
    os.makedirs(TMP, exist_ok=True)
    run(
        "python -m nuitka --standalone --windows-console-mode=disable "
        "--enable-plugin=tk-inter "
        "--output-dir=dist/_tmp --output-filename=UninstallElusha.exe "
        "--windows-icon-from-ico=injector/Uninstall_logo.ico "
        "--assume-yes-for-downloads uninstaller.py",
        "Step 1/3  Build UninstallElusha.exe (Nuitka standalone)")

    # Nuitka uses module name for .dist folder: uninstaller.py -> uninstaller.dist
    uninstaller_src = os.path.join(TMP, "uninstaller.dist", "UninstallElusha.exe")
    if not os.path.isfile(uninstaller_src):
        print("ERROR: UninstallElusha.exe not found at", uninstaller_src)
        sys.exit(1)

    # ── Step 2: ElushaInjector (Nuitka standalone) ──
    run(
        "python -m nuitka --standalone --windows-console-mode=disable "
        "--enable-plugin=pyside6 "
        "--output-dir=dist --output-filename=ElushaInjector.exe "
        "--windows-icon-from-ico=injector/Injector_logo.ico "
        "--include-data-files=injector/Injector_logo.ico=injector/Injector_logo.ico "
        "--include-data-files=injector/Injector_logo.png=injector/Injector_logo.png "
        "--assume-yes-for-downloads run.py",
        "Step 2/3  Build ElushaInjector (Nuitka standalone)")

    # Rename run.dist -> ElushaInjector
    run_dist = os.path.join(DIST, "run.dist")
    injector_dist = os.path.join(DIST, "ElushaInjector")
    if not os.path.isdir(run_dist):
        print("ERROR: run.dist not found!")
        sys.exit(1)
    # Remove previous build if it exists
    if os.path.isdir(injector_dist):
        shutil.rmtree(injector_dist, ignore_errors=True)
    os.rename(run_dist, injector_dist)

    # Merge UninstallElusha + its Tcl/Tk runtime into ElushaInjector/
    uninstaller_dist = os.path.join(TMP, "uninstaller.dist")
    print(f"\n  Merging UninstallElusha runtime files...")
    for item in os.listdir(uninstaller_dist):
        src = os.path.join(uninstaller_dist, item)
        dst = os.path.join(injector_dist, item)
        if os.path.isdir(src):
            if not os.path.exists(dst):
                shutil.copytree(src, dst)
                print(f"    dir : {item}")
        else:
            if not os.path.isfile(dst):
                shutil.copy2(src, dst)
                print(f"    file: {item}")
            # else: already exists (e.g. python310.dll shared with injector)

    # ── Step 3: ElushaInstaller (PyInstaller onefile, bundles entire ElushaInjector/) ──
    if not os.path.isdir(injector_dist):
        print("ERROR: ElushaInjector/ not found!")
        sys.exit(1)

    run(
        "pyinstaller --onefile --windowed "
        "--icon injector/Injector_logo.ico "
        "--name ElushaInstaller "
        f"--add-data \"{injector_dist}{os.pathsep}ElushaInjector\" "
        "--clean "
        "elusha_installer.py",
        "Step 3/3  Build ElushaInstaller (PyInstaller onefile)")

    # ── Cleanup ──
    shutil.rmtree(TMP, ignore_errors=True)
    # Remove Nuitka build dirs that linger in dist/
    for name in os.listdir(DIST):
        if name.endswith(".build"):
            shutil.rmtree(os.path.join(DIST, name), ignore_errors=True)
    # Remove PyInstaller build artifacts and auto-generated spec
    for p in [os.path.join(PROJECT, "build"),
              os.path.join(PROJECT, "ElushaInstaller.spec")]:
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            os.remove(p)

    # ── Report ──
    installer = os.path.join(DIST, "ElushaInstaller.exe")
    injector_exe = os.path.join(injector_dist, "ElushaInjector.exe")
    if not os.path.isfile(installer) or not os.path.isfile(injector_exe):
        print("ERROR: Build outputs missing!")
        sys.exit(1)

    installer_sz = os.path.getsize(installer) / (1024 * 1024)
    injector_sz = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fns in os.walk(injector_dist) for f in fns
    ) / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"  Build complete")
    print(f"{'='*60}")
    print(f"  Step 1+2: Nuitka    — no EnigmaVB detection")
    print(f"  Step 3:   PyInstaller onefile — installer only")
    print(f"{'='*60}")
    print(f"  ElushaInjector/     {injector_sz:.1f} MB  (Nuitka standalone)")
    print(f"  ElushaInstaller.exe {installer_sz:.1f} MB  (PyInstaller onefile)")
    print(f"  dist/ElushaInstaller.exe  <- distribute this file")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

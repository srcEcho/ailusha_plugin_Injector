#!/usr/bin/env pythonw
"""Development launcher for Elusha Injector.
Usage: pythonw run.py [--dev] [--cli <cmd> ...]
Use pythonw.exe (no console) for GUI mode, python.exe for CLI.
"""
import sys
import os

# Ensure project root is in path
try:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(sys.executable))
sys.path.insert(0, PROJECT_ROOT)

from injector.main import main

if __name__ == "__main__":
    main()

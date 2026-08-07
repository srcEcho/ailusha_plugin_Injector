from setuptools import setup, find_packages

setup(
    name="elusha-injector",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["run", "uninstaller"],
    install_requires=[
        "PySide6>=6.5.0",
    ],
    python_requires=">=3.10",
)

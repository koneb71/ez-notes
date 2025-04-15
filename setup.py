import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": [
        "sys",
        "os",
        "json",
        "uuid",
        "wave",
        "pyaudio",
        "threading",
        "tempfile",
        "whisper",
        "subprocess",
        "zipfile",
        "shutil",
        "pathlib",
        "datetime",
        "google.genai",
        "PyQt6",
        "dotenv",
        "cryptography",
        "base64"
    ],
    "excludes": [],
    "include_files": [
        "README.md",
        "requirements.txt",
        "secure_storage.py"
    ]
}

# GUI applications require a different base on Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="EZ Notes",
    version="1.0.0",
    description="Modern note-taking application with AI features",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="EZ Notes.exe",
            icon="icon.ico"  # You'll need to create this
        )
    ]
) 
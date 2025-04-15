@echo off
echo Creating icon...
python create_icon.py

echo Installing required packages...
pip install -r requirements.txt
pip install cx_Freeze pillow pyinstaller

echo Building executable...
python setup.py build

echo Creating PyInstaller executable...
pyinstaller --noconfirm --onefile --windowed ^
  --icon=icon.ico ^
  --add-data "README.md;." ^
  --add-data "LICENSE.txt;." ^
  --add-data "secure_storage.py;." ^
  --clean ^
  --strip ^
  --noupx ^
  --exclude ".conda" ^
  --exclude "__pycache__" ^
  --exclude ".env" ^
  --exclude ".venv" ^
  --exclude "venv" ^
  --exclude "env" ^
  --name "EZ Notes" main.py

echo Creating installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

echo Build complete!
echo Installer can be found in installer/EZNotes_Setup.exe
pause 
@echo off
setlocal

cd /d "%~dp0"

echo [1/2] 依存関係をインストールしています...
pip install -r requirements.txt
if errorlevel 1 goto :error

echo [2/2] exeをビルドしています...
pyinstaller --onefile --windowed --name "BMSWavDurationChecker" main.py
if errorlevel 1 goto :error

echo.
echo ビルド完了: dist\BMSWavDurationChecker.exe
goto :eof

:error
echo ビルドに失敗しました。
exit /b 1

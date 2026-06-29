@echo off
cd /d "%~dp0"
echo Lancement de ARTYX...
where python >nul 2>nul
if %errorlevel% neq 0 (
  echo Python n'est pas installe. Installe Python depuis https://www.python.org/downloads/
  pause
  exit /b
)
start http://localhost:8787
python app.py
pause

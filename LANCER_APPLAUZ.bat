@echo off
cd /d "%~dp0"
echo Lancement de APPLAUZ...
where python >nul 2>nul
if %errorlevel% neq 0 (
  echo Python n est pas installe.
  pause
  exit /b
)
start http://localhost:8787
python app\app.py
pause

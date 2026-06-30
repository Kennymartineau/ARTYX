@echo off
cd /d "%~dp0"
echo Sauvegarde APPLAUZ vers GitHub...
git add .
git commit -m "Mise a jour APPLAUZ"
git push
pause

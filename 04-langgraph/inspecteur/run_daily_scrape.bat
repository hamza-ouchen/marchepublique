@echo off
REM =====================================================================
REM SOU9NA — déclencheur planifié (07:30)
REM Cron -> FastAPI (point d'entrée) -> file de jobs -> RÉGISSEUR (A2A)
REM         -> INSPECTEUR / COMPAGNON / JUGE.
REM Aucun scrape ni pipeline n'est lancé directement depuis ce .bat.
REM =====================================================================
cd /d "C:\Users\PC\Desktop\Sou9na-Projet"
set PY=C:\Users\PC\AppData\Local\Programs\Python\Python315\python.exe
set LOG=C:\Users\PC\AppData\Local\Temp\opencode\inspecteur_daily.log

echo. >> "%LOG%"
echo === RUN %DATE% %TIME% — cron -^> FastAPI -^> RÉGISSEUR === >> "%LOG%"
"%PY%" "02-backend\declencheur_cron.py" auto >> "%LOG%" 2>&1
echo === END %DATE% %TIME% === >> "%LOG%"

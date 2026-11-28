@echo off
REM Job quotidien "offres en cours absentes de la base" (scrape + documents + enrichment).
cd /d "%~dp0..\.."
set PY=C:\Users\PC\AppData\Local\Programs\Python\Python315\python.exe
"%PY%" -m inspecteur --daily-missing --company EXPLEO-IT-001 --docs-minutes 240

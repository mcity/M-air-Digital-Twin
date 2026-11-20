@echo off
rem Windows: install the M-Air corridor. The arguments are those of install.py, for example
rem     install.bat --ue-root "C:\Program Files\Epic Games\UE_5.7"
setlocal
set "MAIR_PY=py -3"
where py >nul 2>nul || set "MAIR_PY=python"
%MAIR_PY% "%~dp0install.py" %*
exit /b %ERRORLEVEL%

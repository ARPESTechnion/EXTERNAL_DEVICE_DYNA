@echo off
REM get the process number
set PID=%1
if "%1"=="" (
    echo Must supply a PID
)

REM enable delayed variable expansion
setlocal enabledelayedexpansion

taskkill /PID %PID% /F

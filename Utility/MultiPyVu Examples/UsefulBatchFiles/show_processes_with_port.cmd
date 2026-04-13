@echo off
REM get the provided port number.  If blank, use port 5000
set PORT=%1
if "%1"=="" (
    set PORT=5000
)

REM enable delayed variable expansion
setlocal enabledelayedexpansion

netstat -ano | findstr :%PORT%

REM The following gets fancier, but I think the above command is more what is desired

@REM REM initialize a flag to show headers
@REM set HEADER_SHOWN=0

@REM set "TAB=   " & set "TAB=!TAB: =    !"

@REM REM get the list of processes using the given port number
@REM for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT%') do (
@REM     REM remove the leading space from the PID
@REM     set PID=%%a

@REM     REM show headers only once
@REM     if "!HEADER_SHOWN!"=="0" (
@REM         echo Name      %TAB%PID      Session Name     Session#    Mem Usage
@REM         echo ==========%TAB%======== ================ =========== ============
@REM     )
@REM         set HEADER_SHOWN=1

@REM     for /f "skip=3 tokens=1,*" %%b in ('tasklist /fi "PID eq !PID!"') do (
@REM         if not "%%b"=="" (
@REM             @REM echo PID: !PID! ~ Process: %%b %%c
@REM             echo %%b%TAB%%%c
@REM         )
@REM     )
@REM )

endlocal

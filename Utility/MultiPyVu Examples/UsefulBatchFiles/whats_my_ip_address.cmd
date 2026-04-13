@echo off
setlocal enabledelayedexpansion
SETLOCAL

rem Find the connected interface
set idx=0
set networkInterface=""
for /f "tokens=1,4,5 delims= " %%A in ('netsh interface IPv4 show interfaces') do ( 
	if "%%B"=="connected" (
		if "%%C"=="Ethernet" (
			set idx=%%A
			set networkInterface=%%C)
		if "%%C"=="Wi-Fi" (
			set idx=%%A
			set networkInterface=%%C)
		)
	)

rem Get the IP address for the connected interface
for /f "tokens=3 delims=: " %%I in ('netsh interface IPv4 show addresses %idx% ^| findstr /C:"IP Address"') do set ipAddress=%%I
echo IPv4 Address:  %ipAddress% (!networkInterface!)

'#Language "WWB-COM"
'#Uses ".\PicoScope\PicoScope.obm"

Option Explicit

Sub Main
	'How to use the PicoScope object:
		' The PicoScope Software must be running for this to function!
		' make sure you have " '#Uses ".\PicoScope\PicoScope.obm" " at the top of your script
		' First thing you want to do is define the default data directory.
			'This is done using PicoScope.FilePath(#)
				'The # is replaced with the directory using standard unix formatting. (C:\QdPpms\Data\YourDataDirectory\)
				'If you leave the # blank or never use the command, the Files will be saved in the standard data directory.
		'Once you have set up the default data directory (or not) you have 2 commands you can use
			'PicoScope.SaveText(#)
				'When this command is used the pico6 software is told to save the current data as .csv as well as the .psdata file types
				'Optional: The # is replaced with the file name or left blank.
				'the files will be labeled With the Date And Time (#PicoScopeData_YearMonthDay_Time)
			'PicoScope.SaveImage(#)
				'When this command is used the pico6 software is told to save a snapshot of the current data being displayed in the pico6 software. It will be saved as a .jpg as well as .psdata
				'Optional: The # is replaced with the file name or left blank.
				'the files will be labeled With the Date And Time (#PicoScopeData_YearMonthDay_Time)
		'The pico6 software takes some time to save files, so you must not send it commands in rapid succession. The time between commands will vary based on the computing speed of your computer.
		'There is not; necessarily, a need to put in wait commands. If your sequence is going to continue on and you do not need to save another file right away; then you can forego the wait command.
		'It is recomended that you test your pico6 software with a simple script before you take measurements. See the examples below or "Scan Temp Sweep With PicoScope.BAS"
		'If the pico6 software remains in the triggered mode(no longer taking live data) after you have used "PicoScope.SaveImage("image")" or "PicoScope.SaveText("Text")"
		'then you should comment out the "Wait(2)" and "Call Shell("cmd.exe /S /C" & "picoscope /a Run", vbNormalFocus)" lines in those respected functions within 
		'"PicoScop.obm"
		

		'Examples:

		PicoScope.FilePath="C:\QdPpms\Data\YourDataDirectory\"
		PicoScope.SaveImage()
		Wait(2)
		PicoScope.SaveImage("image")
		Wait(2)
		PicoScope.SaveText()
		Wait(2)
		PicoScope.SaveText("Text")
		Wait(2)




End Sub

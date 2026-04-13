'#uses "../Utils/PPMSUtils.obm"
'#uses "Keithley6220.obm"
'#uses "Keithley2182A.obm"

Sub Main
	Debug.Clear

	'Constants - do not modify
	Pi = 4*Atn(1)
	Keith6220 = 5      'GPIB addresses of meters
	Keith2182A = 7

	Dim Result As String
	Dim positiveV As String
	Dim negativeV As String
	Dim averageV As Double
	Dim ExciteCurrent As String

    '==================================
	' Initialize instrument and configure for desired measurement
	'===================================

	Keithley6220.Init
	Keithley6220.Config

	Keithley2182A.Init
	Keithley2182A.Config

'---------------------------

	'Assume circular geometry
	ExciteCurrent = InputBox("Excitation current in amps: ", "Sweep Temperature Fixed Field", "1e-9") 'Excitation current in amps
	If IsNumeric(ExciteCurrent) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If



	'==================================
	' Start measurement
	'===================================

	'Set current level
	GPIB.SendString(Keith6220, "OUTP On" & vbCrLf)

	    '==================================
	    ' Grab data
	    '===================================
		GPIB.SendString(Keith6220, "SOUR:CURR:LEV " + ExciteCurrent & vbCrLf)
		Wait(1)
	    'Send trigger command
		GPIB.SendString(Keith2182A, ":READ?" & vbCrLf)
		Wait(0.5)
		GPIB.GetString(Keith2182A, positiveV)
		Debug.Print "Voltage = " & positiveV
		Wait(1)
		'Reverse current and take measurement again
		GPIB.SendString(Keith6220, "SOUR:CURR:LEV -" + ExciteCurrent & vbCrLf)

		Wait(3)
	    'Send trigger command
		GPIB.SendString(Keith2182A, ":READ?" & vbCrLf)
		Wait(0.5)
		GPIB.GetString(Keith2182A, negativeV)
		Debug.Print "Voltage = " & negativeV

		averageV = (CDbl(positiveV) - CDbl(negativeV)) / 2.0

		'Send a request for data point
		'GPIB.SendString(Address, "SYST:COMM:SER:SEND ":DATA:LAT?"" & vbCrLf)

End Sub

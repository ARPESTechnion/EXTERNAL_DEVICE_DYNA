'#Uses "../MVUData/MVUData.cls"
'#uses "../Utils/PPMSUtils.obm"
'#uses "Keithley6220.obm"
'#uses "Keithley2182A.obm"
Sub Main
	Debug.Clear

	'Constants - do not modify
	Pi = 4*Atn(1)
	Keith6220 = 5
	Keith2182A = 7

	Dim field As Double
	Dim fieldstate As Long
	Dim temp As Double
	Dim tempstate As Long
	Dim status As Long
	Dim pressure As Double
	Dim Result As String
	Dim positiveV As String
	Dim negativeV As String
	Dim averageV As Double
	Dim FileName As String
	Dim A As String
	Dim DataFile As New MVUData
	Dim ExciteCurrent As String
	Dim d(10) As Double

    '==================================
	' Initialize instrument and configure for desired measurement
	'===================================

	Keithley6220.Init
	Keithley6220.Config

	Keithley2182A.Init
	Keithley2182A.Config

	'==================================
	' Declare sequence variables
	'===================================
	'Datafile name:
	FileName = InputBox("Data File Name: ", "Sweep Temperature Fixed Field", "C:\QdPpms\Data\BrentMelot\091003\ResistanceTestFile.dat")
	If FileName = "" Then
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	'Assume circular geometry
	ExciteCurrent = InputBox("Excitation current in amps: ", "Sweep Temperature Fixed Field", "1e-9") 'Excitation current in amps
	If IsNumeric(ExciteCurrent) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	ContArea = InputBox("Cross section area in mm^2: ", "Sweep Temperature Fixed Field", "1") 'Excitation current in amps
	If ContArea = "" Then Exit Sub
	If IsNumeric(SampThick) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	ContLength = InputBox("Separation between contacts in mm: ", "Sweep Temperature Fixed Field", "1") 'Excitation current in amps
	If ContLength = "" Then Exit Sub
	If IsNumeric(ContLength) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	TarTemp = InputBox("Target Temperature: ", "Sweep Temperature Fixed Field", "2")
	If TarTemp = "" Then Exit Sub
	If IsNumeric(TarTemp) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	TarTempRate = InputBox("Rate to sweep temperature (MAX = 20): ", "Sweep Temperature Fixed Field", "2") 'Max = 20
	If TarTempRate = "" Then Exit Sub
	If IsNumeric(TarTempRate) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	FixField = InputBox("Target Field: ", "Sweep Temperature Fixed Field", "0")
	If FixField = "" Then Exit Sub
	If IsNumeric(FixField) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	If FixField <> 0 Then
		FixFieldRate = InputBox("Rate to Change Field (Max = 189): ", "Sweep Temperature Fixed Field", "0") 'Max = 189
		If FixFieldRate = "" Then Exit Sub
		If IsNumeric(FixFieldRate) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If

	End If

	WaitTime = InputBox("Wait time between measurement points in seconds: ", "Sweep Temperature Fixed Field", "5") 'Time between measurement points in seconds
	If WaitTime = "" Then Exit Sub
	If IsNumeric(WaitTime) = False Then
		MsgBox("You should probably enter a numeric value.",vbInformation+vbOkOnly,"Oops!")
		GPIB.SendString(Address, "OUTP Off" & vbCrLf)
		Exit Sub
	End If
    '==================================
	' Initialize Datafile
	'===================================

	If DataFile.CreateFile(FileName) Then
		'don't write the header again if file already exists!!!
		DataFile.WriteHeader("Keithley 6220 current source and 2182 nanovoltmeter", "Temperature (K),Field (Oe),Sys. Pressure (torr),Pos. Voltage (V), Neg. Voltage (V), Avg. Voltage (V), Exc. Current (A), Resistance (Ohms), Resisitivity (Ohm-cm)",3,False,10,False,11,False)
	End If

	DataFile.MVUOpen

	'==================================
	' Start measurement
	'===================================

	'Convert dimensions into cm
	CArea = CDbl(ContArea) / 100
	CLength = CDbl(ContLength) / 10

	'Set current level
	GPIB.SendString(Keith6220, "OUTP On" & vbCrLf)
	ExcCurr = CDbl(ExciteCurrent)

	If FixedField <> 0 Then
		'PPMS.SetField(FixField,FixFieldRate,1,0) ' Approach: 0 - Linear Approach / 1 - No Overshoot / 2 - Oscillate Mode: 0 - Persistent 1 - Driven
		Do
			PPMS.GetField(field, fieldstate)
			Wait(1)
		Loop While (fieldstate<>1)
	End If

	PPMS.SetTemperature(TarTemp,TarTempRate,0) ' Mode: 0 - fast settle 1 - No overshoot

	Do
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


		averageV = (CDbl(positiveV) - CDbl(negativeV)) / 2

		'Send a request for data point
		'GPIB.SendString(Address, "SYST:COMM:SER:SEND ":DATA:LAT?"" & vbCrLf)

	    '==================================
	    ' Gather state of the PPMS
	    '===================================

		PPMS.GetField(field,fieldstate)
		PPMS.GetTemperature(temp, tempstate)
		pressure = PPMSUtils.GetPPMSChannelData(19)

	    '===================================
	    ' Dump data to file
	    '===================================

		'put stuff in a properly ordered array for output
		d(0) = Timer
		d(1) = temp
		d(2) = field
		d(3) = pressure
		d(4) = CDbl(positiveV)
		d(5) = CDbl(negativeV)
		d(6) = CDbl(averageV)
		d(7) = ExcCurr
		d(8) = CDbl(averageV) / ExcCurr
		d(9) = d(8) * (CArea / CLength)

		'write array to file
		DataFile.WriteLineArray("",d)

		Wait(WaitTime)

	Loop While (tempstate<>1)


End Sub

'#uses "..\Utils\PPMSUtils.obm"
'#uses "AgilentE4980A.obm"

' NOTE: data file manipulation operations (open, setup, write, graph) have been removed from this script.
' This only demonstrates setting up the LCR meter and getting data from it.  -QD

Sub Main
	Debug.Clear

	Dim status As Long
	Dim Result As String

	'Constants
	EpsZero = 8.854187817e-12 'Permitivity of vacuum - do not change
	Pi = 4*Atn(1)
	LCRAddress = 17

	'List of frequencies swept over !!MAKE SURE TO CHANGE THIS LIST IF YOU ALTER IT IN AgilentE4980A.OBM!!
	MaxFreq = 15
	Dim flist(15) As Double
	flist(0) = 20
	flist(1) = 500
	flist(2) = 1000
	flist(3) = 5000
	flist(4) = 10000
	flist(5) = 25000
	flist(6) = 50000
	flist(7) = 75000
	flist(8) = 100000
	flist(9) = 250000
	flist(10) = 500000
	flist(11) = 750000
	flist(12) = 1000000
	flist(13) = 1500000
	flist(14) = 2000000

    '==================================
	' Initialize instrument and configure for desired measurement
	'===================================
	E4980A.Init
	E4980A.FreqSweepMeasurement

	    '==================================
	    ' Grab data
	    '===================================

	    'Send trigger command
		GPIB.SendString(LCRAddress, "TRIG:IMM" & vbCrLf)
		'Must wait a minimum of 2 seconds for the meter to sweep over entire frequency list
		Wait(2)

		'Send a request for data point
		GPIB.SendString(LCRAddress, "FETCh?" & vbCrLf)
		'Don't talk too fast
		Wait(0.005)

		'Retrieve data from instrument
		GPIB.GetString(LCRAddress, Result)

		If Result <> "" Then
			Debug.Print "Result String = " & Result

			'Parse data
			Res = Split(Result,",")
		End If

End Sub

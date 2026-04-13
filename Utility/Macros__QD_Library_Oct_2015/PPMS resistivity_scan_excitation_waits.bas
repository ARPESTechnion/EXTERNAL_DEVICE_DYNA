Sub Main
	Dim I As Double
	For I = 100 To 1000 Step 50
		'The "LPI" command is for scan excitation, but here we just use it to set a fixed current and we use the loop to increment the current
		'below: 25 is the number of averages and 63 is the bitmask describing which channels and PPMS parameters are being recorded, see Resistivity command
		PPMS.SequenceMeasure("LPI "+ CStr(I) + " " + CStr(I)+ " 0 100.000 5000.000 0 100.000 5000.000 0 100.000 5000.000 0 1 25 63 0 10.000 0 0 10.0 0 10.000 0 0 10.0 0 10.000 0 0 10.0 0 10.000 0 0 10.0")
		Wait(5)
End Sub

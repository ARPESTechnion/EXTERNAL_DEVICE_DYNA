Sub fn_Sequence1
	Dim Field As Double

	For Field = 0 To 1000 Step 100
   		MultiVu.SetField(Field,30.0,0,1)   ' ramp to field at 30 Oe/sec, linear mode, leave driven
		WaitFor(2,0,0)					' wait for field
'		Get GPIB data using GPIB.GetString or similar...

	Next Field
	MultiVu.SetField(1000.0,100.0,0,0) 'set field persistent at 1000 Oe
End Sub

Sub Main
   Call fn_Sequence1
End Sub

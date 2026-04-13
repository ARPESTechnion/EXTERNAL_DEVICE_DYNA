Sub fn_test
   Dim Dir1 As Long
   Dim spacing As Double
   Dim B_start As Double
   Dim B_end As Double
   Dim rate As Double
   Dim state As Long
   Dim B As Double
   Dim num_steps As Integer

   	B_start = 0.0                        		'USER PUTS PARAMETERS HERE
   	B_end = 1000.0
   	rate = 50.0
   	num_steps = 19

   	increment = (B_end-B_start)/(num_steps-1)   'field step size
   	Dir1 = Abs(B_end-B_start)/(B_end-B_start) 	'tells sign of Scan direction
   	MultiVu.SetField(B_start,100.0,0,1) 		'set initial field, linear, driven, use 100 Oe/sec
   	WaitFor(2,0,0)                        		'wait for field stable
   	MultiVu.SetField(B_end,rate,0,0) 			'start the sweep
	B_step = B_start
   	While Dir1*B_step <= Dir1*B_end
      Do
        Wait 0.01                       'wait and DoEvent lets MultiVu thread do other things
        DoEvents                        '
        MultiVu.GetField(B,state) 'mvseq:test.seq>0001 Scan Temp
      Loop While (Dir1*B < Dir1*B_step) And (state <> 1) 'while still short of next field and not at persistent end state
'
' Do your measurements in this loop; measurement time should be less than (spacing/rate) otherwise there will be missed points!
'
Debug.Print B_step
      B_step = B_step + increment                       'mvseq:test.seq>0003 ENT
   Wend                                  'mvseq:test.seq>0003 ENT
End Sub

Sub Main
   Call fn_test
End Sub

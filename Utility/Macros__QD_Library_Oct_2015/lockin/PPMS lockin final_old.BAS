
'#Uses "..\MVUData\MVUData.cls"

' Program for reading output from a Stanford SR830 lock-in amplifier

Sub Main

   Dim replyStr As String
   Dim errorStr As String
   Dim R As Variant
   Dim Rp As Variant
   Dim returnstg As String
   Dim returnlockin As String
   Dim P(7) As Double

   Dim f1 As New MVUData

   If f1.CreateFile("C:\QdPpms\Data\keeseong\macro\lockin_07012008.dat") Then
		'don't write the header again if file already exists!!!
		f1.WriteHeader("Sax Basic Data File", "Temperature (K),Field (Oe), X (V), Y (V), R (V), Theta (Deg)")
   End If


'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
   PPMS.SetTemperature(1.000000,12.000000,0)
   WaitFor(1+2*0+4*0+8*0,10,0)
   PPMS.SetField(50000.0,100.0,0,0)      'mvseq:RES_Yb3Pt4_06302008.seq>0002 Set Field
   WaitFor(1+2*1+4*0+8*0,300,0)          'mvseq:RES_Yb3Pt4_06302008.seq>0003 Wait For %t
   B1 = 50000.0                          'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
   d1 = (-50000.0-50000.0)/(51-1)        'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
   For iB1 = 1 To (51)                   'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      If iB1 <> 51 Then                  'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
         PPMS.SetField(B1,20.0,0,0)      'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      Else                               'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
         PPMS.SetField(-50000.0,20.0,0,0) 'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      End If                             'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      WaitFor(0,1,0)                     'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      WaitFor(2,0,0)                     'mvseq:RES_Yb3Pt4_06302008.seq>0004 Scan Field
      WaitFor(1+2*0+4*0+8*0,30,0)         'wait for stable temp and 10 sec
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

    I = 0
    Do                       'Repeat the measurement 10 times  (Start)

''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

   PPMS.GetPpmsData(30, returnstg, 1, 0, 0) 'get ppms data
   LCGetData(returnlockin) 'get lockin data

 '  PPMS.SendPpmsCommand("ADVISE 1",replyStr, errorStr,0,0) 'mvseq:mac_seq.seq>0006 Advise

   Debug.Print "." & Split(returnstg, ",")(1)
   Debug.Print "." & Split(returnlockin, ",")(0)

        P(0) =  CDbl(Split(returnstg, ",")(1))
        P(1) =  CDbl(Split(returnstg, ",")(2))
        P(2) =  CDbl(Split(returnstg, ",")(3))
        P(3) =  CDbl(Split(returnlockin, ",")(0))
        P(4) =  CDbl(Split(returnlockin, ",")(1))
        P(5) =  CDbl(Split(returnlockin, ",")(2))
        P(6) =  CDbl(Split(returnlockin, ",")(3))

  f1.WriteLineArray("", P)
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
        I = I+1
	    Wait(10.0)

    Loop Until I > 10                         'Repeat the measurement 10 times  (End)

''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''


      B1 = B1 + d1                       'mvseq:RES_Yb3Pt4_06302008.seq>0008 ENB
   Next iB1                              'mvseq:RES_Yb3Pt4_06302008.seq>0008 ENB

   PPMS.SetTemperature(2.000000,12.000000,0) 'mvseq:RES_Yb3Pt4_06302008.seq>0009 Set Temp
   PPMS.SetField(0.0,100.0,2,0)          'mvseq:RES_Yb3Pt4_06302008.seq>0010 Set Field

End Sub

Public Function LCGetData(ByRef Lockindata As String) As Boolean
	Dim s As String
    Address = 8

	'get a temperature reading from the LS bridge
	If GPIB.SendString(Address, "SNAP?1,2,3,4")<>1 Then
		LCGetData = False
		Exit Function
	End If

	'make sure we don't try to talk too fast!
	Wait(0.005)

	If GPIB.GetString(Address, s)<>1 Then
		LCGetData = False
		Exit Function
	End If

	'convert result to a single float and return it
	Lockindata =  s
	LCGetData = True
End Function

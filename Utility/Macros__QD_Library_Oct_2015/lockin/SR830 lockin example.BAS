
' Program for reading output from a Stanford SR830 lock-in amplifier

Sub Main

   Dim returnlockin As String
   Dim P(4) As Double

'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

   Debug.Clear
   LCGetData(returnlockin) 'get lockin data

   Debug.Print "." & Split(returnlockin, ",")(0)

        P(0) =  CDbl(Split(returnlockin, ",")(0))
        P(1) =  CDbl(Split(returnlockin, ",")(1))
        P(2) =  CDbl(Split(returnlockin, ",")(2))
        P(3) =  CDbl(Split(returnlockin, ",")(3))

' then write this array P() to the open data file

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

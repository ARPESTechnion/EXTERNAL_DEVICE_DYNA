Sub Main
    Dim replyStr As String
    Dim errorStr As String
	Dim volts As Double
	Dim channel As Integer

	channel = 1
   	For volts = -5 To 5 Step 0.10
      PPMS.WaitFor(0,2,0)
      Debug.Print volts
      PPMS.SendPpmsCommand("SIGOUT " + CStr(channel) + " " + CStr(volts),replyStr, errorStr,0,0)
   	Next volts
End Sub

'#uses "Utils\PPMSUtils.obm"

Sub Main
	Debug.Clear

	Dim field As Double
	Dim fieldstate As Long
	Dim temp As Double
	Dim tempstate As Long
	Dim status As Long
	Dim pressure As Double
	Dim position As Double

	PPMS.GetField(field,fieldstate)
	PPMS.GetTemperature(temp, tempstate)
	status = PPMSUtils.GetPPMSChannelData(0)
	pressure = PPMSUtils.GetPPMSChannelData(19)
	position = PPMSUtils.GetPPMSChannelData(3)
	MsgBox("Field: "&CStr(field)&Chr(13)&"Temperature: "&CStr(temp),vbInformation+vbOkOnly,"PPMS results")
End Sub

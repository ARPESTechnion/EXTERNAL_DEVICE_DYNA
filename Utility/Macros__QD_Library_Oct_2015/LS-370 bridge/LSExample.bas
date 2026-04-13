'LSExample.bas
'Example script for using LS bridge

'#Uses "LSBridge.obm"

Sub Main
	Dim result As Single


	Debug.Clear
	Debug.Print "Init result = " & LSBridge.Init

	Debug.Print "Read resistance result = " & LSBridge.ReadRes(result)
	Debug.Print "Resistance = " & result & "Ohms."

	Debug.Print "Read temperature result = " & LSBridge.ReadTemp(result)
	Debug.Print "Temperature = " & result & "K."

	Debug.Print "Set voltage excitation result = " & LSBridge.SetVoltageExcit(V_63uV)

End Sub

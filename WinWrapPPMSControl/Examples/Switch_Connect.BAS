'#Language "WWB-COM"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Instruments\MV_K7001.bas"

Option Explicit

Sub fn_SwitchConnet
    Dim K7001_ResourceName As String  ' K7001 VISA resource

    Debug.Clear
    MV_ClearError

	K7001_ResourceName = MV_K7001_RESOURCE
	If Not K7001_Connect(K7001_ResourceName) Then GoTo Fail             'mvseq:Switch_Connect.seq(1)>0001 Connect to Switch
    If Not K7001_OpenAll() Then GoTo Fail                               'mvseq:Switch_Connect.seq(1)>0002 Open All Channels

Fail:
    MV_Log "[MACRO][HALL-ETOR][FAIL] " & MV_LastError

Cleanup:
    On Error Resume Next
    Call K7001_OpenAll()
    Call K7001_Disconnect()
    On Error GoTo 0
End Sub


Sub Main
	   Call fn_SwitchConnet
End Sub

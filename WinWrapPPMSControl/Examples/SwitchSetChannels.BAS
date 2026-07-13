'#Language "WWB-COM"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Instruments\MV_K7001.bas"

Option Explicit

Sub fn_SwitchSetChannels
    Dim K7001_ResourceName As String  ' K7001 VISA resource
    ' Switch logical channel definitions (I+, V+, V-, I-)
    Dim ChA_IPlus As Integer, ChA_VPlus As Integer, ChA_VMinus As Integer, ChA_IMinus As Integer
    Dim ChB_IPlus As Integer, ChB_VPlus As Integer, ChB_VMinus As Integer, ChB_IMinus As Integer
    Dim ChC_IPlus As Integer, ChC_VPlus As Integer, ChC_VMinus As Integer, ChC_IMinus As Integer
    Dim ChD_IPlus As Integer, ChD_VPlus As Integer, ChD_VMinus As Integer, ChD_IMinus As Integer

    ' =========================================================
    ' Defaults - edit for your experiment
    ' =========================================================
    K7001_ResourceName = MV_K7001_RESOURCE

    ChA_IPlus = 1: ChA_VPlus = 2: ChA_VMinus = 3: ChA_IMinus = 4
    ChB_IPlus = 4: ChB_VPlus = 2: ChB_VMinus = 3: ChB_IMinus = 1
    ChC_IPlus = 1: ChC_VPlus = 5: ChC_VMinus = 6: ChC_IMinus = 4
    ChD_IPlus = 4: ChD_VPlus = 5: ChD_VMinus = 6: ChD_IMinus = 1

    Debug.Clear
    MV_ClearError

    MV_Log "[MACRO][HALL-ETOR] Connecting to Switch and Seting channels"

  '  If Not K7001_Connect(K7001_ResourceName) Then GoTo Fail              'mvseq:fn_SwitchSetChannels.seq(1)>0001 Connect to swicth
  '  If Not K7001_OpenAll() Then GoTo Fail                                'mvseq:fn_SwitchSetChannels.seq(1)>0002 Open All
	Call K7001_LoadDefaultMappings
    If Not K7001_DefineChannel("A", ChA_IPlus, ChA_VPlus, ChA_VMinus, ChA_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("B", ChB_IPlus, ChB_VPlus, ChB_VMinus, ChB_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("C", ChC_IPlus, ChC_VPlus, ChC_VMinus, ChC_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("D", ChD_IPlus, ChD_VPlus, ChD_VMinus, ChD_IMinus) Then GoTo Fail
    Call K7001_PrintMappings()


	MV_Log "[MACRO][Switch-Set] Completed successfully"

Fail:
    MV_Log "[MACRO][Switch-Set][FAIL] " & MV_LastError

End Sub


Sub Main
	   Call fn_SwitchSetChannels
End Sub

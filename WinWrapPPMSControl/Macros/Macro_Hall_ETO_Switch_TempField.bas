'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Instruments\MV_K7001.bas"

Option Explicit

Public Sub Macro_Run_Hall_ETO_Switch_TempField()
    ' =========================================================
    ' Measurement Configuration - edit these values
    ' =========================================================
    Dim Temp_Start_K          As Double  ' Outer loop: temperature start (K)
    Dim Temp_End_K            As Double  ' Outer loop: temperature end (K)
    Dim Temp_Steps            As Long    ' Outer loop: number of temperature points (linear)
    Dim Temp_Rate_K_per_min   As Double  ' Temperature ramp rate (K/min)
    Dim Temp_Set_Mode         As Long    ' DynaCool temperature mode: 0=Fast Settle, 1=No Overshoot

    Dim Field_Start_Oe        As Double  ' Inner loop: in-plane field start (Oe)
    Dim Field_End_Oe          As Double  ' Inner loop: in-plane field end (Oe)
    Dim Field_Steps           As Long    ' Inner loop: number of field points (linear)
    Dim Field_Rate_Oe_per_s   As Double  ' In-plane field ramp rate (Oe/s)
    Dim Field_Approach_Mode   As Long    ' DynaCool field approach: 0=Linear, 1=No Overshoot, 2=Oscillate

    Dim Wait_Stable_s         As Long    ' WaitFor timeout for temp/field stabilization (s)
    Dim Switch_Settle_s       As Double  ' Optional settle time after each close channel (s)

    ' ---------------------------------------------------------
    ' ETOR user-settable parameters
    ' ---------------------------------------------------------
    Dim ETOR_P03              As Double  ' measurement points per trigger
    Dim ETOR_P05              As Double  ' AC excitation (mA)
    Dim ETOR_P06              As Double  ' Ch1 resistance frequency (Hz)
    '                                      Ch1: 0.436  1.526  3.052  9.155  18.311  33.569  70.190  128.174  177.002
    '                                      Ch2: 0.509  1.017  6.104  12.207  15.259  21.362  57.983  143.433  186.157
    Dim ETOR_P07              As Double  ' averaging time per point (s)

    ' ---------------------------------------------------------
    ' Instrument + output configuration
    ' ---------------------------------------------------------
    Dim K7001_ResourceName    As String  ' K7001 VISA resource
    Dim BaseFolder            As String  ' Output folder for ETODF
    Dim RunPrefix             As String  ' Output filename prefix

    ' Switch logical channel definitions (I+, V+, V-, I-)
    ' For now this follows the example exactly.
    Dim ChA_IPlus As Integer, ChA_VPlus As Integer, ChA_VMinus As Integer, ChA_IMinus As Integer
    Dim ChB_IPlus As Integer, ChB_VPlus As Integer, ChB_VMinus As Integer, ChB_IMinus As Integer
    Dim ChC_IPlus As Integer, ChC_VPlus As Integer, ChC_VMinus As Integer, ChC_IMinus As Integer
    Dim ChD_IPlus As Integer, ChD_VPlus As Integer, ChD_VMinus As Integer, ChD_IMinus As Integer

    ' =========================================================
    ' Defaults - edit for your experiment
    ' =========================================================
    Temp_Start_K = 300#
    Temp_End_K = 10#
    Temp_Steps = 30
    Temp_Rate_K_per_min = 10#
    Temp_Set_Mode = 0

    Field_Start_Oe = -10000#
    Field_End_Oe = 10000#
    Field_Steps = 81
    Field_Rate_Oe_per_s = 50#
    Field_Approach_Mode = 0

    Wait_Stable_s = 0
    Switch_Settle_s = 0.05

    ETOR_P03 = 1        ' 1 measurement point per trigger
    ETOR_P05 = 0.01     ' AC excitation = 0.01 mA (10 uA)
    ETOR_P06 = 128.1738 ' Ch1 Resistance frequency = 128.174 Hz (from ETO.ini)
    ETOR_P07 = 4.6      ' averaging time = 4.6 s per point

    K7001_ResourceName = MV_K7001_RESOURCE
    BaseFolder = "C:\QdDynacool\Data\ETO\"
    RunPrefix = "HallSwitchETOR"

    ChA_IPlus = 1: ChA_VPlus = 2: ChA_VMinus = 3: ChA_IMinus = 4
    ChB_IPlus = 4: ChB_VPlus = 2: ChB_VMinus = 3: ChB_IMinus = 1
    ChC_IPlus = 1: ChC_VPlus = 5: ChC_VMinus = 6: ChC_IMinus = 4
    ChD_IPlus = 4: ChD_VPlus = 5: ChD_VMinus = 6: ChD_IMinus = 1

    ' =========================================================
    ' Do not edit below this line
    ' =========================================================
    Dim iT As Long
    Dim iB As Long
    Dim nTemps As Long
    Dim nFields As Long
    Dim dT As Double
    Dim dB As Double
    Dim tSet As Double
    Dim bSet As Double
    Dim etoDataFile As String
    Dim etorCmd As String
    Dim ts As String

    On Error GoTo EH
    Debug.Clear
    MV_ClearError

    MV_Log "[MACRO][HALL-ETOR] Starting Hall switch ETOR macro"

    If Temp_Steps < 1 Then
        MV_SetError "Temp_Steps must be >= 1"
        GoTo Fail
    End If
    If Field_Steps < 1 Then
        MV_SetError "Field_Steps must be >= 1"
        GoTo Fail
    End If

    nTemps = Temp_Steps
    nFields = Field_Steps

    If nTemps = 1 Then
        dT = 0#
    Else
        dT = (Temp_End_K - Temp_Start_K) / CDbl(nTemps - 1)
    End If

    If nFields = 1 Then
        dB = 0#
    Else
        dB = (Field_End_Oe - Field_Start_Oe) / CDbl(nFields - 1)
    End If

    If Not K7001_Connect(K7001_ResourceName) Then GoTo Fail
    If Not K7001_OpenAll() Then GoTo Fail

    If Not K7001_DefineChannel("A", ChA_IPlus, ChA_VPlus, ChA_VMinus, ChA_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("B", ChB_IPlus, ChB_VPlus, ChB_VMinus, ChB_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("C", ChC_IPlus, ChC_VPlus, ChC_VMinus, ChC_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("D", ChD_IPlus, ChD_VPlus, ChD_VMinus, ChD_IMinus) Then GoTo Fail

    Call K7001_PrintMappings()

    etorCmd = "ETOR 'C:\QdDynacool\default_ETO.qmap' 0 3 " & _
              CStr(ETOR_P03) & " 0 " & CStr(ETOR_P05) & " " & CStr(ETOR_P06) & " " & _
              CStr(ETOR_P07) & " 1 1 0 0 0 0"

    ts = Format$(Now, "yyyymmdd_hhnnss")
    etoDataFile = BaseFolder & RunPrefix & "_" & ts & ".dat"

    DynaCool.SequenceMeasure "ETODF '" & etoDataFile & "' 0 Untitled"         'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0001 ETODF

    DynaCool.SetTemperature(Temp_Start_K, Temp_Rate_K_per_min, Temp_Set_Mode) 'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0002 Set Temp (initial)
    DynaCool.SetField(Field_Start_Oe, Field_Rate_Oe_per_s, Field_Approach_Mode, 0) 'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0003 Set Field (initial)
    DynaCool.WaitFor(1+2*1, Wait_Stable_s, 0)                                 'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0004 Wait For T and B stable

    For iT = 1 To nTemps
        tSet = Temp_Start_K + CDbl(iT - 1) * dT

        DynaCool.SetTemperature(tSet, Temp_Rate_K_per_min, Temp_Set_Mode) 'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0005 Set Temp
        DynaCool.WaitFor(1, Wait_Stable_s, 0)                             'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0006 Wait For T stable

        For iB = 1 To nFields
            bSet = Field_Start_Oe + CDbl(iB - 1) * dB

            DynaCool.SetField(bSet, Field_Rate_Oe_per_s, Field_Approach_Mode, 0) 'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0007 Set Field
            DynaCool.WaitFor(2, Wait_Stable_s, 0)                               'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0008 Wait For B stable


            If Not K7001_CloseChannel("A") Then GoTo Fail
            If Switch_Settle_s > 0# Then MV_WaitSeconds Switch_Settle_s
            DynaCool.SequenceMeasure "ETOLC 'CHANNEL=A'"                        'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0009 ETOLC Channel A
            DynaCool.SequenceMeasure etorCmd                                     'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0010 ETOR Channel A

            If Not K7001_CloseChannel("B") Then GoTo Fail
            If Switch_Settle_s > 0# Then MV_WaitSeconds Switch_Settle_s
            DynaCool.SequenceMeasure "ETOLC 'CHANNEL=B'"                        'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0011 ETOLC Channel B
            DynaCool.SequenceMeasure etorCmd                                     'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0012 ETOR Channel B

            If Not K7001_CloseChannel("C") Then GoTo Fail
            If Switch_Settle_s > 0# Then MV_WaitSeconds Switch_Settle_s
            DynaCool.SequenceMeasure "ETOLC 'CHANNEL=C'"                        'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0013 ETOLC Channel C
            DynaCool.SequenceMeasure etorCmd                                     'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0014 ETOR Channel C

            If Not K7001_CloseChannel("D") Then GoTo Fail
            If Switch_Settle_s > 0# Then MV_WaitSeconds Switch_Settle_s
            DynaCool.SequenceMeasure "ETOLC 'CHANNEL=D'"                        'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0015 ETOLC Channel D
            DynaCool.SequenceMeasure etorCmd                                     'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0016 ETOR Channel D

            If Not K7001_OpenAll() Then GoTo Fail                                'mvseq:Macro_Hall_ETO_Switch_TempField.seq(1)>0017 Open All
        Next iB
    Next iT

    MV_Log "[MACRO][HALL-ETOR] Completed successfully"
    GoTo Cleanup

EH:
    MV_SetError "Macro_Run_Hall_ETO_Switch_TempField runtime error: " & Err.Description

Fail:
    DynaCool.SequenceMeasure "ETOLC 'RUN_END,status=FAIL'"
    MV_Log "[MACRO][HALL-ETOR][FAIL] " & MV_LastError

Cleanup:
    On Error Resume Next
    Call K7001_OpenAll()
    Call K7001_Disconnect()
    On Error GoTo 0
End Sub

'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Instruments\MV_K7001.bas"
'#Uses "..\Instruments\MV_K2450_Hall.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Instruments\MV_K2450_LiveLog.bas"

Option Explicit

' ============================================================
' Macro_Hall_K2450_Switch_TempField
'
' Hall-effect switching measurement using a Keithley 2450
' DC current source instead of the ETO AC lock-in.
'
' Outer loop: Temperature
' Inner loop: Magnetic field
' Per field point: each channel in ChannelList_Csv is connected
'   in turn via the K7001 switch matrix and a single V/I/R
'   reading is taken with the K2450.
'
' Results are written to a single MultiVu-readable .dat file
' using the CHANNEL_WIDE schema so every channel has its own
' independently selectable Y-axis trace in the MultiVu plot.
' ============================================================

Public Sub Macro_Run_Hall_K2450_Switch_TempField()

    ' =========================================================
    ' Measurement Configuration  -  edit these values
    ' =========================================================

    ' --- Temperature outer loop ---
    Dim Temp_Start_K        As Double  ' Start temperature (K)            = 300
    Dim Temp_End_K          As Double  ' End temperature (K)              = 10
    Dim Temp_Steps          As Long    ' Number of temperature points     = 30
    Dim Temp_Rate_K_per_min As Double  ' Ramp rate (K/min)                = 10
    Dim Temp_Set_Mode       As Long    ' 0 = Fast Settle, 1 = No Overshoot = 0

    ' --- Magnetic field inner loop ---
    Dim Field_Start_Oe      As Double  ' Start field (Oe)                 = -10000
    Dim Field_End_Oe        As Double  ' End field (Oe)                   = 10000
    Dim Field_Steps         As Long    ' Number of field points           = 81
    Dim Field_Rate_Oe_per_s As Double  ' Ramp rate (Oe/s)                 = 50
    Dim Field_Approach_Mode As Long    ' 0 = Linear, 1 = No Overshoot, 2 = Oscillate = 0

    ' --- Timing ---
    Dim Wait_Stable_s       As Long    ' WaitFor stabilization timeout (s); 0 = immediate = 0
    Dim Switch_Settle_s     As Double  ' Relay settle time after K7001 close (s) = 0.05

    ' --- Channel list ---
    '   Comma-separated logical channel names.
    '   Each name must be registered below with K7001_DefineChannel.
    Dim ChannelList_Csv     As String  ' e.g. "A,B,C,D" or "ChLeft,ChRight"

    ' --- K2450 global defaults (applied to all channels unless overridden) ---
    Dim Source_mA     As Double  ' DC source current (mA)                  = 0.1
    Dim Compliance_V  As Double  ' Compliance voltage (V)                  = 5.0
    Dim Nplc          As Double  ' Integration time (power line cycles)    = 1.0
    Dim AvgCount      As Integer ' Number of averages per reading          = 5
    Dim Settle_s      As Double  ' Settle time after output-on (s)         = 0.05
    Dim Use4Wire      As Boolean ' True = 4-wire (RSEN), False = 2-wire    = True
    Dim AutoRange     As Boolean ' True = auto range voltage measurement    = True

    ' --- Per-channel overrides (empty string = use global default above) ---
    '   Values must be in the same order as ChannelList_Csv.
    '   Any entry that is blank or whitespace falls back to the global default.
    Dim PerCh_Source_mA_Csv    As String  ' e.g. "0.1,0.2,0.1,0.1"  or ""
    Dim PerCh_Compliance_V_Csv As String  ' e.g. ""
    Dim PerCh_Nplc_Csv         As String  ' e.g. ""
    Dim PerCh_AvgCount_Csv     As String  ' e.g. ""
    Dim PerCh_Settle_s_Csv     As String  ' e.g. "0.05,0.1,0.05,0.05" or ""

    ' --- Output policy ---
    '   "KEEP_ON"           : K2450 output stays on while all channels are measured.
    '                         Reduces reconfiguration overhead; be aware that the
    '                         source is live during relay switching.
    '   "TOGGLE_PER_POINT"  : K2450 output is turned off before switching channels
    '                         and turned on again immediately before the measurement.
    Dim OutputPolicy    As String  ' "KEEP_ON" or "TOGGLE_PER_POINT"

    ' --- Instruments and output files ---
    Dim K7001_ResourceName As String  ' VISA resource for switch matrix = MV_K7001_RESOURCE
    Dim K2450_ResourceName As String  ' VISA resource for SMU          = MV_K2450_RESOURCE
    Dim BaseFolder         As String  ' Output folder (trailing backslash) = "C:\QdDynacool\Data\ETO\"
    Dim RunPrefix          As String  ' Filename prefix = "HallK2450Switch"

    ' --- K7001 channel pin mappings (I+, V+, V-, I-) ---
    '   Add or remove Dim pairs to match your wiring.
    '   Channel names must match entries in ChannelList_Csv.
    Dim ChA_IPlus As Integer, ChA_VPlus As Integer, ChA_VMinus As Integer, ChA_IMinus As Integer
    Dim ChB_IPlus As Integer, ChB_VPlus As Integer, ChB_VMinus As Integer, ChB_IMinus As Integer
    Dim ChC_IPlus As Integer, ChC_VPlus As Integer, ChC_VMinus As Integer, ChC_IMinus As Integer
    Dim ChD_IPlus As Integer, ChD_VPlus As Integer, ChD_VMinus As Integer, ChD_IMinus As Integer

    ' =========================================================
    ' Default values  -  edit for your experiment
    ' =========================================================
    Temp_Start_K        = 300#
    Temp_End_K          = 10#
    Temp_Steps          = 30
    Temp_Rate_K_per_min = 10#
    Temp_Set_Mode       = 0

    Field_Start_Oe      = -10000#
    Field_End_Oe        = 10000#
    Field_Steps         = 81
    Field_Rate_Oe_per_s = 50#
    Field_Approach_Mode = 0

    Wait_Stable_s   = 0
    Switch_Settle_s = 0.05

    ChannelList_Csv = "A,B,C,D"

    Source_mA    = 0.1
    Compliance_V = 5.0
    Nplc         = 1.0
    AvgCount     = 5
    Settle_s     = 0.05
    Use4Wire     = True
    AutoRange    = True

    PerCh_Source_mA_Csv    = ""
    PerCh_Compliance_V_Csv = ""
    PerCh_Nplc_Csv         = ""
    PerCh_AvgCount_Csv     = ""
    PerCh_Settle_s_Csv     = ""

    OutputPolicy = "KEEP_ON"   ' or "TOGGLE_PER_POINT"

    K7001_ResourceName = MV_K7001_RESOURCE
    K2450_ResourceName = MV_K2450_RESOURCE
    BaseFolder = "C:\QdDynacool\Data\ETO\"
    RunPrefix  = "HallK2450Switch"

    ChA_IPlus = 1: ChA_VPlus = 2: ChA_VMinus = 3: ChA_IMinus = 4
    ChB_IPlus = 4: ChB_VPlus = 2: ChB_VMinus = 3: ChB_IMinus = 1
    ChC_IPlus = 1: ChC_VPlus = 5: ChC_VMinus = 6: ChC_IMinus = 4
    ChD_IPlus = 4: ChD_VPlus = 5: ChD_VMinus = 6: ChD_IMinus = 1

    ' =========================================================
    ' Do not edit below this line
    ' =========================================================
    Dim iT As Long, iB As Long
    Dim nTemps As Long, nFields As Long
    Dim dT As Double, dB As Double
    Dim tSet As Double, bSet As Double
    Dim ts As String
    Dim datFilePath As String

    ' Channel list parsing
    Dim chNames()   As String   ' logical channel names from ChannelList_Csv
    Dim nCh         As Long
    Dim iCh         As Long

    ' Per-channel config arrays (indexed 0..nCh-1)
    Dim chSource_A()   As Double
    Dim chComply_V()   As Double
    Dim chNplc()       As Double
    Dim chAvgCount()   As Long
    Dim chSettle_s()   As Double

    ' Per-channel CSV override tokens
    Dim tokSrc()    As String
    Dim tokCmpl()   As String
    Dim tokNplc()   As String
    Dim tokAvg()    As String
    Dim tokSettle() As String

    ' Measurement state
    Dim measV As Double, measI As Double, measR As Double
    Dim statusTxt As String
    Dim policyUpper As String

    ' Config-change tracking (avoid redundant *RST / SCPI writes)
    Dim lastSource_A   As Double
    Dim lastComply_V   As Double
    Dim lastNplc       As Double
    Dim lastAvgCount   As Long
    Dim lastUse4Wire   As Boolean
    Dim lastAutoRange  As Boolean
    Dim needReconfig   As Boolean

    On Error GoTo EH
    Debug.Clear
    MV_ClearError

    MV_Log "[MACRO][HALL-K2450] Starting Hall switch K2450 macro"

    ' -------------------------------------------------------
    ' Validate user parameters
    ' -------------------------------------------------------
    If Temp_Steps < 1 Then
        MV_SetError "Temp_Steps must be >= 1"
        GoTo Fail
    End If
    If Field_Steps < 1 Then
        MV_SetError "Field_Steps must be >= 1"
        GoTo Fail
    End If
    If Source_mA = 0# Then
        MV_SetError "Source_mA must not be zero"
        GoTo Fail
    End If
    If Abs(Source_mA) > 1050# Then
        MV_SetError "Source_mA exceeds K2450 max of 1050 mA"
        GoTo Fail
    End If
    If Compliance_V <= 0# Or Compliance_V > 210# Then
        MV_SetError "Compliance_V must be in range (0, 210] V"
        GoTo Fail
    End If
    If Nplc < 0.01 Or Nplc > 20# Then
        MV_SetError "Nplc must be in range [0.01, 20]"
        GoTo Fail
    End If
    If AvgCount < 1 Or AvgCount > 100 Then
        MV_SetError "AvgCount must be in range [1, 100]"
        GoTo Fail
    End If
    If Settle_s < 0# Then
        MV_SetError "Settle_s must be >= 0"
        GoTo Fail
    End If
    If Switch_Settle_s < 0# Then
        MV_SetError "Switch_Settle_s must be >= 0"
        GoTo Fail
    End If

    policyUpper = UCase$(Trim$(OutputPolicy))
    If policyUpper <> "KEEP_ON" And policyUpper <> "TOGGLE_PER_POINT" Then
        MV_SetError "OutputPolicy must be 'KEEP_ON' or 'TOGGLE_PER_POINT', got: " & OutputPolicy
        GoTo Fail
    End If

    ' -------------------------------------------------------
    ' Parse channel list
    ' -------------------------------------------------------
    If Trim$(ChannelList_Csv) = "" Then
        MV_SetError "ChannelList_Csv must not be empty"
        GoTo Fail
    End If

    chNames = Split(ChannelList_Csv, ",")
    nCh = UBound(chNames) - LBound(chNames) + 1
    If nCh < 1 Then
        MV_SetError "ChannelList_Csv produced no channels"
        GoTo Fail
    End If

    ' Trim whitespace from each name and re-index to 0-based
    Dim chNamesNorm() As String
    ReDim chNamesNorm(0 To nCh - 1)
    For iCh = 0 To nCh - 1
        chNamesNorm(iCh) = Trim$(chNames(LBound(chNames) + iCh))
        If chNamesNorm(iCh) = "" Then
            MV_SetError "ChannelList_Csv contains an empty channel name at position " & CStr(iCh)
            GoTo Fail
        End If
    Next iCh

    ' -------------------------------------------------------
    ' Build per-channel config arrays using global defaults +
    ' optional per-channel CSV overrides.
    ' -------------------------------------------------------
    ReDim chSource_A(0 To nCh - 1)
    ReDim chComply_V(0 To nCh - 1)
    ReDim chNplc(0 To nCh - 1)
    ReDim chAvgCount(0 To nCh - 1)
    ReDim chSettle_s(0 To nCh - 1)

    ' Tokenise override CSVs (may be fewer tokens than channels — extras fall back to global)
    If Trim$(PerCh_Source_mA_Csv)    <> "" Then tokSrc    = Split(PerCh_Source_mA_Csv,    ",")
    If Trim$(PerCh_Compliance_V_Csv) <> "" Then tokCmpl   = Split(PerCh_Compliance_V_Csv, ",")
    If Trim$(PerCh_Nplc_Csv)         <> "" Then tokNplc   = Split(PerCh_Nplc_Csv,         ",")
    If Trim$(PerCh_AvgCount_Csv)     <> "" Then tokAvg    = Split(PerCh_AvgCount_Csv,      ",")
    If Trim$(PerCh_Settle_s_Csv)     <> "" Then tokSettle = Split(PerCh_Settle_s_Csv,      ",")

    Dim tokIdx As Long
    Dim sTok As String
    Dim cTok As String
    Dim nTok As String
    Dim aTok As String
    Dim stTok As String
    For iCh = 0 To nCh - 1
        tokIdx = iCh + LBound(chNames)   ' same offset as original Split array

        ' Source_mA
        chSource_A(iCh) = Source_mA / 1000#
        If IsInitialized_Str(tokSrc) Then
            If tokIdx <= UBound(tokSrc) Then
                sTok = Trim$(tokSrc(tokIdx))
                If sTok <> "" Then chSource_A(iCh) = CDbl(sTok) / 1000#
            End If
        End If

        ' Compliance_V
        chComply_V(iCh) = Compliance_V
        If IsInitialized_Str(tokCmpl) Then
            If tokIdx <= UBound(tokCmpl) Then
                cTok = Trim$(tokCmpl(tokIdx))
                If cTok <> "" Then chComply_V(iCh) = CDbl(cTok)
            End If
        End If

        ' Nplc
        chNplc(iCh) = Nplc
        If IsInitialized_Str(tokNplc) Then
            If tokIdx <= UBound(tokNplc) Then
                nTok = Trim$(tokNplc(tokIdx))
                If nTok <> "" Then chNplc(iCh) = CDbl(nTok)
            End If
        End If

        ' AvgCount
        chAvgCount(iCh) = CLng(AvgCount)
        If IsInitialized_Str(tokAvg) Then
            If tokIdx <= UBound(tokAvg) Then
                aTok = Trim$(tokAvg(tokIdx))
                If aTok <> "" Then chAvgCount(iCh) = CLng(CDbl(aTok))
            End If
        End If

        ' Settle_s
        chSettle_s(iCh) = Settle_s
        If IsInitialized_Str(tokSettle) Then
            If tokIdx <= UBound(tokSettle) Then
                stTok = Trim$(tokSettle(tokIdx))
                If stTok <> "" Then chSettle_s(iCh) = CDbl(stTok)
            End If
        End If
    Next iCh

    ' -------------------------------------------------------
    ' Temperature / field loop setup
    ' -------------------------------------------------------
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

    ' -------------------------------------------------------
    ' Connect instruments
    ' -------------------------------------------------------
    If Not K7001_Connect(K7001_ResourceName) Then GoTo Fail
    If Not K7001_OpenAll() Then GoTo Fail

    ' Register channels — add more as needed for your probe
    If Not K7001_DefineChannel("A", ChA_IPlus, ChA_VPlus, ChA_VMinus, ChA_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("B", ChB_IPlus, ChB_VPlus, ChB_VMinus, ChB_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("C", ChC_IPlus, ChC_VPlus, ChC_VMinus, ChC_IMinus) Then GoTo Fail
    If Not K7001_DefineChannel("D", ChD_IPlus, ChD_VPlus, ChD_VMinus, ChD_IMinus) Then GoTo Fail
    Call K7001_PrintMappings()

    If Not K2450_Connect(K2450_ResourceName) Then GoTo Fail
    ' Initial config: use global defaults; per-channel config applied inside the loop
    If Not K2450_ConfigCurrentSource(Source_mA / 1000#, Compliance_V, Nplc, CLng(AvgCount), Use4Wire, AutoRange) Then GoTo Fail
    lastSource_A  = Source_mA / 1000#
    lastComply_V  = Compliance_V
    lastNplc      = Nplc
    lastAvgCount  = CLng(AvgCount)
    lastUse4Wire  = Use4Wire
    lastAutoRange = AutoRange

    ' -------------------------------------------------------
    ' Create output file
    ' -------------------------------------------------------
    ts = Format$(Now, "yyyymmdd_hhnnss")
    datFilePath = BaseFolder & RunPrefix & "_" & ts & ".dat"

    If Not K2450_LogInitWide(datFilePath, RunPrefix & " " & ts, chNamesNorm) Then GoTo Fail

    ' -------------------------------------------------------
    ' Initial set-point and stabilisation
    ' -------------------------------------------------------
    DynaCool.SetTemperature(Temp_Start_K, Temp_Rate_K_per_min, Temp_Set_Mode) 'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0001 Set Temp (initial)
    DynaCool.SetField(Field_Start_Oe, Field_Rate_Oe_per_s, Field_Approach_Mode, 0) 'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0002 Set Field (initial)
    DynaCool.WaitFor(1 + 2 * 1, Wait_Stable_s, 0)                           'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0003 Wait T+B stable

    ' For KEEP_ON: turn output on once and leave it on
    If policyUpper = "KEEP_ON" Then
        If Not K2450_OutputOn() Then GoTo Fail
    End If

    ' -------------------------------------------------------
    ' Temperature × Field sweep
    ' -------------------------------------------------------
    For iT = 1 To nTemps
        tSet = Temp_Start_K + CDbl(iT - 1) * dT

        DynaCool.SetTemperature(tSet, Temp_Rate_K_per_min, Temp_Set_Mode) 'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0004 Set Temp
        DynaCool.WaitFor(1, Wait_Stable_s, 0)                             'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0005 Wait T stable

        For iB = 1 To nFields
            bSet = Field_Start_Oe + CDbl(iB - 1) * dB

            DynaCool.SetField(bSet, Field_Rate_Oe_per_s, Field_Approach_Mode, 0) 'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0006 Set Field
            DynaCool.WaitFor(2, Wait_Stable_s, 0)                               'mvseq:Macro_Hall_K2450_Switch_TempField.seq(1)>0007 Wait B stable

            ' --- Per-channel measurement loop ---
            For iCh = 0 To nCh - 1

                ' Apply K2450 config if it differs from last applied config
                needReconfig = (chSource_A(iCh) <> lastSource_A) Or _
                               (chComply_V(iCh) <> lastComply_V)  Or _
                               (chNplc(iCh)     <> lastNplc)      Or _
                               (chAvgCount(iCh) <> lastAvgCount)  Or _
                               (Use4Wire        <> lastUse4Wire)   Or _
                               (AutoRange       <> lastAutoRange)

                If needReconfig Then
                    ' KEEP_ON: output stays on, reconfigure without *RST output disruption;
                    ' TOGGLE_PER_POINT: output is cycled anyway, so full reset is safe.
                    ' Either way K2450_ConfigCurrentSource handles output state.
                    If policyUpper = "KEEP_ON" Then
                        ' Turn off briefly for safe reconfiguration, then back on
                        If Not K2450_OutputOff() Then GoTo Fail
                    End If
                    If Not K2450_ConfigCurrentSource(chSource_A(iCh), chComply_V(iCh), chNplc(iCh), chAvgCount(iCh), Use4Wire, AutoRange) Then GoTo Fail
                    lastSource_A  = chSource_A(iCh)
                    lastComply_V  = chComply_V(iCh)
                    lastNplc      = chNplc(iCh)
                    lastAvgCount  = chAvgCount(iCh)
                    lastUse4Wire  = Use4Wire
                    lastAutoRange = AutoRange
                    If policyUpper = "KEEP_ON" Then
                        If Not K2450_OutputOn() Then GoTo Fail
                    End If
                End If

                ' For TOGGLE_PER_POINT: ensure output is off before relay switch
                If policyUpper = "TOGGLE_PER_POINT" Then
                    If K2450_IsOutputOn() Then
                        If Not K2450_OutputOff() Then GoTo Fail
                    End If
                End If

                ' Connect the channel via the switch matrix
                If Not K7001_CloseChannel(chNamesNorm(iCh)) Then GoTo Fail
                If Switch_Settle_s > 0# Then MV_WaitSeconds Switch_Settle_s

                ' For TOGGLE_PER_POINT: turn output on just before the measurement
                If policyUpper = "TOGGLE_PER_POINT" Then
                    If Not K2450_OutputOn() Then GoTo Fail
                End If

                ' Measure V, I, R — settle time is per-channel and handled inside
                If Not K2450_MeasureAll(measV, measI, measR, chNamesNorm(iCh), chSettle_s(iCh)) Then
                    statusTxt = "READ_FAIL"
                    measV = -9.9E99
                    measI = -9.9E99
                    measR = -9.9E99
                Else
                    statusTxt = "OK"
                End If

                ' For TOGGLE_PER_POINT: turn output off after measurement
                If policyUpper = "TOGGLE_PER_POINT" Then
                    If Not K2450_OutputOff() Then GoTo Fail
                End If

                ' Log the row — only the active channel's columns are filled
                If Not K2450_LogWidePoint(chNamesNorm(iCh), measV, measI, measR, _
                        "T=" & Format$(DYNA_GetTemperature_K(), "0.000") & ";B=" & Format$(DYNA_GetField_Oe(), "0"), _
                        statusTxt) Then
                    MV_Log "[MACRO][HALL-K2450][WARN] K2450_LogWidePoint returned False for ch " & chNamesNorm(iCh)
                End If

                ' Open all relays before moving to the next channel
                If Not K7001_OpenAll() Then GoTo Fail

            Next iCh   ' channel loop

        Next iB   ' field loop

    Next iT   ' temperature loop

    MV_Log "[MACRO][HALL-K2450] Completed successfully"
    GoTo Cleanup

EH:
    MV_SetError "Macro_Run_Hall_K2450_Switch_TempField runtime error: " & Err.Description

Fail:
    MV_Log "[MACRO][HALL-K2450][FAIL] " & MV_LastError

Cleanup:
    On Error Resume Next
    If policyUpper = "KEEP_ON" Then Call K2450_OutputOff()
    Call K7001_OpenAll()
    Call K2450_LogClose()
    Call K2450_Disconnect(True)
    Call K7001_Disconnect()
    On Error GoTo 0
End Sub

' -------------------------------------------------------
' Helper: returns True when a String array has been
' initialised (i.e. ReDim/Split was called on it).
' In WinWrapBASIC the LBound of an uninitialised dynamic
' array raises error 9, so we catch that.
' -------------------------------------------------------
Private Function IsInitialized_Str(ByRef arr() As String) As Boolean
    On Error Resume Next
    Dim lb As Long
    lb = LBound(arr)
    If Err.Number = 0 Then
        IsInitialized_Str = True
    Else
        IsInitialized_Str = False
    End If
    On Error GoTo 0
End Function

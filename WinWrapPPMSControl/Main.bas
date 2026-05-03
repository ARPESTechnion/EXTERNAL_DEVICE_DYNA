 
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_General.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_LiveLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_IV_PostAnalysis.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_RTPostAnalysis.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_RunWrappers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Sub fn_IP_Loop_Helm_Loop_Bsweep().vb"

Option Explicit

Private Sub PrintStartupDefaults()
    Dim maxFieldG As Double
    Dim maxCurrentPerChA As Double
    maxFieldG = MV_HELM_G_PER_A_TOTAL * MV_HELM_MAX_TOTAL_CURRENT_A
    maxCurrentPerChA = MV_HELM_MAX_TOTAL_CURRENT_A / 2#

    MV_Log "========== WinWrapPPMSControl Defaults =========="
    MV_Log "mapping_version = " & MV_MAPPING_VERSION
    MV_Log ""
    MV_Log "Helmholtz"
    MV_Log "  G_per_A_total = " & CStr(MV_HELM_G_PER_A_TOTAL)
    MV_Log "  max_current_per_ch_A = " & CStr(maxCurrentPerChA)
    MV_Log "  max_total_current_A = " & CStr(MV_HELM_MAX_TOTAL_CURRENT_A)
    MV_Log "  max_field_G = " & CStr(maxFieldG)
    MV_Log "  max_rate_G_per_s = " & CStr(MV_HELM_MAX_RATE_G_PER_S)
    MV_Log "  default_compliance_V = " & CStr(MV_HelmCompliance_V)
    MV_Log "  default_nplc = " & CStr(MV_HelmNPLC)
    MV_Log ""
    MV_Log "Hall (default preset: Wire Hall Bar 1)"
    MV_Log "  hall_current_mA = " & CStr(MV_HallCurrent_mA)
    MV_Log "  hall_compliance_V = " & CStr(MV_HallCompliance_V)
    MV_Log "  hall_nplc = " & CStr(MV_HallNPLC)
    MV_Log "  hall_filter_count = " & CStr(MV_HallAvgFilter)
    MV_Log "  hall_v_per_g = " & CStr(MV_HallVPerG)
    MV_Log "  hall_offset_V = " & CStr(MV_HallVOffset)
    If Abs(MV_HallVPerG) > MV_HALL_MIN_ABS_V_PER_G Then
        MV_Log "  hall_g_per_v = " & CStr(1# / MV_HallVPerG)
    End If
    MV_Log "=================================================="
End Sub

Private Sub PrintFunctionCatalog()
    MV_Log "========== WinWrapPPMSControl Public API =========="
    MV_Log "Session"
    MV_Log "  MV_InitSession(runName, helmholtzLogPath)"
    MV_Log "  MV_InitSessionWithPostAnalysis(runName, helmholtzLogPath, mergedPostAnalysisPath)"
    MV_Log "  MV_CloseSession()"
    MV_Log ""
    MV_Log "Helmholtz (K2600)"
    MV_Log "  K2600_Connect([resource]) / K2600_Disconnect()"
    MV_Log "  Helm_ConfigSource(compliance_V, nplc)"
    MV_Log "  Helm_SetField(helmholtzField_Oe, rate_G_per_s)"
    MV_Log "  Helm_ValidateHelmholtzField(helmholtzField_Oe, rate_G_per_s)"
    MV_Log "  Helm_WaitStable(timeout_s, [delay_s])"
    MV_Log "  Helm_MeasureResistances_Ohm(nplc, resistanceA_Ohm, resistanceB_Ohm)"
    MV_Log "  Helm_MeasureAndLog()"
    MV_Log ""
    MV_Log "Hall (K2450)"
    MV_Log "  K2450_Connect([resource]) / K2450_Disconnect()"
    MV_Log "  Hall_ApplyPreset(name), Hall_SetCalibration(vPerG, vOffset_V)"
    MV_Log "  Hall_Configure(current_mA, compliance_V, nplc, avgFilter)"
    MV_Log "  Hall_MeasureVoltage_V(), Hall_ComputeField_Oe(voltage_V)"
    MV_Log "  Hall_MeasureAndLog(), Hall_CalibrateOffset_V()"
    MV_Log "  K2450_ConfigCurrentSource(source_A, compliance_V, nplc, avgCount, [use4Wire], [autoRange])"
    MV_Log "  K2450_ConfigVoltageSource(source_V, compliance_A, nplc, avgCount, [use4Wire], [autoRange])"
    MV_Log "  K2450_MeasureVoltage_V([Ch], [settle_s]), K2450_MeasureCurrent_A([Ch], [settle_s]), K2450_MeasureResistance_Ohm([Ch], [settle_s])"
    MV_Log "  K2450_IV_Run(Ch, sourceMode, startVal, maxVal, minVal, stepVal, directionMode, settle_s, [rampToStart], [rampRatePerS], [comment])"
    MV_Log "  Run_K2450_IV_Sweep(datPath, directionMode, startVal, maxVal, minVal, stepVal, sourceSpec, settle_s, nplc, avgCount, rampRatePerS, ...)"
    MV_Log "  K2450_LogInit(datPath, runTitle), K2450_LogPoint([Ch], [comment]), K2450_LogClose()"
    MV_Log ""
    MV_Log "DynaCool + Data"
    MV_Log "  DYNA_GetTemperature_K(), DYNA_GetField_Oe()"
    MV_Log "  DYNA_SetField(field_Oe, rate_Oe_s), DYNA_SetFieldAndWait(field_Oe, rate_Oe_s, timeout_s)"
    MV_Log "  DYNA_SetTempAndWait(targetK, rateKmin, mode, timeout_s), DYNA_WaitForTempFieldStable(timeout_s)"
    MV_Log "  Data_AddComment(text)"
    MV_Log ""
    MV_Log "GPIB"
    MV_Log "  MV_SetDebugMode(True/False)  -- toggles [GPIB][W/Q/R] trace output"
    MV_Log ""
    MV_Log "Run wrappers"
    MV_Log "  Full_MeasureAndLog([tbm_s])"
    MV_Log "  Run_K2450_IV_Live(datPath, runTitle, Ch, sourceMode, startVal, maxVal, minVal, stepVal, directionMode, settle_s, ...)"
    MV_Log "  Run_IVSweepFastTest()"
    MV_Log "  Run_K2600_ZeroOutputCheck()"
    MV_Log "  Run_K2450_IV_SweepFast(datPath, directionMode, startVal, maxVal, minVal, stepVal, sourceSpec, settle_s, nplc, avgCount, rampRatePerS, ...)"
    MV_Log ""
    MV_Log "Post analysis"
    MV_Log "  Merged_InitPostAnalysisLog(filePath), Merged_ClosePostAnalysisLog()"
    MV_Log "  PostAnalysis_AppendMergedRow(etoDataPath, stepIndex, hallMeasured, measureCh1, measureCh2, ...)"
    MV_Log "  PostAnalysis_AppendAfterETO(etoDataPath, hallMeasured, measureCh1, measureCh2, ...)"
    MV_Log "  PostAnalysis_ReplayOldETOScan(etoDataPath, loopCount, helmStart_Oe, helmStep_Oe, ..., dualBlockOrderCh1First)"
    MV_Log "===================================================="
End Sub

Public Sub Test_NoHardware_Limits()
    Dim ok As Boolean
    ok = SelfTest_LimitEnforcement
    If ok Then
        MV_Log "[TEST][LIMITS] PASS"
    Else
        MV_Log "[TEST][LIMITS] FAIL: " & MV_LastError
    End If
End Sub

Public Sub Test_NoHardware_HallMath()
    Dim v As Double
    Dim hallOe As Double

    Call Hall_ApplyPreset("wire hall bar 1")
    Call Hall_SetCalibration(MV_HallVPerG, 0#)

    v = 0.001
    hallOe = Hall_ComputeField_Oe(v)
    MV_Log "[TEST][HALL-MATH] input_V=" & CStr(v) & " => hall_Oe=" & CStr(hallOe)
End Sub

Public Sub Test_NoHardware_Logger()
    Dim path As String
    Dim i As Integer
    Dim t As Double

    path = "C:\QdDynacool\Data\ETO\NoHW_Helmholtz_live_test.dat"

    If Not MV_InitSession("no_hw_logger", path) Then
        MV_Log "[TEST][LOGGER] FAIL init: " & MV_LastError
        Exit Sub
    End If

    For i = 0 To 4
        t = CDbl(i)
        If Not Log_WriteHelmholtzRow(t, _
                                     300# - CDbl(i), _
                                     10# * CDbl(i), _
                                     10# * CDbl(i), _
                                     0.05 * CDbl(i), _
                                     0.05 * CDbl(i), _
                                     MV_HelmCompliance_V, _
                                     MV_HelmNPLC, _
                                     2# + CDbl(i), _
                                     2.5 + CDbl(i), _
                                     MV_HallCurrent_mA, _
                                     MV_HallCompliance_V, _
                                     MV_HallNPLC) Then
            MV_Log "[TEST][LOGGER] FAIL write row " & CStr(i) & ": " & MV_LastError
            Call MV_CloseSession()
            Exit Sub
        End If
    Next

    Call MV_CloseSession()
    MV_Log "[TEST][LOGGER] PASS file=" & path
End Sub

Public Sub Test_NoHardware_K2450_IV_Setpoints()
    Dim points() As Double
    Dim ok As Boolean

    ok = K2450_IV_BuildSetpoints(0#, 1#, -1#, 0.5, K2450_IV_DIR_START_MAX_MIN_START, points)
    If Not ok Then
        MV_Log "[TEST][K2450-IV-POINTS] FAIL dir0: " & MV_LastError
        Exit Sub
    End If
    MV_Log "[TEST][K2450-IV-POINTS] PASS dir0 count=" & CStr(UBound(points) - LBound(points) + 1)

    ok = K2450_IV_BuildSetpoints(0#, 1#, -1#, 0.5, K2450_IV_DIR_START_MIN_MAX_START, points)
    If Not ok Then
        MV_Log "[TEST][K2450-IV-POINTS] FAIL dir1: " & MV_LastError
        Exit Sub
    End If
    MV_Log "[TEST][K2450-IV-POINTS] PASS dir1 count=" & CStr(UBound(points) - LBound(points) + 1)

    ok = K2450_IV_BuildSetpoints(0#, 1#, -1#, 0.5, K2450_IV_DIR_START_MAX_START, points)
    If Not ok Then
        MV_Log "[TEST][K2450-IV-POINTS] FAIL dir2: " & MV_LastError
        Exit Sub
    End If
    MV_Log "[TEST][K2450-IV-POINTS] PASS dir2 count=" & CStr(UBound(points) - LBound(points) + 1)

    ok = K2450_IV_BuildSetpoints(0#, 1#, -1#, 0.5, K2450_IV_DIR_START_MIN_START, points)
    If Not ok Then
        MV_Log "[TEST][K2450-IV-POINTS] FAIL dir3: " & MV_LastError
        Exit Sub
    End If
    MV_Log "[TEST][K2450-IV-POINTS] PASS dir3 count=" & CStr(UBound(points) - LBound(points) + 1)
End Sub

Public Sub Test_NoHardware_K2450_Logger()
    Dim path As String

    path = "C:\QdDynacool\Data\ETO\NoHW_K2450_live_test.dat"

    If Not K2450_LogInit(path, "no_hw_k2450_logger", True) Then
        MV_Log "[TEST][K2450-LOGGER] FAIL init: " & MV_LastError
        Exit Sub
    End If

    If Not K2450_LogPointMeasured("Ch1", "no-hw row", 0.001, 0.0005, 2#, -1, -1, 0, 0#, 0.05, False, "OK") Then
        MV_Log "[TEST][K2450-LOGGER] FAIL write: " & MV_LastError
        Call K2450_LogClose()
        Exit Sub
    End If

    Call K2450_LogClose()
    MV_Log "[TEST][K2450-LOGGER] PASS file=" & path
End Sub

Public Sub Test_NoHardware_PostAnalysisReplay(Optional ByVal etoDataPath As String = "")
    Const CH1_IV_CURR_COL As Long = 9
    Const CH1_IV_VOLT_COL As Long = 10
    Const CH1_AVG_COL As Long = 12
    Const CH1_GAIN_COL As Long = 23

    Const CH2_IV_CURR_COL As Long = 29
    Const CH2_IV_VOLT_COL As Long = 30
    Const CH2_AVG_COL As Long = 32
    Const CH2_GAIN_COL As Long = 43

    Dim helmLogPath As String
    Dim mergedPath As String
    Dim ok As Boolean
    Dim dualBlockOrderCh1First As Boolean

    If etoDataPath = "" Then
        etoDataPath = "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Quantum clock and Rings\RIE Rings\TaS2005LW\AO\Bsweep_2_6_K_-150_3_150_G.dat"
    End If

    helmLogPath = "C:\QdDynacool\Data\ETO\NoHW_Helmholtz_live_for_postanalysis.dat"
    mergedPath = "C:\QdDynacool\Data\ETO\NoHW_PostAnalysisMerged_test.dat"
    dualBlockOrderCh1First = True

    MV_Log "[TEST][POST-REPLAY] Using ETO file: " & etoDataPath
    MV_Log "[TEST][POST-REPLAY] Replaying 101 Helmholtz points from -150 Oe to 150 Oe in 3 Oe steps"
    MV_Log "[TEST][POST-REPLAY] Fitting both channels from separate archived 1023-row blocks"
    If dualBlockOrderCh1First Then
        MV_Log "[TEST][POST-REPLAY] Block order assumption: Ch1 then Ch2"
    Else
        MV_Log "[TEST][POST-REPLAY] Block order assumption: Ch2 then Ch1"
    End If

    If Not MV_InitSessionWithPostAnalysis("no_hw_post_replay", helmLogPath, mergedPath) Then
        MV_Log "[TEST][POST-REPLAY] FAIL init: " & MV_LastError
        Exit Sub
    End If

    ok = PostAnalysis_ReplayOldETOScan(etoDataPath, _
                                       101, _
                                       -150#, _
                                       3#, _
                                       False, _
                                       True, _
                                       True, _
                                       False, _
                                       dualBlockOrderCh1First, _
                                       CH1_IV_CURR_COL, _
                                       CH1_IV_VOLT_COL, _
                                       CH1_AVG_COL, _
                                       CH1_GAIN_COL, _
                                       CH2_IV_CURR_COL, _
                                       CH2_IV_VOLT_COL, _
                                       CH2_AVG_COL, _
                                       CH2_GAIN_COL)

    If ok Then
        MV_Log "[TEST][POST-REPLAY] PASS merged file=" & mergedPath
    Else
        MV_Log "[TEST][POST-REPLAY] FAIL: " & MV_LastError
    End If

    Call MV_CloseSession()
End Sub

Public Sub Test_NoHardware_All()
    MV_Log "===== No-Hardware Smoke Tests ====="
    Call Test_NoHardware_Limits()
    Call Test_NoHardware_HallMath()
    Call Test_NoHardware_Logger()
    Call Test_NoHardware_K2450_IV_Setpoints()
    Call Test_NoHardware_K2450_Logger()
    Call Test_NoHardware_PostAnalysisReplay()
    Call Test_Logger_HeaderCheck()
    Call Test_Sweep_RowPerPoint()
    MV_Log "==================================="
End Sub

Public Sub Test_VISA32_Connection()
    ' Test VISA32 backend connectivity
    ' Note: This test will FAIL if hardware is not present, which is expected.
    ' The test verifies that VISA32.DLL interface is working and connection attempts
    ' are being made via the new VISA backend (not MultiVu.GPIB).
    
    Dim k2600Key As String
    Dim k2450Key As String
    Dim ok As Boolean
    
    MV_Log "========== VISA32 Connection Test =========="
    
    ' Enable debug logging to see VISA calls
    Call MV_SetDebugMode(True)
    
    MV_Log "[VISA32-TEST] Attempting K2600 connection..."
    ok = K2600_Connect()
    If ok Then
        MV_Log "[VISA32-TEST] K2600 successfully connected"
        Call K2600_Disconnect()
        MV_Log "[VISA32-TEST] K2600 disconnected"
    Else
        MV_Log "[VISA32-TEST] K2600 connection FAILED (hardware may not be present): " & MV_LastError
    End If
    
    MV_Log "[VISA32-TEST] Attempting K2450 connection..."
    ok = K2450_Connect()
    If ok Then
        MV_Log "[VISA32-TEST] K2450 successfully connected"
        Call K2450_Disconnect()
        MV_Log "[VISA32-TEST] K2450 disconnected"
    Else
        MV_Log "[VISA32-TEST] K2450 connection FAILED (hardware may not be present): " & MV_LastError
    End If
    
    ' Clean up any open sessions
    Call MV_GPIB_CloseAll()
    
    ' Disable debug logging
    Call MV_SetDebugMode(False)
    
    MV_Log "========== VISA32 Test Complete =========="
End Sub

Public Sub Test_K2600_Connection()
    Dim resourceName As String
    Dim okConnect As Boolean
    Dim idn As String
    Dim q As String

    resourceName = "GPIB0::26::INSTR"

    MV_Log "[TEST][K2600] Connecting to " & resourceName
    okConnect = K2600_Connect(resourceName)
    If okConnect = False Then
        MV_Log "[TEST][K2600] FAIL connect: " & MV_LastError
        Exit Sub
    End If

    If Not MV_GPIB_Query(MV_K2600_Device, "print(1)", q) Then
        MV_Log "[TEST][K2600] FAIL transport probe print(1): " & MV_LastError
        Call K2600_Disconnect()
        Exit Sub
    End If
    MV_Log "[TEST][K2600] probe=" & q

    If Not MV_GPIB_Query(MV_K2600_Device, "print(localnode.model)", idn) Then
        MV_Log "[TEST][K2600] FAIL model query: " & MV_LastError
        Call K2600_Disconnect()
        Exit Sub
    End If
    MV_Log "[TEST][K2600] model=" & idn

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.output)", q) Then
        MV_Log "[TEST][K2600] WARN cannot read smua output state: " & MV_LastError
    Else
        MV_Log "[TEST][K2600] smua.source.output=" & q
    End If

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.output)", q) Then
        MV_Log "[TEST][K2600] WARN cannot read smub output state: " & MV_LastError
    Else
        MV_Log "[TEST][K2600] smub.source.output=" & q
    End If

    Call K2600_Disconnect()
    MV_Log "[TEST][K2600] PASS"
End Sub

Public Sub Test_VISA_K2600_Minimal()
    Dim rm As Object
    Dim inst As Object
    Dim resourceName As String
    Dim response As String

    resourceName = MV_K2600_RESOURCE
    MV_Log "[TEST][VISA] Opening " & resourceName

    On Error Resume Next
    Err.Clear
    Set rm = CreateObject("VISA.GlobalRM")
    If rm Is Nothing Then
        Err.Clear
        Set rm = CreateObject("VISA.ResourceManager")
    End If
    If rm Is Nothing Then
        Err.Clear
        Set rm = CreateObject("VisaComLib.ResourceManager")
    End If
    If rm Is Nothing Then
        Err.Clear
        Set rm = CreateObject("NiVisaCom.NIResourceManager")
    End If
    On Error GoTo EH

    If rm Is Nothing Then
        MV_Log "[TEST][VISA] FAIL resource manager was not created"
        Exit Sub
    End If

    Set inst = rm.Open(resourceName)

    On Error Resume Next
    inst.Timeout = 5000
    On Error GoTo EH

    inst.WriteString "print(1)" & vbLf
    response = Trim$(inst.ReadString())
    MV_Log "[TEST][VISA] probe=" & response

    inst.WriteString "print(localnode.model)" & vbLf
    response = Trim$(inst.ReadString())
    MV_Log "[TEST][VISA] model=" & response

    inst.WriteString "print(smua.source.output)" & vbLf
    response = Trim$(inst.ReadString())
    MV_Log "[TEST][VISA] smua.source.output=" & response

    inst.WriteString "print(smub.source.output)" & vbLf
    response = Trim$(inst.ReadString())
    MV_Log "[TEST][VISA] smub.source.output=" & response

    On Error Resume Next
    inst.Close
    Set inst = Nothing
    Set rm = Nothing
    On Error GoTo 0

    MV_Log "[TEST][VISA] PASS"
    Exit Sub

EH:
    MV_Log "[TEST][VISA] FAIL " & Err.Description
    On Error Resume Next
    If Not inst Is Nothing Then inst.Close
    Set inst = Nothing
    Set rm = Nothing
    On Error GoTo 0
End Sub

Public Sub Test_K2600_VISA_Connection()
    Call Test_VISA_K2600_Minimal()
End Sub

Public Sub Test_Logger_HeaderCheck()
    ' Writes one row to a temp .dat then reads it back to verify
    ' the QD MultiVuDataFile header contains BYAPP, STARTUPAXIS, and [Data].
    Dim path As String
    Dim fileNum As Integer
    Dim lineText As String
    Dim foundByApp As Boolean
    Dim foundStartupAxis As Boolean
    Dim foundData As Boolean

    path = "C:\QdDynacool\Data\ETO\NoHW_HeaderCheck_test.dat"

    If Not MV_InitSession("header_check", path) Then
        MV_Log "[TEST][HEADER] FAIL init: " & MV_LastError
        Exit Sub
    End If

    Call Log_WriteHelmholtzRow(0#, 300#, 0#, 0#, 0#, 0#, _
                               MV_HelmCompliance_V, MV_HelmNPLC, _
                               1#, 1#, MV_HallCurrent_mA, MV_HallCompliance_V, MV_HallNPLC)
    Call MV_CloseSession()

    fileNum = FreeFile
    Open path For Input As #fileNum
    Do While Not EOF(fileNum)
        Line Input #fileNum, lineText
        Dim upLine As String
        upLine = UCase(lineText)
        If InStr(upLine, "BYAPP") > 0 Then foundByApp = True
        If InStr(upLine, "STARTUPAXIS") > 0 Then foundStartupAxis = True
        If InStr(upLine, "[DATA]") > 0 Then foundData = True
    Loop
    Close #fileNum

    If foundByApp And foundStartupAxis And foundData Then
        MV_Log "[TEST][HEADER] PASS  (BYAPP + STARTUPAXIS + [Data] present)"
    Else
        Dim missing As String
        missing = ""
        If Not foundByApp Then missing = missing & "BYAPP "
        If Not foundStartupAxis Then missing = missing & "STARTUPAXIS "
        If Not foundData Then missing = missing & "[Data]"
        MV_Log "[TEST][HEADER] FAIL  missing: " & missing
    End If
End Sub

Public Sub Test_Sweep_RowPerPoint()
    ' Writes 3 fake measurement rows and verifies exactly 3 numeric data
    ' lines appear in the [Data] section (one per sweep point).
    Const ROW_COUNT As Integer = 3
    Dim path As String
    Dim fileNum As Integer
    Dim lineText As String
    Dim inDataSection As Boolean
    Dim dataRows As Integer
    Dim i As Integer
    Dim fc As String

    path = "C:\QdDynacool\Data\ETO\NoHW_SweepRows_test.dat"

    If Not MV_InitSession("sweep_rows", path) Then
        MV_Log "[TEST][SWEEP-ROWS] FAIL init: " & MV_LastError
        Exit Sub
    End If

    For i = 1 To ROW_COUNT
        If Not Log_WriteHelmholtzRow(CDbl(i), 295# + CDbl(i), _
                                     CDbl(i) * 50#, CDbl(i) * 50#, _
                                     0.02 * CDbl(i), 0.02 * CDbl(i), _
                                     MV_HelmCompliance_V, MV_HelmNPLC, _
                                     10# + CDbl(i), 10.5 + CDbl(i), _
                                     MV_HallCurrent_mA, MV_HallCompliance_V, MV_HallNPLC) Then
            MV_Log "[TEST][SWEEP-ROWS] FAIL writing row " & CStr(i) & ": " & MV_LastError
            Call MV_CloseSession()
            Exit Sub
        End If
    Next
    Call MV_CloseSession()

    ' Count data lines: lines after [Data] that start with a digit or minus sign
    inDataSection = False
    dataRows = 0
    fileNum = FreeFile
    Open path For Input As #fileNum
    Do While Not EOF(fileNum)
        Line Input #fileNum, lineText
        lineText = Trim(lineText)
        If UCase(lineText) = "[DATA]" Then
            inDataSection = True
        ElseIf inDataSection And Len(lineText) > 0 Then
            fc = Left(lineText, 1)
            If fc = "-" Or (fc >= "0" And fc <= "9") Then
                dataRows = dataRows + 1
            End If
        End If
    Loop
    Close #fileNum

    If dataRows = ROW_COUNT Then
        MV_Log "[TEST][SWEEP-ROWS] PASS  (" & CStr(dataRows) & " data rows, expected " & CStr(ROW_COUNT) & ")"
    Else
        MV_Log "[TEST][SWEEP-ROWS] FAIL  (found " & CStr(dataRows) & ", expected " & CStr(ROW_COUNT) & ")"
    End If
End Sub

Private Function Test_CountDataRows(ByVal path As String) As Long
    Dim fileNum As Integer
    Dim lineText As String
    Dim inDataSection As Boolean
    Dim rows As Long
    Dim fc As String

    rows = 0
    inDataSection = False
    fileNum = FreeFile

    On Error GoTo EH
    Open path For Input As #fileNum
    Do While Not EOF(fileNum)
        Line Input #fileNum, lineText
        lineText = Trim$(lineText)
        If UCase$(lineText) = "[DATA]" Then
            inDataSection = True
        ElseIf inDataSection And Len(lineText) > 0 Then
            fc = Left$(lineText, 1)
            If fc = "-" Or (fc >= "0" And fc <= "9") Then
                rows = rows + 1
            End If
        End If
    Loop
    Close #fileNum

    Test_CountDataRows = rows
    Exit Function
EH:
    On Error Resume Next
    Close #fileNum
    Test_CountDataRows = 0
End Function

Private Function Test_FileContainsText(ByVal path As String, ByVal token As String) As Boolean
    Dim fileNum As Integer
    Dim lineText As String
    Dim upLine As String
    Dim upToken As String

    Test_FileContainsText = False
    fileNum = FreeFile
    upToken = UCase$(token)

    On Error GoTo EH
    Open path For Input As #fileNum
    Do While Not EOF(fileNum)
        Line Input #fileNum, lineText
        upLine = UCase$(lineText)
        If InStr(upLine, upToken) > 0 Then
            Test_FileContainsText = True
            Exit Do
        End If
    Loop
    Close #fileNum
    Exit Function
EH:
    On Error Resume Next
    Close #fileNum
End Function

Public Sub Test_K2450_IV_Live_Hardware()
    Dim path As String
    Dim expectedPts() As Double
    Dim expectedCount As Long
    Dim rowCount As Long
    Dim ok As Boolean
    Dim chTag As String

    chTag = "Ch_HW_1"
    path = "C:\QdDynacool\Data\ETO\K2450_IV_Live_Hardware_Test.dat"

    ok = K2450_IV_BuildSetpoints(0#, 0.001, -0.001, 0.001, K2450_IV_DIR_START_MAX_MIN_START, expectedPts)
    If Not ok Then
        MV_Log "[TEST][K2450-IV-HW] FAIL setpoint build: " & MV_LastError
        Exit Sub
    End If
    expectedCount = UBound(expectedPts) - LBound(expectedPts) + 1

    ok = Run_K2450_IV_Live(path, _
                           "K2450 IV hardware smoke", _
                           chTag, _
                           "CURRENT", _
                           0#, _
                           0.001, _
                           -0.001, _
                           0.001, _
                           K2450_IV_DIR_START_MAX_MIN_START, _
                           0.05, _
                           True, _
                           0#, _
                           2#, _
                           1#, _
                           3, _
                           True, _
                           True, _
                           MV_K2450_RESOURCE, _
                           "hardware smoke")
    If Not ok Then
        MV_Log "[TEST][K2450-IV-HW] FAIL run: " & MV_LastError
        Exit Sub
    End If

    rowCount = Test_CountDataRows(path)
    If rowCount = expectedCount Then
        MV_Log "[TEST][K2450-IV-HW] PASS row count: " & CStr(rowCount)
    Else
        MV_Log "[TEST][K2450-IV-HW] FAIL row count: got " & CStr(rowCount) & " expected " & CStr(expectedCount)
    End If

    If Test_FileContainsText(path, "," & chTag & ",") Then
        MV_Log "[TEST][K2450-IV-HW] PASS Ch tag found: " & chTag
    Else
        MV_Log "[TEST][K2450-IV-HW] FAIL Ch tag missing: " & chTag
    End If
End Sub

Public Sub RT_PostAnalysis_Run()
    Dim dataFilePath As String
    Dim analyzeCh1   As Boolean
    Dim analyzeCh2   As Boolean

    dataFilePath = "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\RT_Ch1_NJ1_Ch2_TN_00001.dat"
    analyzeCh1   = True
    analyzeCh2   = True

    If RT_AnalyzeFile(dataFilePath, analyzeCh1, analyzeCh2) Then
        MV_Log "[RT-ANALYSIS] Done."
    Else
        MV_Log "[RT-ANALYSIS] FAIL: " & MV_LastError
    End If
End Sub

' ---------------------------------------------------------------------------
' Run_IVSweepTest: standalone K2450 software IV sweep (test / debug entry point)
' ---------------------------------------------------------------------------
Public Sub Run_IVSweepTest()
    Debug.Clear


    Dim ok As Boolean          ' Overall success flag for each IV run.
    Dim ivSoftPath As String   ' Output .dat path for the IV sweep.

    Const kIvDirection As Integer = K2450_IV_DIR_START_MAX_MIN_START ' Sweep order: start -> max -> min -> start.
    Const kStart_A As Double = 0#            ' Start current in amperes.
    Const kMax_A As Double = 0.001         ' Maximum current in amperes (1 mA).
    Const kMin_A As Double = -0.001        ' Minimum current in amperes (-1 mA).
    Const kStep_A As Double = 0.000004       ' Current step in amperes (4 uA).
    Const kSettle_s As Double = 0#           ' Settling time before each measurement point (seconds).
    Const kNplc As Double = 1#               ' NPLC for measurement integration.
    Const kAvgCount As Integer = 1           ' Number of averaged readings per point.
    Const kRampRatePerS As Double = 0#       ' Ramp rate to start setpoint (0 = immediate/default behavior).
    Const kCompliance_V As Double = 20#       ' Compliance voltage limit in volts.
    Const kSampleChannelTag As String = "Ch2" ' PPMS/sample channel label written to logs (text tag).
    Const kUse4Wire As Boolean = True        ' Enable 4-wire (remote sense) mode.
    Const kAutoRange As Boolean = True       ' Enable automatic measurement range.


'    If Not MV_InitSession("demo_run", "C:\QdDynacool\Data\ETO\Helmholtz_live_log.dat") Then
'        MV_Log "Init failed: " & MV_LastError
'        Exit Sub
'    End If

'    Call PrintStartupDefaults()
'    Call PrintFunctionCatalog()

'    ' Hardware sanity check for K2600 over MultiVu built-in GPIB (non-destructive).
'    Call Test_K2600_Connection()

    ' K2450 CH2 IV sweep: 0 -> +1 mA -> -1 mA -> 0, step 4 uA.
    ivSoftPath = "C:\QdDynacool\Data\ETO\Test_IV5.dat"
    ok = Run_K2450_IV_Sweep(ivSoftPath, _
                            kIvDirection, _
                            kStart_A, _
                            kMax_A, _
                            kMin_A, _
                            kStep_A, _
                            "A", _
                            kSettle_s, _
                            kNplc, _
                            kAvgCount, _
                            kRampRatePerS, _
                            "K2450 IV sweep slow CH2", _
                            kCompliance_V, _
                            kSampleChannelTag, _
                            kUse4Wire, _
                            kAutoRange, _
                            MV_K2450_RESOURCE, _
                            "slow sweep")
    If Not ok Then
        MV_Log "Run_K2450_IV_Sweep failed: " & MV_LastError
        Exit Sub
    End If
End Sub

' ---------------------------------------------------------------------------
' Run_IVSweepFastTest: standalone K2450 fast IV sweep (easy run entry point)
' ---------------------------------------------------------------------------
Public Sub Run_IVSweepFastTest()
    Debug.Clear

    Dim ok As Boolean
    Dim ivFastPath As String
    Dim totalStartDate As Date
    Dim totalStartTimer As Double
    Dim totalElapsed_s As Double
    Const kDebugGPIB As Boolean = True

    Const kIvDirection As Integer = K2450_IV_DIR_START_MAX_MIN_START
    Const kStart_A As Double = 0#
    Const kMax_A As Double = 0.001
    Const kMin_A As Double = -0.001
    Const kStep_A As Double = 0.000004
    Const kSettle_s As Double = 0#
    Const kNplc As Double = 1
    Const kAvgCount As Integer = 1
    Const kRampRatePerS As Double = 0#
    Const kCompliance_V As Double = 20#
    Const kSampleChannelTag As String = "Ch2"
    Const kUse4Wire As Boolean = True
    Const kAutoRange As Boolean = True
    Const kTbRefresh_s As Double = 1#

    totalStartDate = Date
    totalStartTimer = Timer

    Call MV_SetDebugMode(kDebugGPIB)

    ivFastPath = "C:\QdDynacool\Data\ETO\Test_IV_fast200.dat"
    ok = Run_K2450_IV_SweepFast(ivFastPath, _
                                kIvDirection, _
                                kStart_A, _
                                kMax_A, _
                                kMin_A, _
                                kStep_A, _
                                "A", _
                                kSettle_s, _
                                kNplc, _
                                kAvgCount, _
                                kRampRatePerS, _
                                "K2450 IV sweep fast CH2", _
                                kCompliance_V, _
                                kSampleChannelTag, _
                                kUse4Wire, _
                                kAutoRange, _
                                MV_K2450_RESOURCE, _
                                "fast sweep", _
                                kTbRefresh_s)

    If Not ok Then
        totalElapsed_s = (CDbl(Date - totalStartDate) * 86400#) + (Timer - totalStartTimer)
        If totalElapsed_s < 0# Then totalElapsed_s = 0#
        MV_Log "[K2450][FAST] total_runtime_s=" & Format$(totalElapsed_s, "0.000")
        MV_Log "Run_K2450_IV_SweepFast failed: " & MV_LastError
        Call MV_SetDebugMode(False)
        Exit Sub
    End If

    totalElapsed_s = (CDbl(Date - totalStartDate) * 86400#) + (Timer - totalStartTimer)
    If totalElapsed_s < 0# Then totalElapsed_s = 0#
    MV_Log "[K2450][FAST] total_runtime_s=" & Format$(totalElapsed_s, "0.000")
    MV_Log "Run_K2450_IV_SweepFast finished OK: " & ivFastPath
    Call MV_SetDebugMode(False)
End Sub

Public Sub Run_K2600_ZeroOutputCheck()
    Const kCurrentTolerance_A As Double = 0.000001

    Dim resourceName As String
    Dim outputA As String
    Dim outputB As String
    Dim currentA As String
    Dim currentB As String
    Dim currentA_A As Double
    Dim currentB_A As Double
    Dim ok As Boolean
    Dim connectedHere As Boolean

    Debug.Clear
    resourceName = MV_K2600_RESOURCE
    connectedHere = False

    MV_Log "[K2600][ZERO] Starting zero-output check"

    If MV_K2600_Device = "" Then
        MV_Log "[K2600][ZERO] Connecting to " & resourceName
        If Not K2600_Connect(resourceName) Then
            MV_Log "[K2600][ZERO] FAIL connect: " & MV_LastError
            Exit Sub
        End If
        connectedHere = True
        MV_Log "[K2600][ZERO] Connected"
    Else
        MV_Log "[K2600][ZERO] Using existing connection: " & MV_K2600_Device
    End If

    Call K2600_OutputOff()
    MV_Log "[K2600][ZERO] Sent OUTPUT_OFF and zero-current commands to SMUA/SMUB"

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.output)", outputA) Then
        MV_Log "[K2600][ZERO] FAIL read SMUA output state: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.output)", outputB) Then
        MV_Log "[K2600][ZERO] FAIL read SMUB output state: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.leveli)", currentA) Then
        MV_Log "[K2600][ZERO] FAIL read SMUA current level: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.leveli)", currentB) Then
        MV_Log "[K2600][ZERO] FAIL read SMUB current level: " & MV_LastError
        GoTo Cleanup
    End If

    currentA_A = CDbl(Val(currentA))
    currentB_A = CDbl(Val(currentB))

    MV_Log "[K2600][ZERO] SMUA output=" & Trim$(outputA) & ", leveli=" & CStr(currentA_A) & " A"
    MV_Log "[K2600][ZERO] SMUB output=" & Trim$(outputB) & ", leveli=" & CStr(currentB_A) & " A"

    ok = (Val(outputA) = 0) And _
         (Val(outputB) = 0) And _
         (Abs(currentA_A) <= kCurrentTolerance_A) And _
         (Abs(currentB_A) <= kCurrentTolerance_A)

    If ok Then
        MV_Log "[K2600][ZERO] PASS both outputs are off and both current setpoints are zero"
    Else
        MV_Log "[K2600][ZERO] FAIL readback indicates a non-zero or enabled output state"
    End If

Cleanup:
    If MV_K2600_Device <> "" Then
        Call K2600_Disconnect()
        If connectedHere Then
            MV_Log "[K2600][ZERO] Disconnected"
        Else
            MV_Log "[K2600][ZERO] Disconnected existing session after safety shutdown"
        End If
    End If
End Sub

' ---------------------------------------------------------------------------
' Run_HelmholtzBSweep: Helmholtz B-sweep entry point.
' Edit the configuration inside Sub fn_IP_Loop_Helm_Loop_Bsweep (the #Uses file).
' ---------------------------------------------------------------------------
Public Sub Run_HelmholtzBSweep()
    Debug.Clear
    Call fn_IP_Loop_Helm_Loop_Bsweep()
End Sub

' ---------------------------------------------------------------------------
' RunAllTests: runs all no-hardware smoke tests and available hardware checks.
' ---------------------------------------------------------------------------
Public Sub RunAllTests()
    Debug.Clear
    Call Test_NoHardware_All()
    Call Test_VISA32_Connection()
    Call Test_K2600_Connection()
    Call Test_K2600_VISA_Connection()
    Call Test_K2450_IV_Live_Hardware()
    Call Run_K2600_ZeroOutputCheck()
End Sub

' ---------------------------------------------------------------------------
' Main: default entry point when MultiVu runs the script.
' Change the Call below to whichever sub you want to run.
' ---------------------------------------------------------------------------
Sub Main()
    Dim runStartDate As Date
    Dim runStartTimer As Double
    Dim elapsed_s As Double

    Debug.Clear

    MV_Log "[MAIN] ===== IV speed compare: FAST then SLOW ====="

    runStartDate = Date
    runStartTimer = Timer
    Call Run_IVSweepFastTest()
    elapsed_s = (CDbl(Date - runStartDate) * 86400#) + (Timer - runStartTimer)
    If elapsed_s < 0# Then elapsed_s = 0#
    MV_Log "[MAIN] FAST elapsed_s=" & Format$(elapsed_s, "0.000")

    runStartDate = Date
    runStartTimer = Timer
    Call Run_IVSweepTest()
    elapsed_s = (CDbl(Date - runStartDate) * 86400#) + (Timer - runStartTimer)
    If elapsed_s < 0# Then elapsed_s = 0#
    MV_Log "[MAIN] SLOW elapsed_s=" & Format$(elapsed_s, "0.000")

    MV_Log "[MAIN] ===== IV speed compare complete ====="
End Sub

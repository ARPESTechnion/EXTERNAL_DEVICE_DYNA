
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_RunWrappers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"

Option Explicit

Private Sub PrintStartupDefaults()
    Dim maxFieldG As Double
    maxFieldG = MV_HELM_G_PER_A_TOTAL * MV_HELM_MAX_TOTAL_CURRENT_A

    MV_Log "========== WinWrapPPMSControl Defaults =========="
    MV_Log "mapping_version = " & MV_MAPPING_VERSION
    MV_Log ""
    MV_Log "Helmholtz"
    MV_Log "  G_per_A_total = " & CStr(MV_HELM_G_PER_A_TOTAL)
    MV_Log "  max_current_per_ch_A = " & CStr(MV_HELM_MAX_TOTAL_CURRENT_A / 2#)
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
    MV_Log "  MV_CloseSession()"
    MV_Log ""
    MV_Log "Helmholtz (K2600)"
    MV_Log "  K2600_Connect([resource]) / K2600_Disconnect()"
    MV_Log "  Helm_ConfigSource(compliance_V, nplc)"
    MV_Log "  Helm_SetField(targetField_Oe, rate_G_per_s)"
    MV_Log "  Helm_GetField_Oe()"
    MV_Log "  Helm_WaitStable(timeout_s, tolCurrent_A, stableCount)"
    MV_Log "  Helm_GetAppliedCurrents_A(currentA_A, currentB_A)"
    MV_Log "  Helm_MeasureResistances_Ohm(nplc, resistanceA_Ohm, resistanceB_Ohm)"
    MV_Log ""
    MV_Log "Hall (K2450)"
    MV_Log "  K2450_Connect([resource]) / K2450_Disconnect()"
    MV_Log "  K2450_OutputOn() / K2450_OutputOff() / K2450_IsOutputOn()"
    MV_Log "  Hall_ApplyPreset(name), Hall_SetCalibration(vPerG, vOffset_V)"
    MV_Log "  Hall_Configure(current_mA, compliance_V, nplc, avgFilter)"
    MV_Log "  Hall_MeasureVoltage_V([tbm_s]), Hall_ComputeField_Oe(voltage_V)"
    MV_Log "  Hall_MeasureAndLog([tbm_s])  -- appends Hall data into Helmholtz log"
    MV_Log "  Hall_CalibrateOffset_V([tbm_s])"
    MV_Log ""
    MV_Log "DynaCool + Data"
    MV_Log "  DYNA_GetTemperature_K(), DYNA_GetField_Oe()"
    MV_Log "  DYNA_SetField(target_Oe, rate_Oe_s), DYNA_SetFieldAndWait(target_Oe, rate_Oe_s, timeout_s)"
    MV_Log "  DYNA_SetTempAndWait(targetK, rateKmin, mode, timeout_s), DYNA_WaitForTempFieldStable(timeout_s)"
    MV_Log "  Data_AddComment(text)"
    MV_Log ""
    MV_Log "GPIB"
    MV_Log "  MV_SetDebugMode(True/False)  -- toggles [GPIB][W/Q/R] trace output"
    MV_Log ""
    MV_Log "Run wrappers"
    MV_Log "  Run_HelmholtzPoint(targetField_Oe, rate_G_per_s, [measureHall], [hallTBM_s])"
    MV_Log "  Run_HelmholtzPointWithHall(targetField_Oe, rate_G_per_s, [hallTBM_s])"
    MV_Log "  Run_Combined_Dyna_Helm_Point(targetTemp_K, targetField_Oe, rate_G_per_s)"
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
                                     MV_HallNPLC, _
                                     0.001 * CDbl(i), _
                                     10# * CDbl(i)) Then
            MV_Log "[TEST][LOGGER] FAIL write row " & CStr(i) & ": " & MV_LastError
            Call MV_CloseSession()
            Exit Sub
        End If
    Next

    Call MV_CloseSession()
    MV_Log "[TEST][LOGGER] PASS file=" & path
End Sub

Public Sub Test_NoHardware_All()
    MV_Log "===== No-Hardware Smoke Tests ====="
    Call Test_NoHardware_Limits()
    Call Test_NoHardware_HallMath()
    Call Test_NoHardware_Logger()
    Call Test_Logger_HeaderCheck()
    Call Test_Sweep_RowPerPoint()
    MV_Log "==================================="
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
                               1#, 1#, _
                               MV_HallCurrent_mA, MV_HallCompliance_V, MV_HallNPLC)
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

Sub Main()
	Debug.Clear
    ' Example entry point for MultiVu Macro Editor
    ' Update paths to match your MultiVu PC.



    If Not MV_InitSession("demo_run", "C:\QdDynacool\Data\ETO\Helmholtz_live_log.dat") Then
        MV_Log "Init failed: " & MV_LastError
        Exit Sub
    End If

    Call PrintStartupDefaults()
    Call PrintFunctionCatalog()

    ' Hardware sanity check for K2600 over MultiVu built-in GPIB (non-destructive).
    Call Test_K2600_Connection()
End Sub

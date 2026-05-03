Option Explicit

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
    Dim ok As Boolean

    MV_Log "========== VISA32 Connection Test =========="

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

    Call MV_GPIB_CloseAll()
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
    Dim analyzeCh1 As Boolean
    Dim analyzeCh2 As Boolean

    dataFilePath = "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\RT_Ch1_NJ1_Ch2_TN_00001.dat"
    analyzeCh1 = True
    analyzeCh2 = True

    If RT_AnalyzeFile(dataFilePath, analyzeCh1, analyzeCh2) Then
        MV_Log "[RT-ANALYSIS] Done."
    Else
        MV_Log "[RT-ANALYSIS] FAIL: " & MV_LastError
    End If
End Sub

Public Sub Run_IVSweepTest()
    Dim ok As Boolean

    Debug.Clear

    ok = Run_K2450_IV_Sweep("C:\QdDynacool\Data\ETO\Test_IV5.dat", _
                            K2450_IV_DIR_START_MAX_MIN_START, _
                            0#, _
                            0.001, _
                            -0.001, _
                            0.000004, _
                            "A", _
                            0#, _
                            1#, _
                            1, _
                            0#, _
                            "K2450 IV sweep slow CH2", _
                            20#, _
                            "Ch2", _
                            True, _
                            True, _
                            MV_K2450_RESOURCE, _
                            "slow sweep")
    If Not ok Then
        MV_Log "Run_K2450_IV_Sweep failed: " & MV_LastError
        Exit Sub
    End If
End Sub

Public Sub Run_IVSweepFastTest()
    Dim ok As Boolean
    Dim totalStartDate As Date
    Dim totalStartTimer As Double
    Dim totalElapsed_s As Double

    Debug.Clear

    totalStartDate = Date
    totalStartTimer = Timer

    Call MV_SetDebugMode(True)

    ok = Run_K2450_IV_SweepFast("C:\QdDynacool\Data\ETO\Test_IV_fast200.dat", _
                                K2450_IV_DIR_START_MAX_MIN_START, _
                                0#, _
                                0.001, _
                                -0.001, _
                                0.000004, _
                                "A", _
                                0#, _
                                1#, _
                                1, _
                                0#, _
                                "K2450 IV sweep fast CH2", _
                                20#, _
                                "Ch2", _
                                True, _
                                True, _
                                MV_K2450_RESOURCE, _
                                "fast sweep", _
                                1#)

    totalElapsed_s = (CDbl(Date - totalStartDate) * 86400#) + (Timer - totalStartTimer)
    If totalElapsed_s < 0# Then totalElapsed_s = 0#
    MV_Log "[K2450][FAST] total_runtime_s=" & Format$(totalElapsed_s, "0.000")

    If Not ok Then
        MV_Log "Run_K2450_IV_SweepFast failed: " & MV_LastError
        Call MV_SetDebugMode(False)
        Exit Sub
    End If

    MV_Log "Run_K2450_IV_SweepFast finished OK"
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

Public Sub Run_HelmholtzBSweep()
    Debug.Clear
    Call fn_IP_Loop_Helm_Loop_Bsweep(-150#, 150#, 3#, 0.0005, 12.20704, 60, "3 2 1", "0 0 0", 300, 3#, True, True, 2.7, 2.7, 0#, 0#, 0#, 0#, "GPIB0::26::INSTR", "GPIB0::18::INSTR", "wire2", "C:\QdDynacool\Data\ETO\")
End Sub

Public Sub RunAllTests()
    Debug.Clear
    Call Test_NoHardware_All()
    Call Test_VISA32_Connection()
    Call Test_K2600_Connection()
    Call Test_K2600_VISA_Connection()
    Call Test_K2450_IV_Live_Hardware()
    Call Run_K2600_ZeroOutputCheck()
End Sub

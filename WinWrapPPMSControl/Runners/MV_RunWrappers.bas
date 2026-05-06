'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2450_Hall.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Instruments\MV_K2450_LiveLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Instruments\MV_K7001.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"
'#Uses "..\Analysis\MV_PostAnalysisMergedLog.bas"

Option Explicit

' ============================================================
' SESSION MANAGEMENT
' ============================================================
Public Function MV_InitSession(ByVal runName As String, ByVal helmholtzLogPath As String) As Boolean
    MV_RunName = runName
    MV_ClearError
    MV_ResetDefaults
    MV_StartSessionClock

    If Not MV_InitHelmholtzLog(helmholtzLogPath) Then
        MV_InitSession = False
        Exit Function
    End If

    MV_InitSession = True
End Function

Public Function MV_InitSessionWithPostAnalysis(ByVal runName As String, _
                                               ByVal helmholtzLogPath As String, _
                                               ByVal mergedPostAnalysisPath As String) As Boolean
    If Not MV_InitSession(runName, helmholtzLogPath) Then
        MV_InitSessionWithPostAnalysis = False
        Exit Function
    End If

    If Not Merged_InitPostAnalysisLog(mergedPostAnalysisPath) Then
        Call MV_CloseSession()
        MV_InitSessionWithPostAnalysis = False
        Exit Function
    End If

    MV_InitSessionWithPostAnalysis = True
End Function

Public Function MV_CloseSession() As Boolean
    On Error Resume Next
    Call K2600_OutputOff()
    Call K2450_OutputOff()
    Call K2600_Disconnect()
    Call K2450_Disconnect()
    Call MV_GPIB_CloseAll()
    Call Merged_ClosePostAnalysisLog()
    MV_CloseSession = True
End Function

' ============================================================
' COMBINED MEASUREMENT HELPERS
' ============================================================
Public Function Full_MeasureAndLog(Optional ByVal tbm_s As Double = 0.05) As Boolean
    Dim v As Double
    Dim hallOe As Double

    v = Hall_MeasureVoltage_V(tbm_s)
    If Not MV_IsFinite(v) Then
        MV_SetError "Hall voltage read failed"
        Full_MeasureAndLog = False
        Exit Function
    End If

    hallOe = Hall_ComputeField_Oe(v)
    Full_MeasureAndLog = Helm_WriteLogRow(v, hallOe)
End Function

' ============================================================
' POST-ANALYSIS WRAPPERS
' ============================================================
Public Function PostAnalysis_AppendAfterETO(ByVal etoDataPath As String, _
                                            ByVal hallMeasuredThisStep As Boolean, _
                                            ByVal measureCh1 As Boolean, _
                                            ByVal measureCh2 As Boolean, _
                                            ByVal channelsShareBlock As Boolean, _
                                            ByVal dualBlockOrderCh1First As Boolean, _
                                            ByVal ch1CurrentColIndex As Long, _
                                            ByVal ch1VoltageColIndex As Long, _
                                            ByVal ch1AveragingTimeColIndex As Long, _
                                            ByVal ch1GainColIndex As Long, _
                                            ByVal ch2CurrentColIndex As Long, _
                                            ByVal ch2VoltageColIndex As Long, _
                                            ByVal ch2AveragingTimeColIndex As Long, _
                                            ByVal ch2GainColIndex As Long, _
                                            Optional ByVal overrideTemp_K As Double = -9.9E99, _
                                            Optional ByVal overrideField_Oe As Double = -9.9E99, _
                                            Optional ByVal hallVoltage_V As Double = -9.9E99, _
                                            Optional ByVal hallField_Oe As Double = -9.9E99) As Boolean
    Dim ok As Boolean

    ok = PostAnalysis_AppendMergedRow(etoDataPath, _
                                      MV_PostAnalysisStepIndex, _
                                      hallMeasuredThisStep, _
                                      measureCh1, _
                                      measureCh2, _
                                      channelsShareBlock, _
                                      dualBlockOrderCh1First, _
                                      ch1CurrentColIndex, _
                                      ch1VoltageColIndex, _
                                      ch1AveragingTimeColIndex, _
                                      ch1GainColIndex, _
                                      ch2CurrentColIndex, _
                                      ch2VoltageColIndex, _
                                      ch2AveragingTimeColIndex, _
                                      ch2GainColIndex, _
                                      overrideTemp_K, _
                                      overrideField_Oe, _
                                      hallVoltage_V, _
                                      hallField_Oe)

    If Not ok Then
        PostAnalysis_AppendAfterETO = False
        Exit Function
    End If

    MV_PostAnalysisStepIndex = MV_PostAnalysisStepIndex + 1
    PostAnalysis_AppendAfterETO = True
End Function

Public Function PostAnalysis_ReplayOldETOScan(ByVal etoDataPath As String, _
                                              ByVal loopCount As Long, _
                                              ByVal helmStart_Oe As Double, _
                                              ByVal helmStep_Oe As Double, _
                                              ByVal hallMeasuredThisStep As Boolean, _
                                              ByVal measureCh1 As Boolean, _
                                              ByVal measureCh2 As Boolean, _
                                              ByVal channelsShareBlock As Boolean, _
                                              ByVal dualBlockOrderCh1First As Boolean, _
                                              ByVal ch1CurrentColIndex As Long, _
                                              ByVal ch1VoltageColIndex As Long, _
                                              ByVal ch1AveragingTimeColIndex As Long, _
                                              ByVal ch1GainColIndex As Long, _
                                              ByVal ch2CurrentColIndex As Long, _
                                              ByVal ch2VoltageColIndex As Long, _
                                              ByVal ch2AveragingTimeColIndex As Long, _
                                              ByVal ch2GainColIndex As Long) As Boolean
    Dim i As Long
    Dim targetHelm_Oe As Double
    Dim totalCurrent_A As Double
    Dim ok As Boolean
    Dim sourceTemp_K As Double
    Dim sourceField_Oe As Double
    Dim contextBlockIndex As Long

    If loopCount <= 0 Then
        MV_SetError "PostAnalysis replay requires loopCount > 0"
        PostAnalysis_ReplayOldETOScan = False
        Exit Function
    End If

    For i = 0 To loopCount - 1
        targetHelm_Oe = helmStart_Oe + (CDbl(i) * helmStep_Oe)
        totalCurrent_A = Helm_FieldToCurrent_A(targetHelm_Oe)

        If channelsShareBlock Or (Not measureCh1) Or (Not measureCh2) Then
            contextBlockIndex = i
        Else
            contextBlockIndex = 2 * i
        End If

        If Not IV_ExtractBlockTempFieldFromFile(etoDataPath, contextBlockIndex, sourceTemp_K, sourceField_Oe) Then
            PostAnalysis_ReplayOldETOScan = False
            Exit Function
        End If

        ' Virtual Helmholtz state for offline replay without hardware I/O.
        MV_LastHelmholtzField_Oe = targetHelm_Oe
        MV_LastCurrentA_A = totalCurrent_A / 2#
        MV_LastCurrentB_A = totalCurrent_A / 2#
        MV_LastTotalCurrent_A = totalCurrent_A

        If Not Log_WriteHelmholtzRow(CDbl(i), _
                                     sourceTemp_K, _
                                     sourceField_Oe, _
                                     targetHelm_Oe, _
                                     MV_LastCurrentA_A, _
                                     MV_LastCurrentB_A, _
                                     MV_HelmCompliance_V, _
                                     MV_HelmNPLC, _
                                     -9.9E99, _
                                     -9.9E99, _
                                     MV_HallCurrent_mA, _
                                     MV_HallCompliance_V, _
                                     MV_HallNPLC) Then
            PostAnalysis_ReplayOldETOScan = False
            Exit Function
        End If

        ok = PostAnalysis_AppendAfterETO(etoDataPath, _
                                         hallMeasuredThisStep, _
                                         measureCh1, _
                                         measureCh2, _
                                         channelsShareBlock, _
                                         dualBlockOrderCh1First, _
                                         ch1CurrentColIndex, _
                                         ch1VoltageColIndex, _
                                         ch1AveragingTimeColIndex, _
                                         ch1GainColIndex, _
                                         ch2CurrentColIndex, _
                                         ch2VoltageColIndex, _
                                         ch2AveragingTimeColIndex, _
                                         ch2GainColIndex, _
                                         sourceTemp_K, _
                                         sourceField_Oe)
        If Not ok Then
            PostAnalysis_ReplayOldETOScan = False
            Exit Function
        End If
    Next i

    PostAnalysis_ReplayOldETOScan = True
End Function

Private Function K2450RW_NormalizeSourceSpec(ByVal sourceSpec As String, ByRef outMode As String, ByRef outScale As Double) As Boolean
    Dim key As String

    key = UCase$(Trim$(sourceSpec))
    outMode = ""
    outScale = 1#

    If key = "V" Or key = "VOLT" Or key = "VOLTAGE" Then
        outMode = "VOLTAGE"
        outScale = 1#
    ElseIf key = "MA" Or key = "MILLIAMP" Or key = "MILLIAMPS" Or key = "CURRENT_MA" Or key = "CURR_MA" Or key = "I_MA" Then
        outMode = "CURRENT"
        outScale = 0.001
    ElseIf key = "A" Or key = "AMP" Or key = "AMPS" Or key = "CURR" Or key = "CURRENT" Then
        outMode = "CURRENT"
        outScale = 1#
    Else
        MV_SetError "Unknown source spec (use V, VOLTAGE, mA, or A): " & sourceSpec
        K2450RW_NormalizeSourceSpec = False
        Exit Function
    End If

    K2450RW_NormalizeSourceSpec = True
End Function

' ============================================================
' IV SWEEP RUN FUNCTIONS
' ============================================================
Public Function Run_K2450_IV_Live(ByVal datPath As String, _
                                  ByVal runTitle As String, _
                                  ByVal ch As String, _
                                  ByVal sourceMode As String, _
                                  ByVal startVal As Double, _
                                  ByVal maxVal As Double, _
                                  ByVal minVal As Double, _
                                  ByVal stepVal As Double, _
                                  ByVal directionMode As Integer, _
                                  ByVal settle_s As Double, _
                                  Optional ByVal rampToStart As Boolean = True, _
                                  Optional ByVal rampRatePerS As Double = 0#, _
                                  Optional ByVal compliance As Double = 2#, _
                                  Optional ByVal nplc As Double = 1#, _
                                  Optional ByVal avgCount As Integer = 5, _
                                  Optional ByVal use4Wire As Boolean = True, _
                                  Optional ByVal autoRange As Boolean = True, _
                                  Optional ByVal resource As String = "", _
                                  Optional ByVal comment As String = "") As Boolean
    Dim modeKey As String
    Dim autoConnected As Boolean
    Dim ok As Boolean

    modeKey = UCase$(Trim$(sourceMode))
    autoConnected = False

    If MV_K2450_Device = "" Then
        If resource = "" Then
            ok = K2450_Connect()
        Else
            ok = K2450_Connect(resource)
        End If
        If Not ok Then
            Run_K2450_IV_Live = False
            Exit Function
        End If
        autoConnected = True
    End If

    If modeKey = "CURR" Or modeKey = "CURRENT" Then
        ok = K2450_ConfigCurrentSource(startVal, compliance, nplc, avgCount, use4Wire, autoRange)
    ElseIf modeKey = "VOLT" Or modeKey = "VOLTAGE" Then
        ok = K2450_ConfigVoltageSource(startVal, compliance, nplc, avgCount, use4Wire, autoRange)
    Else
        MV_SetError "Run_K2450_IV_Live invalid sourceMode: " & sourceMode
        ok = False
    End If
    If Not ok Then GoTo Fail

    If Not K2450_LogInit(datPath, runTitle, True) Then GoTo Fail

    ok = K2450_IV_Run(ch, sourceMode, startVal, maxVal, minVal, stepVal, directionMode, settle_s, rampToStart, rampRatePerS, comment)

    Call K2450_LogClose()
    If autoConnected Then Call K2450_Disconnect(True)

    Run_K2450_IV_Live = ok
    Exit Function

Fail:
    Call K2450_LogClose()
    Call K2450_OutputOff()
    If autoConnected Then Call K2450_Disconnect(True)
    Run_K2450_IV_Live = False
End Function

' ch is a sample/log channel tag (for data labeling), not a physical K2450 channel selector.
Public Function Run_K2450_IV_Sweep(ByVal datPath As String, _
                                   ByVal directionMode As Integer, _
                                   ByVal startVal As Double, _
                                   ByVal maxVal As Double, _
                                   ByVal minVal As Double, _
                                   ByVal stepVal As Double, _
                                   ByVal sourceSpec As String, _
                                   ByVal settle_s As Double, _
                                   ByVal nplc As Double, _
                                   ByVal avgCount As Integer, _
                                   ByVal rampRatePerS As Double, _
                                   Optional ByVal runTitle As String = "K2450 IV sweep", _
                                   Optional ByVal compliance As Double = -1#, _
                                   Optional ByVal ch As String = "Ch1", _
                                   Optional ByVal use4Wire As Boolean = True, _
                                   Optional ByVal autoRange As Boolean = True, _
                                   Optional ByVal resource As String = "", _
                                   Optional ByVal comment As String = "") As Boolean
    Dim sourceMode As String
    Dim sourceScale As Double
    Dim startScaled As Double
    Dim maxScaled As Double
    Dim minScaled As Double
    Dim stepScaled As Double
    Dim autoConnected As Boolean
    Dim ok As Boolean

    If Not K2450RW_NormalizeSourceSpec(sourceSpec, sourceMode, sourceScale) Then
        Run_K2450_IV_Sweep = False
        Exit Function
    End If

    If nplc <= 0# Then
        MV_SetError "NPLC must be > 0"
        Run_K2450_IV_Sweep = False
        Exit Function
    End If

    startScaled = startVal * sourceScale
    maxScaled = maxVal * sourceScale
    minScaled = minVal * sourceScale
    stepScaled = stepVal * sourceScale

    If stepScaled = 0# Then
        MV_SetError "step must be non-zero"
        Run_K2450_IV_Sweep = False
        Exit Function
    End If

    If compliance < 0# Then
        If sourceMode = "CURRENT" Then
            compliance = 2#
        Else
            compliance = 0.01
        End If
    End If

    autoConnected = False
    If MV_K2450_Device = "" Then
        If resource = "" Then
            ok = K2450_Connect()
        Else
            ok = K2450_Connect(resource)
        End If
        If Not ok Then
            Run_K2450_IV_Sweep = False
            Exit Function
        End If
        autoConnected = True
    End If

    If sourceMode = "CURRENT" Then
        ok = K2450_ConfigCurrentSource(startScaled, compliance, nplc, avgCount, use4Wire, autoRange)
    Else
        ok = K2450_ConfigVoltageSource(startScaled, compliance, nplc, avgCount, use4Wire, autoRange)
    End If
    If Not ok Then GoTo Fail

    If Not K2450_LogInit(datPath, runTitle, True) Then GoTo Fail

    ok = K2450_IV_Run(ch, sourceMode, startScaled, maxScaled, minScaled, stepScaled, directionMode, settle_s, True, rampRatePerS, comment)

    Call K2450_LogClose()
    If autoConnected Then Call K2450_Disconnect(True)

    Run_K2450_IV_Sweep = ok
    Exit Function

Fail:
    Call K2450_LogClose()
    Call K2450_OutputOff()
    If autoConnected Then Call K2450_Disconnect(True)
    Run_K2450_IV_Sweep = False
End Function

' Fast path: execute list sweeps inside K2450 and batch-log after each instrument chunk.
Public Function Run_K2450_IV_SweepFast(ByVal datPath As String, _
                                       ByVal directionMode As Integer, _
                                       ByVal startVal As Double, _
                                       ByVal maxVal As Double, _
                                       ByVal minVal As Double, _
                                       ByVal stepVal As Double, _
                                       ByVal sourceSpec As String, _
                                       ByVal settle_s As Double, _
                                       ByVal nplc As Double, _
                                       ByVal avgCount As Integer, _
                                       ByVal rampRatePerS As Double, _
                                       Optional ByVal runTitle As String = "K2450 IV sweep fast", _
                                       Optional ByVal compliance As Double = -1#, _
                                       Optional ByVal ch As String = "Ch1", _
                                       Optional ByVal use4Wire As Boolean = True, _
                                       Optional ByVal autoRange As Boolean = True, _
                                       Optional ByVal resource As String = "", _
                                       Optional ByVal comment As String = "", _
                                       Optional ByVal tbRefresh_s As Double = 1#, _
                                       Optional ByVal appendExisting As Boolean = False) As Boolean
    Dim sourceMode As String
    Dim sourceScale As Double
    Dim startScaled As Double
    Dim maxScaled As Double
    Dim minScaled As Double
    Dim stepScaled As Double
    Dim autoConnected As Boolean
    Dim ok As Boolean
    Dim headerNote As String
    Dim expectedPoints As Long

    If Not K2450RW_NormalizeSourceSpec(sourceSpec, sourceMode, sourceScale) Then
        Run_K2450_IV_SweepFast = False
        Exit Function
    End If

    If nplc <= 0# Then
        MV_SetError "NPLC must be > 0"
        Run_K2450_IV_SweepFast = False
        Exit Function
    End If

    startScaled = startVal * sourceScale
    maxScaled = maxVal * sourceScale
    minScaled = minVal * sourceScale
    stepScaled = stepVal * sourceScale

    If stepScaled = 0# Then
        MV_SetError "step must be non-zero"
        Run_K2450_IV_SweepFast = False
        Exit Function
    End If

    expectedPoints = K2450RW_GetSweepPointCount(startScaled, maxScaled, minScaled, Abs(stepScaled), directionMode)
    If expectedPoints < 1 Then expectedPoints = 0

    If compliance < 0# Then
        If sourceMode = "CURRENT" Then
            compliance = 2#
        Else
            compliance = 0.01
        End If
    End If

    autoConnected = False
    If MV_K2450_Device = "" Then
        If resource = "" Then
            ok = K2450_Connect()
        Else
            ok = K2450_Connect(resource)
        End If
        If Not ok Then
            Run_K2450_IV_SweepFast = False
            Exit Function
        End If
        autoConnected = True
    End If

    If sourceMode = "CURRENT" Then
        ok = K2450_ConfigCurrentSource(startScaled, compliance, nplc, avgCount, use4Wire, autoRange)
    Else
        ok = K2450_ConfigVoltageSource(startScaled, compliance, nplc, avgCount, use4Wire, autoRange)
    End If
    If Not ok Then GoTo Fail

    Dim s4w As String
    Dim sAr As String
    If use4Wire Then s4w = "1" Else s4w = "0"
    If autoRange Then sAr = "1" Else sAr = "0"
    headerNote = "mode=" & sourceMode & "; compliance=" & CStr(compliance) & "; nplc=" & CStr(nplc) & "; avg=" & CStr(avgCount) & "; settle_s=" & CStr(settle_s) & "; tb_refresh_s=" & CStr(tbRefresh_s) & "; use4wire=" & s4w & "; autorange=" & sAr & "; start=" & Format$(Now, "YYYY-MM-DD HH:MM:SS")
    If Not K2450_LogInit(datPath, runTitle, False, True, "FAST_MIN", headerNote, appendExisting, expectedPoints) Then GoTo Fail

    ok = K2450_IV_RunFast(ch, sourceMode, startScaled, maxScaled, minScaled, stepScaled, directionMode, settle_s, True, rampRatePerS, comment, tbRefresh_s)

    Call K2450_LogClose()
    If autoConnected Then Call K2450_Disconnect(True)

    Run_K2450_IV_SweepFast = ok
    Exit Function

Fail:
    Call K2450_LogClose()
    Call K2450_OutputOff()
    If autoConnected Then Call K2450_Disconnect(True)
    Run_K2450_IV_SweepFast = False
End Function

Private Function K2450RW_ParseCsvDoubleList(ByVal csvText As String, ByRef outValues() As Double) As Boolean
    Dim parts() As String
    Dim i As Long
    Dim token As String
    Dim count As Long

    csvText = Trim$(csvText)
    If csvText = "" Then
        K2450RW_ParseCsvDoubleList = False
        Exit Function
    End If

    parts = Split(csvText, ",")
    count = 0
    For i = LBound(parts) To UBound(parts)
        token = Trim$(parts(i))
        If token <> "" Then count = count + 1
    Next i

    If count <= 0 Then
        K2450RW_ParseCsvDoubleList = False
        Exit Function
    End If

    ReDim outValues(0 To count - 1)
    count = 0

    On Error GoTo ParseFail
    For i = LBound(parts) To UBound(parts)
        token = Trim$(parts(i))
        If token <> "" Then
            outValues(count) = CDbl(token)
            count = count + 1
        End If
    Next i
    On Error GoTo 0

    K2450RW_ParseCsvDoubleList = True
    Exit Function

ParseFail:
    On Error GoTo 0
    K2450RW_ParseCsvDoubleList = False
End Function

Private Function K2450RW_ParseCsvLongList(ByVal csvText As String, ByRef outValues() As Long) As Boolean
    Dim parts() As String
    Dim i As Long
    Dim token As String
    Dim count As Long

    csvText = Trim$(csvText)
    If csvText = "" Then
        K2450RW_ParseCsvLongList = False
        Exit Function
    End If

    parts = Split(csvText, ",")
    count = 0
    For i = LBound(parts) To UBound(parts)
        token = Trim$(parts(i))
        If token <> "" Then count = count + 1
    Next i

    If count <= 0 Then
        K2450RW_ParseCsvLongList = False
        Exit Function
    End If

    ReDim outValues(0 To count - 1)
    count = 0

    On Error GoTo ParseFail
    For i = LBound(parts) To UBound(parts)
        token = Trim$(parts(i))
        If token <> "" Then
            outValues(count) = CLng(token)
            count = count + 1
        End If
    Next i
    On Error GoTo 0

    K2450RW_ParseCsvLongList = True
    Exit Function

ParseFail:
    On Error GoTo 0
    K2450RW_ParseCsvLongList = False
End Function

Private Function K2450RW_SegPts(ByVal fromV As Double, ByVal toV As Double, ByVal stepAbs As Double, ByVal inclFirst As Boolean) As Long
    Dim span As Double
    Dim n As Long

    span = Abs(toV - fromV)
    If span <= 0.000000000001 Then
        K2450RW_SegPts = 1
        Exit Function
    End If

    n = CLng(Int(span / stepAbs + 0.000000001))
    If CDbl(n) * stepAbs < span - 0.000000001 Then n = n + 1

    If inclFirst Then
        K2450RW_SegPts = n + 1
    Else
        K2450RW_SegPts = n
    End If
End Function

Private Function K2450RW_GetSweepPointCount(ByVal start_mA As Double, _
                                            ByVal max_mA As Double, _
                                            ByVal min_mA As Double, _
                                            ByVal step_mA As Double, _
                                            ByVal directionMode As Integer) As Long
    Dim cnt As Long

    If step_mA <= 0# Then
        K2450RW_GetSweepPointCount = -1
        Exit Function
    End If

    cnt = 0
    If directionMode = 0 Then
        cnt = K2450RW_SegPts(start_mA, max_mA, step_mA, True)
        cnt = cnt + K2450RW_SegPts(max_mA, min_mA, step_mA, False)
        cnt = cnt + K2450RW_SegPts(min_mA, start_mA, step_mA, False)
    ElseIf directionMode = 1 Then
        cnt = K2450RW_SegPts(start_mA, min_mA, step_mA, True)
        cnt = cnt + K2450RW_SegPts(min_mA, max_mA, step_mA, False)
        cnt = cnt + K2450RW_SegPts(max_mA, start_mA, step_mA, False)
    ElseIf directionMode = 2 Then
        cnt = K2450RW_SegPts(start_mA, max_mA, step_mA, True)
        cnt = cnt + K2450RW_SegPts(max_mA, start_mA, step_mA, False)
    ElseIf directionMode = 3 Then
        cnt = K2450RW_SegPts(start_mA, min_mA, step_mA, True)
        cnt = cnt + K2450RW_SegPts(min_mA, start_mA, step_mA, False)
    Else
        K2450RW_GetSweepPointCount = -1
        Exit Function
    End If

    If cnt > 0 Then
        K2450RW_GetSweepPointCount = cnt
    Else
        K2450RW_GetSweepPointCount = -1
    End If
End Function

Private Function K2450RW_FindStepFromTargetPoints(ByVal start_mA As Double, _
                                                  ByVal max_mA As Double, _
                                                  ByVal min_mA As Double, _
                                                  ByVal directionMode As Integer, _
                                                  ByVal targetPoints As Long, _
                                                  ByVal minStep_mA As Double, _
                                                  ByRef outStep_mA As Double, _
                                                  ByRef outActualPoints As Long) As Boolean
    Dim span As Double
    Dim stepLo As Double
    Dim stepHi As Double
    Dim stepMid As Double
    Dim cntLo As Long
    Dim cntHi As Long
    Dim cntMid As Long
    Dim bestStep As Double
    Dim bestCnt As Long
    Dim bestErr As Long
    Dim thisErr As Long
    Dim i As Integer

    If targetPoints < 3 Then
        K2450RW_FindStepFromTargetPoints = False
        Exit Function
    End If

    span = Abs(max_mA - min_mA)
    If span <= 0# Then
        K2450RW_FindStepFromTargetPoints = False
        Exit Function
    End If

    If minStep_mA <= 0# Then minStep_mA = span / 100000#

    stepHi = span
    cntHi = K2450RW_GetSweepPointCount(start_mA, max_mA, min_mA, stepHi, directionMode)
    If cntHi < 0 Then
        K2450RW_FindStepFromTargetPoints = False
        Exit Function
    End If

    stepLo = minStep_mA
    cntLo = K2450RW_GetSweepPointCount(start_mA, max_mA, min_mA, stepLo, directionMode)
    If cntLo < 0 Then
        K2450RW_FindStepFromTargetPoints = False
        Exit Function
    End If

    If cntLo < targetPoints Then
        K2450RW_FindStepFromTargetPoints = False
        Exit Function
    End If

    bestStep = stepHi
    bestCnt = cntHi
    bestErr = Abs(cntHi - targetPoints)

    thisErr = Abs(cntLo - targetPoints)
    If thisErr < bestErr Then
        bestErr = thisErr
        bestStep = stepLo
        bestCnt = cntLo
    End If

    For i = 1 To 36
        stepMid = (stepLo + stepHi) / 2#
        If stepMid <= 0# Then Exit For

        cntMid = K2450RW_GetSweepPointCount(start_mA, max_mA, min_mA, stepMid, directionMode)
        If cntMid < 0 Then
            K2450RW_FindStepFromTargetPoints = False
            Exit Function
        End If

        thisErr = Abs(cntMid - targetPoints)
        If thisErr < bestErr Then
            bestErr = thisErr
            bestStep = stepMid
            bestCnt = cntMid
            If bestErr = 0 Then Exit For
        End If

        If cntMid >= targetPoints Then
            stepLo = stepMid
            cntLo = cntMid
        Else
            stepHi = stepMid
            cntHi = cntMid
        End If
    Next i

    outStep_mA = bestStep
    outActualPoints = bestCnt
    K2450RW_FindStepFromTargetPoints = True
End Function

Private Function K2450RW_DirectionTag(ByVal directionMode As Integer) As String
    If directionMode = 1 Then
        K2450RW_DirectionTag = "MINFIRST"
    ElseIf directionMode = 0 Then
        K2450RW_DirectionTag = "MAXFIRST"
    Else
        K2450RW_DirectionTag = "DIR" & CStr(directionMode)
    End If
End Function

Private Function K2450RW_BoolText(ByVal value As Boolean) As String
    If value Then
        K2450RW_BoolText = "1"
    Else
        K2450RW_BoolText = "0"
    End If
End Function

Private Function K2450RW_SetTemperatureAndDelay(ByVal targetK As Double, _
                                                ByVal rateKmin As Double, _
                                                ByVal tempMode As Integer, _
                                                ByVal stableTimeout_s As Double, _
                                                ByVal settleDelay_s As Double) As Boolean
    MV_Log "[K2450RW][FAST-TC] Set temperature to " & CStr(targetK) & " K @ " & CStr(rateKmin) & " K/min"
    If Not DYNA_SetTempAndWait(targetK, rateKmin, tempMode, stableTimeout_s) Then
        K2450RW_SetTemperatureAndDelay = False
        Exit Function
    End If
    MV_Log "[K2450RW][FAST-TC] Temperature wait finished at " & CStr(targetK) & " K"

    If settleDelay_s > 0# Then
        MV_Log "[K2450RW][FAST-TC] Extra settle delay " & CStr(settleDelay_s) & " s"
        DynaCool.WaitFor 0, CLng(settleDelay_s), 0 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0004 Wait For %t
    End If

    K2450RW_SetTemperatureAndDelay = True
End Function

Public Function Run_K2450_IV_Fast_TempCycle(ByVal tempList_K_Csv As String, _
                                            ByVal maxCurrentList_mA_Csv As String, _
                                            ByVal pointsPerIV_List_Csv As String, _
                                            ByVal highTemp_K As Double, _
                                            ByVal tempRampRate_Kmin As Double, _
                                            ByVal tempSetMode As Integer, _
                                            ByVal tempStableTimeout_s As Double, _
                                            ByVal tempSettleDelay_s As Double, _
                                            ByVal repeatsPerTemp As Integer, _
                                            ByVal sourceSpec As String, _
                                            ByVal start_mA As Double, _
                                            ByVal minStep_uA As Double, _
                                            ByVal nplc As Double, _
                                            ByVal avgCount As Integer, _
                                            ByVal sweepSettle_s As Double, _
                                            ByVal rampRate_mA_per_s As Double, _
                                            ByVal compliance_V As Double, _
                                            ByVal use4Wire As Boolean, _
                                            ByVal autoRange As Boolean, _
                                            ByVal tbRefresh_s As Double, _
                                            ByVal directionFirst As Integer, _
                                            ByVal directionSecond As Integer, _
                                            ByVal resourceName As String, _
                                            ByVal sampleChannelTag As String, _
                                            ByVal baseFolder As String, _
                                            ByVal runPrefix As String, _
                                            Optional ByVal debugGPIB As Boolean = False) As Boolean
    Dim temps_K() As Double
    Dim maxCurr_mA() As Double
    Dim pointsPerIV() As Long
    Dim timeStamp As String
    Dim runFilePath As String
    Dim hasWrittenAnyIV As Boolean
    Dim connectedHere As Boolean
    Dim i As Long
    Dim rep As Integer
    Dim lowK As Double
    Dim max_mA As Double
    Dim targetPoints As Long
    Dim directionMode As Integer
    Dim step_mA As Double
    Dim actualPoints As Long
    Dim runTitle As String
    Dim runComment As String
    Dim ok As Boolean

    Debug.Clear
    Call MV_SetDebugMode(debugGPIB)
    MV_ClearError

    timeStamp = Format$(Now, "yyyymmdd_hhnnss")
    runFilePath = baseFolder & runPrefix & "_ALL_" & timeStamp & ".dat"
    hasWrittenAnyIV = False
    MV_Log "[K2450RW][FAST-TC] output_file=" & runFilePath

    MV_Log "[K2450RW][FAST-TC] temp_list_K=" & tempList_K_Csv
    MV_Log "[K2450RW][FAST-TC] max_current_list_mA=" & maxCurrentList_mA_Csv
    MV_Log "[K2450RW][FAST-TC] points_per_iv_list=" & pointsPerIV_List_Csv
    MV_Log "[K2450RW][FAST-TC] high_temp_K=" & CStr(highTemp_K) & "; temp_ramp_K_min=" & CStr(tempRampRate_Kmin) & "; temp_mode=" & CStr(tempSetMode)
    MV_Log "[K2450RW][FAST-TC] temp_stable_timeout_s=" & CStr(tempStableTimeout_s) & "; temp_settle_delay_s=" & CStr(tempSettleDelay_s) & "; repeats_per_temp=" & CStr(repeatsPerTemp)
    MV_Log "[K2450RW][FAST-TC] source_spec=" & sourceSpec & "; start_mA=" & CStr(start_mA) & "; min_step_uA=" & CStr(minStep_uA)
    MV_Log "[K2450RW][FAST-TC] nplc=" & CStr(nplc) & "; avg_count=" & CStr(avgCount) & "; sweep_settle_s=" & CStr(sweepSettle_s) & "; ramp_rate_mA_s=" & CStr(rampRate_mA_per_s)
    MV_Log "[K2450RW][FAST-TC] compliance_V=" & CStr(compliance_V) & "; use_4wire=" & K2450RW_BoolText(use4Wire) & "; auto_range=" & K2450RW_BoolText(autoRange) & "; tb_refresh_s=" & CStr(tbRefresh_s)
    MV_Log "[K2450RW][FAST-TC] direction_first=" & K2450RW_DirectionTag(directionFirst) & "; direction_second=" & K2450RW_DirectionTag(directionSecond)
    MV_Log "[K2450RW][FAST-TC] resource=" & resourceName & "; sample_tag=" & sampleChannelTag
    MV_Log "[K2450RW][FAST-TC] base_folder=" & baseFolder & "; run_prefix=" & runPrefix & "; debug_gpib=" & K2450RW_BoolText(debugGPIB)
    If repeatsPerTemp < 1 Then
        MV_SetError "RepeatsPerTemp must be >= 1"
        GoTo Fail
    End If
    If minStep_uA <= 0# Then
        MV_SetError "MinStep_uA must be > 0"
        GoTo Fail
    End If

    ReDim temps_K(0)
    ReDim maxCurr_mA(0)
    ReDim pointsPerIV(0)

    If Not K2450RW_ParseCsvDoubleList(tempList_K_Csv, temps_K) Then
        MV_SetError "Invalid TempList_K_Csv"
        GoTo Fail
    End If
    If Not K2450RW_ParseCsvDoubleList(maxCurrentList_mA_Csv, maxCurr_mA) Then
        MV_SetError "Invalid MaxCurrentList_mA_Csv"
        GoTo Fail
    End If
    If Not K2450RW_ParseCsvLongList(pointsPerIV_List_Csv, pointsPerIV) Then
        MV_SetError "Invalid PointsPerIV_List_Csv"
        GoTo Fail
    End If
    If UBound(temps_K) <> UBound(maxCurr_mA) Or UBound(temps_K) <> UBound(pointsPerIV) Then
        MV_SetError "Temperature, max-current, and points-per-IV lists must have the same length"
        GoTo Fail
    End If

    connectedHere = False
    If MV_K2450_Device = "" Then
        If Not K2450_Connect(resourceName) Then GoTo Fail 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0001 Connect To K2450
        connectedHere = True
    End If

    MV_Log "[K2450RW][FAST-TC] Starting temperature cycle fast-IV run"
    MV_Log "[K2450RW][FAST-TC] pairs=" & CStr(UBound(temps_K) + 1) & ", repeats_per_temp=" & CStr(repeatsPerTemp)

    For i = LBound(temps_K) To UBound(temps_K) 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0002 Temp Pair Loop
        lowK = temps_K(i)
        max_mA = maxCurr_mA(i)
        targetPoints = pointsPerIV(i)

        If max_mA <= 0# Then
            MV_SetError "Max current must be > 0 mA at index " & CStr(i + 1)
            GoTo Fail
        End If
        If targetPoints < 3 Then
            MV_SetError "Points per IV must be >= 3 at index " & CStr(i + 1)
            GoTo Fail
        End If

        MV_Log "[K2450RW][FAST-TC] Pair " & CStr(i + 1) & "/" & CStr(UBound(temps_K) + 1) & _
               ": lowT=" & CStr(lowK) & " K, Imax=" & CStr(max_mA) & " mA, target_points=" & CStr(targetPoints)

        For rep = 1 To repeatsPerTemp 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0003 Repeat Loop
            If (rep Mod 2) = 1 Then
                directionMode = directionFirst
            Else
                directionMode = directionSecond
            End If

            If Not K2450RW_SetTemperatureAndDelay(lowK, tempRampRate_Kmin, tempSetMode, tempStableTimeout_s, tempSettleDelay_s) Then GoTo Fail 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0004 Set Low Temp

            If Not K2450RW_FindStepFromTargetPoints(start_mA, max_mA, -max_mA, directionMode, targetPoints, minStep_uA / 1000#, step_mA, actualPoints) Then
                MV_SetError "Could not derive step from points at index " & CStr(i + 1)
                GoTo Fail
            End If

            runTitle = "K2450 fast IV temp cycle: T=" & CStr(lowK) & " K, Imax=" & CStr(max_mA) & " mA"
            runComment = "pair=" & CStr(i + 1) & ";rep=" & CStr(rep) & ";direction=" & K2450RW_DirectionTag(directionMode) & ";lowT=" & CStr(lowK) & ";target_points=" & CStr(targetPoints) & ";actual_points=" & CStr(actualPoints) & ";step_mA=" & CStr(step_mA)

            MV_Log "[K2450RW][FAST-TC] rep=" & CStr(rep) & ", direction=" & K2450RW_DirectionTag(directionMode) & ", step_mA=" & CStr(step_mA) & ", actual_points=" & CStr(actualPoints)

            ok = Run_K2450_IV_SweepFast(runFilePath, _
                                        directionMode, _
                                        start_mA, _
                                        max_mA, _
                                        -max_mA, _
                                        step_mA, _
                                        sourceSpec, _
                                        sweepSettle_s, _
                                        nplc, _
                                        avgCount, _
                                        rampRate_mA_per_s, _
                                        runTitle, _
                                        compliance_V, _
                                        sampleChannelTag, _
                                        use4Wire, _
                                        autoRange, _
                                        resourceName, _
                                        runComment, _
                                        tbRefresh_s, _
                                        hasWrittenAnyIV) 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0005 Run IV Sweep
            If Not ok Then GoTo Fail
            hasWrittenAnyIV = True

            MV_Log "[K2450RW][FAST-TC] IV done: " & runFilePath

            If Not K2450RW_SetTemperatureAndDelay(highTemp_K, tempRampRate_Kmin, tempSetMode, tempStableTimeout_s, tempSettleDelay_s) Then GoTo Fail 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0006 Return To High Temp
        Next rep
    Next i

    If connectedHere Then
        Call K2450_OutputOff() 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0007 Output Off
        Call K2450_Disconnect(True) 'mvseq:K2450_IV_Fast_TempCycle.seq(1)>0008 Disconnect K2450
    End If
    Call MV_SetDebugMode(False)
    Run_K2450_IV_Fast_TempCycle = True
    Exit Function

Fail:
    MV_Log "[K2450RW][FAST-TC] FAIL: " & MV_LastError
    On Error Resume Next
    Call K2450_OutputOff()
    If connectedHere Then Call K2450_Disconnect(True)
    On Error GoTo 0
    Call MV_SetDebugMode(False)
    Run_K2450_IV_Fast_TempCycle = False
End Function

Public Sub Run_K2450_IV_Fast_TempCycle_Configured()
    Dim ok As Boolean

    ok = Run_K2450_IV_Fast_TempCycle(K2450RW_FTC_TempList_K_Csv, _
                                     K2450RW_FTC_MaxCurrentList_mA_Csv, _
                                     K2450RW_FTC_PointsPerIV_List_Csv, _
                                     K2450RW_FTC_HighTemp_K, _
                                     K2450RW_FTC_TempRampRate_Kmin, _
                                     K2450RW_FTC_TempSetMode, _
                                     K2450RW_FTC_TempStableTimeout_s, _
                                     0#, _
                                     K2450RW_FTC_RepeatsPerTemp, _
                                     K2450RW_FTC_SourceSpec, _
                                     K2450RW_FTC_Start_mA, _
                                     K2450RW_FTC_MinStep_uA, _
                                     K2450RW_FTC_Nplc, _
                                     K2450RW_FTC_AvgCount, _
                                     K2450RW_FTC_SweepSettle_s, _
                                     K2450RW_FTC_RampRate_mA_per_s, _
                                     K2450RW_FTC_Compliance_V, _
                                     K2450RW_FTC_Use4Wire, _
                                     K2450RW_FTC_AutoRange, _
                                     K2450RW_FTC_TbRefresh_s, _
                                     K2450RW_FTC_DirectionFirst, _
                                     K2450RW_FTC_DirectionSecond, _
                                     K2450RW_FTC_ResourceName, _
                                     K2450RW_FTC_SampleChannelTag, _
                                     K2450RW_FTC_BaseFolder, _
                                     K2450RW_FTC_RunPrefix, _
                                     K2450RW_FTC_DebugGPIB)

    If Not ok Then
        MV_Log "[MACRO][FAST-TC] FAIL: " & MV_LastError
    End If
End Sub

Public Sub Run_K2450_IV_Fast_TempCycle_Defaults()
    K2450RW_FTC_TempList_K_Csv = "300, 299, 298, 297, 296, 295, 294, 293, 292, 291"
    K2450RW_FTC_MaxCurrentList_mA_Csv = "0.065, 0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.1, 0.105, 0.11"
    K2450RW_FTC_PointsPerIV_List_Csv = "1023, 1023, 1023, 1023, 1023, 1023, 1023, 1023, 1023, 1023"

    K2450RW_FTC_HighTemp_K = 300#
    K2450RW_FTC_TempRampRate_Kmin = 10#
    K2450RW_FTC_TempSetMode = 0
    K2450RW_FTC_TempStableTimeout_s = 60#
    K2450RW_FTC_TempSettleDelay_s = 0#
    K2450RW_FTC_RepeatsPerTemp = 2

    K2450RW_FTC_SourceSpec = "mA"
    K2450RW_FTC_Start_mA = 0#
    K2450RW_FTC_MinStep_uA = 0.01
    K2450RW_FTC_Nplc = 1#
    K2450RW_FTC_AvgCount = 1
    K2450RW_FTC_SweepSettle_s = 0.01#
    K2450RW_FTC_RampRate_mA_per_s = 0#
    K2450RW_FTC_Compliance_V = 20#
    K2450RW_FTC_Use4Wire = True
    K2450RW_FTC_AutoRange = True
    K2450RW_FTC_TbRefresh_s = 1#
    K2450RW_FTC_DirectionFirst = 1
    K2450RW_FTC_DirectionSecond = 0

    K2450RW_FTC_ResourceName = "GPIB0::18::INSTR"
    K2450RW_FTC_SampleChannelTag = "Ch2"
    K2450RW_FTC_BaseFolder = "C:\QdDynacool\Data\ETO\"
    K2450RW_FTC_RunPrefix = "K2450_fast_tempcycle"
    K2450RW_FTC_DebugGPIB = False

    Call Run_K2450_IV_Fast_TempCycle_Configured()
End Sub

Public Sub FTC_RunDefault()
    Call Run_K2450_IV_Fast_TempCycle_Defaults
End Sub

Public Sub FTC_RunConfigured()
    Call Run_K2450_IV_Fast_TempCycle_Configured
End Sub


'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_General.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_LiveLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_IV_PostAnalysis.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_PostAnalysisMergedLog.bas"

Option Explicit

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

Public Function SelfTest_Connections() As Boolean
    Dim ok As Boolean

    ok = K2600_Connect()
    If ok Then ok = K2450_Connect()

    SelfTest_Connections = ok

    Call MV_CloseSession()
End Function

Public Function SelfTest_LimitEnforcement() As Boolean
    Dim ok1 As Boolean
    Dim ok2 As Boolean

    ok1 = Not Helm_ValidateHelmholtzField(5000#, 10#)
    ok2 = Not Helm_ValidateHelmholtzField(10#, 1000#)

    SelfTest_LimitEnforcement = (ok1 And ok2)
End Function

Public Function SelfTest_SafeAbort() As Boolean
    On Error Resume Next
    Call K2600_OutputOff()
    Call K2450_OutputOff()
    SelfTest_SafeAbort = True
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

Public Function Run_K2450_IV_Sweep(ByVal datPath As String, _
                                   ByVal directionMode As Integer, _
                                   ByVal startVal As Double, _
                                   ByVal maxVal As Double, _
                                   ByVal minVal As Double, _
                                   ByVal stepVal As Double, _
                                   ByVal sourceSpec As String, _
                                   ByVal runFastIV As Boolean, _
                                   ByVal settle_s As Double, _
                                   ByVal nplcRead As Double, _
                                   ByVal nplcSource As Double, _
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

    If nplcRead <= 0# Or nplcSource <= 0# Then
        MV_SetError "NPLC values must be > 0"
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
        ok = K2450_ConfigCurrentSource(startScaled, compliance, nplcRead, avgCount, use4Wire, autoRange)
        If ok Then ok = MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:NPLC " & CStr(nplcSource))
    Else
        ok = K2450_ConfigVoltageSource(startScaled, compliance, nplcRead, avgCount, use4Wire, autoRange)
        If ok Then ok = MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:NPLC " & CStr(nplcSource))
    End If
    If Not ok Then GoTo Fail

    If Not K2450_LogInit(datPath, runTitle, True) Then GoTo Fail

    If runFastIV Then
        ok = K2450_IV_RunFast(ch, sourceMode, startScaled, maxScaled, minScaled, stepScaled, directionMode, settle_s, True, rampRatePerS, comment)
    Else
        ok = K2450_IV_Run(ch, sourceMode, startScaled, maxScaled, minScaled, stepScaled, directionMode, settle_s, True, rampRatePerS, comment)
    End If

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

Public Function Run_K2450_IV_HardwareSweep(ByVal datPath As String, _
                                           ByVal directionMode As Integer, _
                                           ByVal startVal As Double, _
                                           ByVal maxVal As Double, _
                                           ByVal minVal As Double, _
                                           ByVal stepVal As Double, _
                                           ByVal sourceSpec As String, _
                                           ByVal settle_s As Double, _
                                           ByVal nplcRead As Double, _
                                           ByVal nplcSource As Double, _
                                           ByVal avgCount As Integer, _
                                           ByVal rampRatePerS As Double, _
                                           Optional ByVal runFastHW As Boolean = False, _
                                           Optional ByVal sourceValueMode As Integer = K2450_HW_SRC_MODE_MEASURED, _
                                           Optional ByVal runTitle As String = "K2450 IV hardware sweep", _
                                           Optional ByVal compliance As Double = -1#, _
                                           Optional ByVal ch As String = "Ch1", _
                                           Optional ByVal rampToStart As Boolean = True, _
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
        Run_K2450_IV_HardwareSweep = False
        Exit Function
    End If

    If nplcRead <= 0# Or nplcSource <= 0# Then
        MV_SetError "NPLC values must be > 0"
        Run_K2450_IV_HardwareSweep = False
        Exit Function
    End If

    If runFastHW Then
        sourceValueMode = K2450_HW_SRC_MODE_CMD_ONLY
    ElseIf sourceValueMode < K2450_HW_SRC_MODE_CMD_ONLY Or sourceValueMode > K2450_HW_SRC_MODE_MEASURED Then
        sourceValueMode = K2450_HW_SRC_MODE_MEASURED
    End If

    startScaled = startVal * sourceScale
    maxScaled = maxVal * sourceScale
    minScaled = minVal * sourceScale
    stepScaled = stepVal * sourceScale

    If stepScaled = 0# Then
        MV_SetError "step must be non-zero"
        Run_K2450_IV_HardwareSweep = False
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
            Run_K2450_IV_HardwareSweep = False
            Exit Function
        End If
        autoConnected = True
    End If

    If sourceMode = "CURRENT" Then
        ok = K2450_ConfigCurrentSource(startScaled, compliance, nplcRead, avgCount, use4Wire, autoRange)
        If ok Then ok = MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:NPLC " & CStr(nplcSource))
    Else
        ok = K2450_ConfigVoltageSource(startScaled, compliance, nplcRead, avgCount, use4Wire, autoRange)
        If ok Then ok = MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:NPLC " & CStr(nplcSource))
    End If
    If Not ok Then GoTo Fail

    If Not K2450_LogInit(datPath, runTitle, True) Then GoTo Fail

    ok = K2450_IV_RunHardwareSweep(ch, sourceMode, startScaled, maxScaled, minScaled, stepScaled, directionMode, settle_s, sourceValueMode, rampToStart, rampRatePerS, comment)

    Call K2450_LogClose()
    If autoConnected Then Call K2450_Disconnect(True)

    Run_K2450_IV_HardwareSweep = ok
    Exit Function

Fail:
    Call K2450_LogClose()
    Call K2450_OutputOff()
    If autoConnected Then Call K2450_Disconnect(True)
    Run_K2450_IV_HardwareSweep = False
End Function

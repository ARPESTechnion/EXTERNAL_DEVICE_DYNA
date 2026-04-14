'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
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

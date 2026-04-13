'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"

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

Public Function MV_CloseSession() As Boolean
    On Error Resume Next
    Call K2600_OutputOff()
    Call K2600_Disconnect()
    Call K2450_Disconnect()
    Call MV_GPIB_CloseAll()
    MV_CloseSession = True
End Function

Public Function Run_HelmholtzPoint(ByVal targetField_Oe As Double, ByVal rate_G_per_s As Double, Optional ByVal measureHall As Boolean = False, Optional ByVal hallTBM_s As Double = 0.05) As Boolean
    Dim tRel As Double
    Dim tempK As Double
    Dim fieldOe As Double
    Dim rA As Double
    Dim rB As Double
    Dim hallV As Double
    Dim hallOe As Double

    If Not Helm_SetField(targetField_Oe, rate_G_per_s) Then
        Run_HelmholtzPoint = False
        Exit Function
    End If

    If Not Helm_WaitStable(30#, MV_DEFAULT_CURRENT_TOL_A, MV_DEFAULT_STABLE_COUNT) Then
        Run_HelmholtzPoint = False
        Exit Function
    End If

    Call DYNA_WaitForTempFieldStable(60#)

    If Not Helm_MeasureResistances_Ohm(MV_HelmNPLC, rA, rB) Then
        Run_HelmholtzPoint = False
        Exit Function
    End If

    hallV = -9.9E99
    hallOe = -9.9E99
    If measureHall Then
        hallV = Hall_MeasureVoltage_V(hallTBM_s)
        If Not MV_IsFinite(hallV) Then
            MV_SetError "Hall voltage read failed"
            Run_HelmholtzPoint = False
            Exit Function
        End If
        hallOe = Hall_ComputeField_Oe(hallV)
    End If

    tempK = DYNA_GetTemperature_K()
    fieldOe = DYNA_GetField_Oe()
    tRel = MV_GetSessionElapsedSeconds()

    If Not Log_WriteHelmholtzRow(tRel, tempK, fieldOe, targetField_Oe, MV_LastCurrentA_A, MV_LastCurrentB_A, MV_HelmCompliance_V, MV_HelmNPLC, rA, rB, MV_HallCurrent_mA, MV_HallCompliance_V, MV_HallNPLC, hallV, hallOe) Then
        Run_HelmholtzPoint = False
        Exit Function
    End If

    Run_HelmholtzPoint = True
End Function

Public Function Run_HelmholtzPointWithHall(ByVal targetField_Oe As Double, ByVal rate_G_per_s As Double, Optional ByVal hallTBM_s As Double = 0.05) As Boolean
    Run_HelmholtzPointWithHall = Run_HelmholtzPoint(targetField_Oe, rate_G_per_s, True, hallTBM_s)
End Function

Public Function Run_Combined_Dyna_Helm_Point(ByVal targetTemp_K As Double, ByVal targetField_Oe As Double, ByVal rate_G_per_s As Double) As Boolean
    If Not DYNA_SetTempAndWait(targetTemp_K, 1#, 0, 600#) Then
        Run_Combined_Dyna_Helm_Point = False
        Exit Function
    End If

    Run_Combined_Dyna_Helm_Point = Run_HelmholtzPoint(targetField_Oe, rate_G_per_s)
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

    ok1 = Not Helm_ValidateTarget(5000#, 10#)
    ok2 = Not Helm_ValidateTarget(10#, 1000#)

    SelfTest_LimitEnforcement = (ok1 And ok2)
End Function

Public Function SelfTest_SafeAbort() As Boolean
    On Error Resume Next
    Call K2600_OutputOff()
    SelfTest_SafeAbort = True
End Function

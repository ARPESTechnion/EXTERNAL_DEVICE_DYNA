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
    Call K2450_OutputOff()
    Call K2600_Disconnect()
    Call K2450_Disconnect()
    Call MV_GPIB_CloseAll()
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
    Call K2450_OutputOff()
    SelfTest_SafeAbort = True
End Function

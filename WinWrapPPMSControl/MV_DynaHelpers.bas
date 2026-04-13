'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"

Option Explicit

Public Function DYNA_GetTemperature_K() As Double
    On Error GoTo EH
    Dim tempK As Double
    Dim statusCode As Long

    DynaCool.GetTemperature tempK, statusCode
    DYNA_GetTemperature_K = tempK
    Exit Function
EH:
    DYNA_GetTemperature_K = -9.9E99
End Function

Public Function DYNA_GetField_Oe() As Double
    On Error GoTo EH
    Dim fieldOe As Double
    Dim statusCode As Long

    DynaCool.GetField fieldOe, statusCode
    DYNA_GetField_Oe = fieldOe
    Exit Function
EH:
    DYNA_GetField_Oe = -9.9E99
End Function

Public Function DYNA_WaitForTempFieldStable(ByVal timeout_s As Double) As Boolean
    On Error GoTo EH
    ' 1 = temperature, 2 = field
    DynaCool.WaitFor 1 + 2, CLng(timeout_s), 0
    DYNA_WaitForTempFieldStable = True
    Exit Function
EH:
    MV_SetError "DynaCool WaitFor temp+field failed: " & Err.Description
    DYNA_WaitForTempFieldStable = False
End Function

Public Function DYNA_SetTempAndWait(ByVal targetK As Double, ByVal rateKmin As Double, ByVal mode As Integer, ByVal timeout_s As Double) As Boolean
    On Error GoTo EH
    DynaCool.SetTemperature targetK, rateKmin, mode
    DYNA_SetTempAndWait = DYNA_WaitForTempFieldStable(timeout_s)
    Exit Function
EH:
    MV_SetError "DynaCool SetTemperature failed: " & Err.Description
    DYNA_SetTempAndWait = False
End Function

Public Function DYNA_SetField(ByVal targetField_Oe As Double, ByVal rate_Oe_per_s As Double) As Boolean
    ' Sends a field command to the DynaCool superconducting magnet and returns immediately.
    ' mode 0 = linear, driven = 1 (energises persistent switch).
    ' Call DYNA_WaitForTempFieldStable() or DYNA_SetFieldAndWait() to block until settled.
    On Error GoTo EH
    DynaCool.SetField targetField_Oe, rate_Oe_per_s, 0, 1
    DYNA_SetField = True
    Exit Function
EH:
    MV_SetError "DynaCool SetField failed: " & Err.Description
    DYNA_SetField = False
End Function

Public Function DYNA_SetFieldAndWait(ByVal targetField_Oe As Double, ByVal rate_Oe_per_s As Double, ByVal timeout_s As Double) As Boolean
    ' Sends field command then blocks until the magnet reports stable.
    If Not DYNA_SetField(targetField_Oe, rate_Oe_per_s) Then
        DYNA_SetFieldAndWait = False
        Exit Function
    End If
    ' WaitFor bitmask 2 = field only (bitmask 1 = temperature)
    On Error GoTo EH
    DynaCool.WaitFor 2, CLng(timeout_s), 0
    DYNA_SetFieldAndWait = True
    Exit Function
EH:
    MV_SetError "DynaCool WaitFor field failed: " & Err.Description
    DYNA_SetFieldAndWait = False
End Function

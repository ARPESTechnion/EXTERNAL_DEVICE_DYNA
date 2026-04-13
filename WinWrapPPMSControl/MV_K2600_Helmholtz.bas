'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"

Option Explicit

Public MV_LastTargetField_Oe As Double
Public MV_LastTotalCurrent_A As Double
Public MV_LastCurrentA_A As Double
Public MV_LastCurrentB_A As Double

Private Sub Helm_GetRampStartCurrents(ByRef currentA_A As Double, ByRef currentB_A As Double)
    If Not Helm_GetAppliedCurrents_A(currentA_A, currentB_A) Then
        currentA_A = MV_LastCurrentA_A
        currentB_A = MV_LastCurrentB_A
    End If
End Sub

Private Function Helm_WriteChannelCurrents(ByVal currentA_A As Double, ByVal currentB_A As Double) As Boolean
    If Not MV_GPIB_Write(MV_K2600_Device, "smua.source.leveli = " & CStr(currentA_A)) Then
        Helm_WriteChannelCurrents = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.source.leveli = " & CStr(currentB_A)) Then
        Helm_WriteChannelCurrents = False
        Exit Function
    End If

    Helm_WriteChannelCurrents = True
End Function

Private Function Helm_RampCurrents(ByVal targetCurrentA_A As Double, ByVal targetCurrentB_A As Double, ByVal rate_G_per_s As Double) As Boolean
    Dim startCurrentA_A As Double
    Dim startCurrentB_A As Double
    Dim deltaCurrentA_A As Double
    Dim deltaCurrentB_A As Double
    Dim maxDelta_A As Double
    Dim ratePerCh_A_per_s As Double
    Dim stepTime_s As Double
    Dim stepCount As Long
    Dim i As Long
    Dim frac As Double
    Dim nextCurrentA_A As Double
    Dim nextCurrentB_A As Double

    Call Helm_GetRampStartCurrents(startCurrentA_A, startCurrentB_A)

    deltaCurrentA_A = targetCurrentA_A - startCurrentA_A
    deltaCurrentB_A = targetCurrentB_A - startCurrentB_A
    maxDelta_A = Abs(deltaCurrentA_A)
    If Abs(deltaCurrentB_A) > maxDelta_A Then maxDelta_A = Abs(deltaCurrentB_A)

    If maxDelta_A <= 0# Then
        Helm_RampCurrents = Helm_WriteChannelCurrents(targetCurrentA_A, targetCurrentB_A)
        Exit Function
    End If

    ratePerCh_A_per_s = Abs(rate_G_per_s) / MV_HELM_G_PER_A_TOTAL / 2#
    If ratePerCh_A_per_s <= 0# Then
        MV_SetError "Helm ramp rate must be > 0"
        Helm_RampCurrents = False
        Exit Function
    End If

    stepTime_s = MV_DEFAULT_POLL_S
    stepCount = CLng(Int(maxDelta_A / (ratePerCh_A_per_s * stepTime_s)))
    If (CDbl(stepCount) * ratePerCh_A_per_s * stepTime_s) < maxDelta_A Then
        stepCount = stepCount + 1
    End If
    If stepCount < 1 Then stepCount = 1

    For i = 1 To stepCount
        MV_WaitSeconds stepTime_s
        DoEvents

        frac = CDbl(i) / CDbl(stepCount)
        nextCurrentA_A = startCurrentA_A + deltaCurrentA_A * frac
        nextCurrentB_A = startCurrentB_A + deltaCurrentB_A * frac

        If Not Helm_WriteChannelCurrents(nextCurrentA_A, nextCurrentB_A) Then
            Helm_RampCurrents = False
            Exit Function
        End If
    Next i

    Helm_RampCurrents = True
End Function

Public Function K2600_Connect(Optional ByVal resource As String = "") As Boolean
    If resource = "" Then resource = MV_K2600_RESOURCE
    K2600_Connect = MV_GPIB_Connect(resource, MV_K2600_Device)
End Function

Public Function K2600_Disconnect() As Boolean
    On Error Resume Next
    Call K2600_OutputOff()
    Call MV_GPIB_Disconnect(MV_K2600_Device)
    K2600_Disconnect = True
End Function

Public Function Helm_FieldToCurrent_A(ByVal targetField_Oe As Double) As Double
    Helm_FieldToCurrent_A = targetField_Oe / MV_HELM_G_PER_A_TOTAL
End Function

Public Function Helm_GetField_Oe() As Double
    Dim iA As Double
    Dim iB As Double

    If Helm_GetAppliedCurrents_A(iA, iB) Then
        Helm_GetField_Oe = (iA + iB) * MV_HELM_G_PER_A_TOTAL
    Else
        Helm_GetField_Oe = -9.9E99
    End If
End Function

Public Function Helm_ValidateTarget(ByVal targetField_Oe As Double, ByVal rate_G_per_s As Double) As Boolean
    Dim iTotal As Double

    If Abs(rate_G_per_s) > MV_HELM_MAX_RATE_G_PER_S Then
        MV_SetError "Rate exceeds limit: " & CStr(rate_G_per_s) & " G/s"
        Helm_ValidateTarget = False
        Exit Function
    End If

    iTotal = Helm_FieldToCurrent_A(targetField_Oe)

    If Abs(iTotal) > MV_HELM_MAX_TOTAL_CURRENT_A Then
        MV_SetError "Current exceeds total (3 A) limit at target field: " & CStr(targetField_Oe)
        Helm_ValidateTarget = False
        Exit Function
    End If

    Helm_ValidateTarget = True
End Function

Public Function Helm_ConfigSource(ByVal compliance_V As Double, ByVal nplc As Double) As Boolean
    On Error GoTo EH
    If MV_K2600_Device = "" Then
        MV_SetError "K2600 not connected"
        Helm_ConfigSource = False
        Exit Function
    End If

    If compliance_V < MV_HELM_MIN_COMPLIANCE_V Or compliance_V > MV_HELM_MAX_COMPLIANCE_V Then
        MV_SetError "Helm compliance out of range (0..20 V): " & CStr(compliance_V)
        Helm_ConfigSource = False
        Exit Function
    End If
    If nplc < MV_HELM_MIN_NPLC Or nplc > MV_HELM_MAX_NPLC Then
        MV_SetError "Helm NPLC out of range (0.01..20): " & CStr(nplc)
        Helm_ConfigSource = False
        Exit Function
    End If

    MV_HelmCompliance_V = compliance_V
    MV_HelmNPLC = nplc

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.sense = smua.SENSE_LOCAL") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.sense = smub.SENSE_LOCAL") Then GoTo Fail

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.source.func = smua.OUTPUT_DCAMPS") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.source.func = smub.OUTPUT_DCAMPS") Then GoTo Fail

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.source.autorangei = smua.AUTORANGE_ON") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.source.autorangei = smub.AUTORANGE_ON") Then GoTo Fail

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.source.limitv = " & CStr(MV_HelmCompliance_V)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.source.limitv = " & CStr(MV_HelmCompliance_V)) Then GoTo Fail

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.measure.nplc = " & CStr(MV_HelmNPLC)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.measure.nplc = " & CStr(MV_HelmNPLC)) Then GoTo Fail

    Helm_ConfigSource = True
    Exit Function
Fail:
    Helm_ConfigSource = False
    Exit Function
EH:
    MV_SetError "Helm config failed: " & Err.Description
    Helm_ConfigSource = False
End Function

Public Function K2600_OutputOn() As Boolean
    If MV_K2600_Device = "" Then
        MV_SetError "K2600 not connected"
        K2600_OutputOn = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.source.output = smua.OUTPUT_ON") Then
        K2600_OutputOn = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.source.output = smub.OUTPUT_ON") Then
        K2600_OutputOn = False
        Exit Function
    End If

    K2600_OutputOn = True
End Function

Public Function K2600_OutputOff() As Boolean
    On Error Resume Next
    If MV_K2600_Device <> "" Then
        Call MV_GPIB_Write(MV_K2600_Device, "smua.source.output = smua.OUTPUT_OFF")
        Call MV_GPIB_Write(MV_K2600_Device, "smub.source.output = smub.OUTPUT_OFF")
        Call MV_GPIB_Write(MV_K2600_Device, "smua.source.leveli = 0")
        Call MV_GPIB_Write(MV_K2600_Device, "smub.source.leveli = 0")
    End If
    K2600_OutputOff = True
End Function

Public Function Helm_SetField(ByVal targetField_Oe As Double, ByVal rate_G_per_s As Double) As Boolean
    Dim iTotal As Double
    Dim iPerCh As Double

    If Not Helm_ValidateTarget(targetField_Oe, rate_G_per_s) Then
        Helm_SetField = False
        Exit Function
    End If

    iTotal = Helm_FieldToCurrent_A(targetField_Oe)
    iPerCh = iTotal / 2#

    If Not K2600_OutputOn() Then
        Helm_SetField = False
        Exit Function
    End If

    If Not Helm_RampCurrents(iPerCh, iPerCh, rate_G_per_s) Then
        Helm_SetField = False
        Exit Function
    End If

    MV_LastTargetField_Oe = targetField_Oe
    MV_LastTotalCurrent_A = iTotal
    MV_LastCurrentA_A = iPerCh
    MV_LastCurrentB_A = iPerCh

    Helm_SetField = True
End Function

Public Function Helm_WaitStable(ByVal timeout_s As Double, ByVal tolCurrent_A As Double, ByVal stableCount As Integer) As Boolean
    Dim q As String
    Dim iA As Double
    Dim iB As Double
    Dim okCount As Integer
    Dim t0 As Double

    If MV_K2600_Device = "" Then
        MV_SetError "K2600 not connected"
        Helm_WaitStable = False
        Exit Function
    End If

    t0 = Timer
    okCount = 0

    Do
        If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.leveli)", q) Then GoTo Fail
        iA = CDbl(q)

        If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.leveli)", q) Then GoTo Fail
        iB = CDbl(q)

        If Abs(iA - MV_LastCurrentA_A) <= tolCurrent_A And Abs(iB - MV_LastCurrentB_A) <= tolCurrent_A Then
            okCount = okCount + 1
        Else
            okCount = 0
        End If

        If okCount >= stableCount Then
            Helm_WaitStable = True
            Exit Function
        End If

        MV_WaitSeconds MV_DEFAULT_POLL_S
        DoEvents
    Loop While (Timer - t0) < timeout_s

Fail:
    MV_SetError "Helmholtz stability timeout"
    Helm_WaitStable = False
End Function

Public Function Helm_GetAppliedCurrents_A(ByRef currentA_A As Double, ByRef currentB_A As Double) As Boolean
    Dim q As String
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.leveli)", q) Then
        Helm_GetAppliedCurrents_A = False
        Exit Function
    End If
    currentA_A = CDbl(q)

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.leveli)", q) Then
        Helm_GetAppliedCurrents_A = False
        Exit Function
    End If
    currentB_A = CDbl(q)

    Helm_GetAppliedCurrents_A = True
End Function

Public Function Helm_MeasureResistances_Ohm(ByVal nplc As Double, ByRef resistanceA_Ohm As Double, ByRef resistanceB_Ohm As Double) As Boolean
    Dim q As String

    If Not MV_GPIB_Write(MV_K2600_Device, "smua.measure.nplc = " & CStr(nplc)) Then
        Helm_MeasureResistances_Ohm = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2600_Device, "smub.measure.nplc = " & CStr(nplc)) Then
        Helm_MeasureResistances_Ohm = False
        Exit Function
    End If

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.measure.r())", q) Then
        Helm_MeasureResistances_Ohm = False
        Exit Function
    End If
    resistanceA_Ohm = CDbl(q)

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.measure.r())", q) Then
        Helm_MeasureResistances_Ohm = False
        Exit Function
    End If
    resistanceB_Ohm = CDbl(q)

    Helm_MeasureResistances_Ohm = True
End Function

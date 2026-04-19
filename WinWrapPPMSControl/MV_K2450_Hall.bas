'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"

Option Explicit

Private MV_K2450_OutputEnabled As Boolean

Public Function K2450_Connect(Optional ByVal resource As String = "") As Boolean
    If resource = "" Then resource = MV_K2450_RESOURCE
    K2450_Connect = MV_GPIB_Connect(resource, MV_K2450_Device)
    If K2450_Connect Then MV_K2450_OutputEnabled = False
End Function

Public Function K2450_Disconnect(Optional ByVal rampToZero As Boolean = True) As Boolean
    On Error Resume Next
    If rampToZero Then
        Call K2450_RampSourceToZero()
    End If
    Call K2450_OutputOff()
    Call MV_GPIB_Disconnect(MV_K2450_Device)
    MV_K2450_OutputEnabled = False
    K2450_Disconnect = True
End Function

Public Function K2450_OutputOn() As Boolean
    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_OutputOn = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "OUTP ON") Then
        K2450_OutputOn = False
        Exit Function
    End If

    MV_K2450_OutputEnabled = True
    K2450_OutputOn = True
End Function

Public Function K2450_OutputOff() As Boolean
    On Error Resume Next
    If MV_K2450_Device <> "" Then
        Call MV_GPIB_Write(MV_K2450_Device, "OUTP OFF")
    End If
    MV_K2450_OutputEnabled = False
    K2450_OutputOff = True
End Function

Public Function K2450_IsOutputOn() As Boolean
    K2450_IsOutputOn = MV_K2450_OutputEnabled
End Function

Public Function Hall_SetCalibration(ByVal vPerG As Double, ByVal vOffset_V As Double) As Boolean
    If Abs(vPerG) < MV_HALL_MIN_ABS_V_PER_G Then
        MV_SetError "Hall vPerG magnitude too small"
        Hall_SetCalibration = False
        Exit Function
    End If
    If vOffset_V < MV_HALL_MIN_OFFSET_V Or vOffset_V > MV_HALL_MAX_OFFSET_V Then
        MV_SetError "Hall offset out of range (-5..5 V): " & CStr(vOffset_V)
        Hall_SetCalibration = False
        Exit Function
    End If

    MV_HallVPerG = vPerG
    MV_HallVOffset = vOffset_V
    Hall_SetCalibration = True
End Function

Public Function Hall_Configure(ByVal current_mA As Double, ByVal compliance_V As Double, ByVal nplc As Double, ByVal avgFilter As Integer) As Boolean
    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        Hall_Configure = False
        Exit Function
    End If

    If current_mA < MV_HALL_MIN_CURRENT_mA Or current_mA > MV_HALL_MAX_CURRENT_mA Then
        MV_SetError "Hall current out of range (0..105 mA): " & CStr(current_mA)
        Hall_Configure = False
        Exit Function
    End If
    If compliance_V < MV_HALL_MIN_COMPLIANCE_V Or compliance_V > MV_HALL_MAX_COMPLIANCE_V Then
        MV_SetError "Hall compliance out of range (0..210 V): " & CStr(compliance_V)
        Hall_Configure = False
        Exit Function
    End If
    If nplc < MV_HALL_MIN_NPLC Or nplc > MV_HALL_MAX_NPLC Then
        MV_SetError "Hall NPLC out of range (0.01..20): " & CStr(nplc)
        Hall_Configure = False
        Exit Function
    End If
    If avgFilter < MV_HALL_MIN_FILTER_COUNT Or avgFilter > MV_HALL_MAX_FILTER_COUNT Then
        MV_SetError "Hall filter count out of range (1..100): " & CStr(avgFilter)
        Hall_Configure = False
        Exit Function
    End If

    MV_HallCurrent_mA = current_mA
    MV_HallCompliance_V = compliance_V
    MV_HallNPLC = nplc
    MV_HallAvgFilter = avgFilter

    If Not MV_GPIB_Write(MV_K2450_Device, "*RST") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "ROUT:TERM REAR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC CURR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR " & CStr(current_mA / 1000#)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR:VLIM " & CStr(compliance_V)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:FUNC 'VOLT'") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:RSEN ON") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:NPLC " & CStr(nplc)) Then GoTo Fail

    MV_K2450_OutputEnabled = False

    Hall_Configure = True
    Exit Function
Fail:
    Hall_Configure = False
End Function

Public Function Hall_MeasureVoltage_V(Optional ByVal tbm_s As Double = 0.05) As Double
    Dim q As String
    Dim i As Integer
    Dim sumV As Double
    Dim readCount As Integer
    Dim targetReads As Integer
    Dim v As Double
    Dim outputWasOn As Boolean

    If MV_K2450_Device = "" Then
        Hall_MeasureVoltage_V = -9.9E99
        Exit Function
    End If

    outputWasOn = MV_K2450_OutputEnabled
    If Not outputWasOn Then
        If Not K2450_OutputOn() Then
            Hall_MeasureVoltage_V = -9.9E99
            Exit Function
        End If
        If tbm_s > 0# Then
            MV_WaitSeconds tbm_s
        End If
    End If

    targetReads = MV_HallAvgFilter
    If targetReads < MV_HALL_MIN_FILTER_COUNT Then targetReads = MV_HALL_MIN_FILTER_COUNT
    If targetReads > MV_HALL_MAX_FILTER_COUNT Then targetReads = MV_HALL_MAX_FILTER_COUNT

    sumV = 0#
    readCount = 0

    For i = 1 To targetReads
        If MV_GPIB_Query(MV_K2450_Device, "MEAS:VOLT?", q) Then
            v = CDbl(q)
            If MV_IsFinite(v) Then
                sumV = sumV + v
                readCount = readCount + 1
            End If
        End If
        DoEvents
    Next

    If readCount > 0 Then
        Hall_MeasureVoltage_V = sumV / CDbl(readCount)
    Else
        Hall_MeasureVoltage_V = -9.9E99
    End If

    If Not outputWasOn Then
        Call K2450_OutputOff()
    End If
End Function

Public Function Hall_ComputeField_Oe(ByVal voltage_V As Double) As Double
    Hall_ComputeField_Oe = (voltage_V - MV_HallVOffset) / MV_HallVPerG
End Function

Public Function Hall_MeasureAndLog(Optional ByVal tbm_s As Double = 0.05) As Boolean
    Dim v As Double
    Dim hallOe As Double

    v = Hall_MeasureVoltage_V(tbm_s)
    If Not MV_IsFinite(v) Then
        MV_SetError "Hall voltage read failed"
        Hall_MeasureAndLog = False
        Exit Function
    End If

    hallOe = Hall_ComputeField_Oe(v)
    Hall_MeasureAndLog = Helm_WriteLogRow(v, hallOe)
End Function

Public Function Hall_CalibrateOffset_V(Optional ByVal tbm_s As Double = 0.05) As Boolean
    ' Measure current Hall voltage and store as zero-field offset (MV_HallVOffset).
    ' Call this while the sample sits at zero applied field.
    ' Returns True and updates MV_HallVOffset on success; False on any fault.
    Dim v As Double

    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected — cannot calibrate Hall offset"
        Hall_CalibrateOffset_V = False
        Exit Function
    End If

    v = Hall_MeasureVoltage_V(tbm_s)
    If Not MV_IsFinite(v) Then
        MV_SetError "Hall offset calibration: voltage read returned non-finite value"
        Hall_CalibrateOffset_V = False
        Exit Function
    End If

    If v < MV_HALL_MIN_OFFSET_V Or v > MV_HALL_MAX_OFFSET_V Then
        MV_SetError "Hall offset out of range (" & CStr(MV_HALL_MIN_OFFSET_V) & ".." & CStr(MV_HALL_MAX_OFFSET_V) & " V): " & CStr(v)
        Hall_CalibrateOffset_V = False
        Exit Function
    End If

    MV_HallVOffset = v
    MV_Log "[HALL] Zero-field offset calibrated: " & CStr(v) & " V  (prev: stored)"
    Hall_CalibrateOffset_V = True
End Function
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"

Option Explicit

Public Const K2450_IV_DIR_START_MAX_MIN_START As Integer = 0
Public Const K2450_IV_DIR_START_MIN_MAX_START As Integer = 1
Public Const K2450_IV_DIR_START_MAX_START As Integer = 2
Public Const K2450_IV_DIR_START_MIN_START As Integer = 3

Private Const MV_K2450_MIN_NPLC As Double = 0.01
Private Const MV_K2450_MAX_NPLC As Double = 20#
Private Const MV_K2450_MIN_AVG_COUNT As Integer = 1
Private Const MV_K2450_MAX_AVG_COUNT As Integer = 100
Private Const MV_K2450_MAX_SOURCE_V As Double = 210#
Private Const MV_K2450_MAX_SOURCE_A As Double = 1.05
Private Const MV_K2450_MAX_COMP_V As Double = 210#
Private Const MV_K2450_MAX_COMP_A As Double = 1.05
Private Const MV_K2450_EPS As Double = 0.000000000001

Private MV_K2450G_SourceMode As String
Private MV_K2450G_SourceSetpoint As Double
Private MV_K2450G_Compliance As Double
Private MV_K2450G_NPLC As Double
Private MV_K2450G_AvgCount As Integer
Private MV_K2450G_Use4Wire As Boolean
Private MV_K2450G_AutoRange As Boolean
Private MV_K2450G_RunId As String
Private MV_K2450G_LastCh As String

Private Function K2450_ParseDouble(ByVal txt As String, ByRef outValue As Double) As Boolean
    On Error GoTo EH
    outValue = CDbl(Trim$(txt))
    K2450_ParseDouble = True
    Exit Function
EH:
    K2450_ParseDouble = False
End Function

Private Function K2450_ClampAvgCount(ByVal avgCount As Integer) As Integer
    If avgCount < MV_K2450_MIN_AVG_COUNT Then avgCount = MV_K2450_MIN_AVG_COUNT
    If avgCount > MV_K2450_MAX_AVG_COUNT Then avgCount = MV_K2450_MAX_AVG_COUNT
    K2450_ClampAvgCount = avgCount
End Function

Private Function K2450_NormalizeSourceMode(ByVal sourceMode As String) As String
    Dim key As String
    key = UCase$(Trim$(sourceMode))

    If key = "CURR" Or key = "CURRENT" Then
        K2450_NormalizeSourceMode = "CURRENT"
    ElseIf key = "VOLT" Or key = "VOLTAGE" Then
        K2450_NormalizeSourceMode = "VOLTAGE"
    Else
        K2450_NormalizeSourceMode = ""
    End If
End Function

Public Function K2450_NormalizeCh(ByVal ch As String) As String
    Dim outCh As String
    outCh = Trim$(ch)
    If outCh = "" Then outCh = "NA"
    If Len(outCh) > 32 Then outCh = Left$(outCh, 32)
    K2450_NormalizeCh = outCh
End Function

Public Function K2450_GetLastError() As String
    K2450_GetLastError = MV_LastError
End Function

Public Function K2450_GetSourceModeText() As String
    K2450_GetSourceModeText = MV_K2450G_SourceMode
End Function

Public Function K2450_GetSourceSetpoint() As Double
    K2450_GetSourceSetpoint = MV_K2450G_SourceSetpoint
End Function

Public Function K2450_GetCompliance() As Double
    K2450_GetCompliance = MV_K2450G_Compliance
End Function

Public Function K2450_GetNPLC() As Double
    K2450_GetNPLC = MV_K2450G_NPLC
End Function

Public Function K2450_GetAvgCount() As Integer
    K2450_GetAvgCount = MV_K2450G_AvgCount
End Function

Public Function K2450_GetWireModeText() As String
    If MV_K2450G_Use4Wire Then
        K2450_GetWireModeText = "4W"
    Else
        K2450_GetWireModeText = "2W"
    End If
End Function

Public Function K2450_GetAutoRangeText() As String
    If MV_K2450G_AutoRange Then
        K2450_GetAutoRangeText = "ON"
    Else
        K2450_GetAutoRangeText = "OFF"
    End If
End Function

Public Function K2450_GetRunId() As String
    K2450_GetRunId = MV_K2450G_RunId
End Function

Public Function K2450_GetLastCh() As String
    K2450_GetLastCh = MV_K2450G_LastCh
End Function

Public Function K2450_ResetToKnownState() As Boolean
    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_ResetToKnownState = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "*RST") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "ROUT:TERM REAR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:FUNC 'VOLT'") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:RSEN ON") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:NPLC " & CStr(MV_DEFAULT_HALL_NPLC)) Then GoTo Fail
    Call K2450_OutputOff

    MV_K2450G_SourceMode = "CURRENT"
    MV_K2450G_SourceSetpoint = 0#
    MV_K2450G_Compliance = MV_DEFAULT_HALL_COMPLIANCE_V
    MV_K2450G_NPLC = MV_DEFAULT_HALL_NPLC
    MV_K2450G_AvgCount = MV_DEFAULT_HALL_FILTER_COUNT
    MV_K2450G_Use4Wire = True
    MV_K2450G_AutoRange = True
    MV_K2450G_LastCh = "NA"

    K2450_ResetToKnownState = True
    Exit Function
Fail:
    K2450_ResetToKnownState = False
End Function

Public Function K2450_ConfigCurrentSource(ByVal source_A As Double, ByVal compliance_V As Double, ByVal nplc As Double, ByVal avgCount As Integer, Optional ByVal use4Wire As Boolean = True, Optional ByVal autoRange As Boolean = True) As Boolean
    Dim rsenState As String
    Dim arState As String

    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_ConfigCurrentSource = False
        Exit Function
    End If

    If Abs(source_A) > MV_K2450_MAX_SOURCE_A Then
        MV_SetError "K2450 current source out of range (+/-1.05 A): " & CStr(source_A)
        K2450_ConfigCurrentSource = False
        Exit Function
    End If
    If compliance_V < 0# Or compliance_V > MV_K2450_MAX_COMP_V Then
        MV_SetError "K2450 voltage compliance out of range (0..210 V): " & CStr(compliance_V)
        K2450_ConfigCurrentSource = False
        Exit Function
    End If
    If nplc < MV_K2450_MIN_NPLC Or nplc > MV_K2450_MAX_NPLC Then
        MV_SetError "K2450 NPLC out of range (0.01..20): " & CStr(nplc)
        K2450_ConfigCurrentSource = False
        Exit Function
    End If

    avgCount = K2450_ClampAvgCount(avgCount)
    If use4Wire Then
        rsenState = "ON"
    Else
        rsenState = "OFF"
    End If
    If autoRange Then
        arState = "ON"
    Else
        arState = "OFF"
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "*RST") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "ROUT:TERM REAR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC CURR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR " & CStr(source_A)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR:VLIM " & CStr(compliance_V)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:FUNC 'VOLT'") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:RSEN " & rsenState) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:NPLC " & CStr(nplc)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:RANG:AUTO " & arState) Then GoTo Fail
    Call K2450_OutputOff

    MV_K2450G_SourceMode = "CURRENT"
    MV_K2450G_SourceSetpoint = source_A
    MV_K2450G_Compliance = compliance_V
    MV_K2450G_NPLC = nplc
    MV_K2450G_AvgCount = avgCount
    MV_K2450G_Use4Wire = use4Wire
    MV_K2450G_AutoRange = autoRange

    K2450_ConfigCurrentSource = True
    Exit Function
Fail:
    K2450_ConfigCurrentSource = False
End Function

Public Function K2450_ConfigVoltageSource(ByVal source_V As Double, ByVal compliance_A As Double, ByVal nplc As Double, ByVal avgCount As Integer, Optional ByVal use4Wire As Boolean = True, Optional ByVal autoRange As Boolean = True) As Boolean
    Dim rsenState As String
    Dim arState As String

    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_ConfigVoltageSource = False
        Exit Function
    End If

    If Abs(source_V) > MV_K2450_MAX_SOURCE_V Then
        MV_SetError "K2450 voltage source out of range (+/-210 V): " & CStr(source_V)
        K2450_ConfigVoltageSource = False
        Exit Function
    End If
    If compliance_A < 0# Or compliance_A > MV_K2450_MAX_COMP_A Then
        MV_SetError "K2450 current compliance out of range (0..1.05 A): " & CStr(compliance_A)
        K2450_ConfigVoltageSource = False
        Exit Function
    End If
    If nplc < MV_K2450_MIN_NPLC Or nplc > MV_K2450_MAX_NPLC Then
        MV_SetError "K2450 NPLC out of range (0.01..20): " & CStr(nplc)
        K2450_ConfigVoltageSource = False
        Exit Function
    End If

    avgCount = K2450_ClampAvgCount(avgCount)
    If use4Wire Then
        rsenState = "ON"
    Else
        rsenState = "OFF"
    End If
    If autoRange Then
        arState = "ON"
    Else
        arState = "OFF"
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "*RST") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "ROUT:TERM REAR") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC VOLT") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:VOLT " & CStr(source_V)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:VOLT:ILIM " & CStr(compliance_A)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:FUNC 'CURR'") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:RSEN " & rsenState) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:NPLC " & CStr(nplc)) Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:RANG:AUTO " & arState) Then GoTo Fail
    Call K2450_OutputOff

    MV_K2450G_SourceMode = "VOLTAGE"
    MV_K2450G_SourceSetpoint = source_V
    MV_K2450G_Compliance = compliance_A
    MV_K2450G_NPLC = nplc
    MV_K2450G_AvgCount = avgCount
    MV_K2450G_Use4Wire = use4Wire
    MV_K2450G_AutoRange = autoRange

    K2450_ConfigVoltageSource = True
    Exit Function
Fail:
    K2450_ConfigVoltageSource = False
End Function

Public Function K2450_SetWireMode(ByVal use4Wire As Boolean) As Boolean
    Dim rsenState As String

    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_SetWireMode = False
        Exit Function
    End If

    If use4Wire Then
        rsenState = "ON"
    Else
        rsenState = "OFF"
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:VOLT:RSEN " & rsenState) Then
        K2450_SetWireMode = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:CURR:RSEN " & rsenState) Then
        K2450_SetWireMode = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2450_Device, "SENS:RES:RSEN " & rsenState) Then
        K2450_SetWireMode = False
        Exit Function
    End If

    MV_K2450G_Use4Wire = use4Wire
    K2450_SetWireMode = True
End Function

Public Function K2450_SetCurrent(ByVal source_A As Double) As Boolean
    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_SetCurrent = False
        Exit Function
    End If
    If Abs(source_A) > MV_K2450_MAX_SOURCE_A Then
        MV_SetError "K2450 current source out of range (+/-1.05 A): " & CStr(source_A)
        K2450_SetCurrent = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC CURR") Then
        K2450_SetCurrent = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR " & CStr(source_A)) Then
        K2450_SetCurrent = False
        Exit Function
    End If

    MV_K2450G_SourceMode = "CURRENT"
    MV_K2450G_SourceSetpoint = source_A
    K2450_SetCurrent = True
End Function

Public Function K2450_SetVoltage(ByVal source_V As Double) As Boolean
    If MV_K2450_Device = "" Then
        MV_SetError "K2450 not connected"
        K2450_SetVoltage = False
        Exit Function
    End If
    If Abs(source_V) > MV_K2450_MAX_SOURCE_V Then
        MV_SetError "K2450 voltage source out of range (+/-210 V): " & CStr(source_V)
        K2450_SetVoltage = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC VOLT") Then
        K2450_SetVoltage = False
        Exit Function
    End If
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:VOLT " & CStr(source_V)) Then
        K2450_SetVoltage = False
        Exit Function
    End If

    MV_K2450G_SourceMode = "VOLTAGE"
    MV_K2450G_SourceSetpoint = source_V
    K2450_SetVoltage = True
End Function

Private Function K2450_MeasureQueryAverage(ByVal queryCmd As String, ByVal ch As String, ByVal settle_s As Double) As Double
    Dim i As Integer
    Dim q As String
    Dim v As Double
    Dim sumV As Double
    Dim readCount As Integer
    Dim targetReads As Integer
    Dim outputWasOn As Boolean

    If MV_K2450_Device = "" Then
        K2450_MeasureQueryAverage = -9.9E99
        Exit Function
    End If

    MV_K2450G_LastCh = K2450_NormalizeCh(ch)

    outputWasOn = K2450_IsOutputOn()
    If Not outputWasOn Then
        If Not K2450_OutputOn() Then
            K2450_MeasureQueryAverage = -9.9E99
            Exit Function
        End If
    End If

    If settle_s > 0# Then MV_WaitSeconds settle_s

    targetReads = K2450_ClampAvgCount(MV_K2450G_AvgCount)
    sumV = 0#
    readCount = 0

    For i = 1 To targetReads
        If MV_GPIB_Query(MV_K2450_Device, queryCmd, q) Then
            If K2450_ParseDouble(q, v) Then
                If MV_IsFinite(v) Then
                    sumV = sumV + v
                    readCount = readCount + 1
                End If
            End If
        End If
        DoEvents
    Next

    If readCount > 0 Then
        K2450_MeasureQueryAverage = sumV / CDbl(readCount)
    Else
        K2450_MeasureQueryAverage = -9.9E99
    End If

    If Not outputWasOn Then
        Call K2450_OutputOff
    End If
End Function

Public Function K2450_MeasureVoltage_V(Optional ByVal ch As String = "", Optional ByVal settle_s As Double = 0.05) As Double
    K2450_MeasureVoltage_V = K2450_MeasureQueryAverage("MEAS:VOLT?", ch, settle_s)
End Function

Public Function K2450_MeasureCurrent_A(Optional ByVal ch As String = "", Optional ByVal settle_s As Double = 0.05) As Double
    K2450_MeasureCurrent_A = K2450_MeasureQueryAverage("MEAS:CURR?", ch, settle_s)
End Function

Public Function K2450_MeasureResistance_Ohm(Optional ByVal ch As String = "", Optional ByVal settle_s As Double = 0.05) As Double
    K2450_MeasureResistance_Ohm = K2450_MeasureQueryAverage("MEAS:RES?", ch, settle_s)
End Function

Public Function K2450_MeasureAll(ByRef outV As Double, ByRef outI As Double, ByRef outR As Double, Optional ByVal ch As String = "", Optional ByVal settle_s As Double = 0.05) As Boolean
    outV = K2450_MeasureVoltage_V(ch, settle_s)
    outI = K2450_MeasureCurrent_A(ch, 0#)

    If MV_IsFinite(outV) And MV_IsFinite(outI) And Abs(outI) > MV_K2450_EPS Then
        outR = outV / outI
    Else
        outR = -9.9E99
    End If

    K2450_MeasureAll = (MV_IsFinite(outV) And MV_IsFinite(outI))
End Function

Private Function K2450_IsArrayAllocatedD(ByRef arr() As Double) As Boolean
    On Error GoTo EH
    Dim n As Long
    n = UBound(arr)
    K2450_IsArrayAllocatedD = (LBound(arr) <= n)
    Exit Function
EH:
    K2450_IsArrayAllocatedD = False
End Function

Private Function K2450_IsArrayAllocatedI(ByRef arr() As Integer) As Boolean
    On Error GoTo EH
    Dim n As Long
    n = UBound(arr)
    K2450_IsArrayAllocatedI = (LBound(arr) <= n)
    Exit Function
EH:
    K2450_IsArrayAllocatedI = False
End Function

Private Sub K2450_AppendPoint(ByRef points() As Double, ByRef segments() As Integer, ByVal value As Double, ByVal segmentId As Integer, Optional ByVal preventDuplicate As Boolean = True)
    Dim n As Long

    If K2450_IsArrayAllocatedD(points) Then
        n = UBound(points)
        If preventDuplicate Then
            If Abs(points(n) - value) <= MV_K2450_EPS Then Exit Sub
        End If
        ReDim Preserve points(0 To n + 1)
        points(n + 1) = value

        If K2450_IsArrayAllocatedI(segments) Then
            ReDim Preserve segments(0 To n + 1)
            segments(n + 1) = segmentId
        End If
    Else
        ReDim points(0 To 0)
        points(0) = value

        ReDim segments(0 To 0)
        segments(0) = segmentId
    End If
End Sub

Private Function K2450_AppendLinearSegment(ByRef points() As Double, ByRef segments() As Integer, ByVal fromVal As Double, ByVal toVal As Double, ByVal stepVal As Double, ByVal segmentId As Integer, ByVal includeFirst As Boolean) As Boolean
    Dim stepAbs As Double
    Dim stepSigned As Double
    Dim x As Double
    Dim reached As Boolean

    stepAbs = Abs(stepVal)
    If stepAbs <= 0# Then
        MV_SetError "IV step must be > 0"
        K2450_AppendLinearSegment = False
        Exit Function
    End If

    If Abs(toVal - fromVal) <= MV_K2450_EPS Then
        If includeFirst Then
            Call K2450_AppendPoint(points, segments, fromVal, segmentId, True)
        End If
        If Not includeFirst Then
            Call K2450_AppendPoint(points, segments, toVal, segmentId, True)
        End If
        K2450_AppendLinearSegment = True
        Exit Function
    End If

    If toVal >= fromVal Then
        stepSigned = stepAbs
    Else
        stepSigned = -stepAbs
    End If

    If includeFirst Then
        Call K2450_AppendPoint(points, segments, fromVal, segmentId, True)
    End If

    x = fromVal
    reached = False
    Do While Not reached
        x = x + stepSigned

        If stepSigned > 0# Then
            If x >= toVal Then
                x = toVal
                reached = True
            End If
        Else
            If x <= toVal Then
                x = toVal
                reached = True
            End If
        End If

        Call K2450_AppendPoint(points, segments, x, segmentId, True)
    Loop

    K2450_AppendLinearSegment = True
End Function

Private Function K2450_IV_BuildSetpointsCore(ByVal startVal As Double, ByVal maxVal As Double, ByVal minVal As Double, ByVal stepVal As Double, ByVal directionMode As Integer, ByRef points() As Double, ByRef segments() As Integer) As Boolean
    Erase points
    Erase segments

    Select Case directionMode
        Case K2450_IV_DIR_START_MAX_MIN_START
            If Not K2450_AppendLinearSegment(points, segments, startVal, maxVal, stepVal, 1, True) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, maxVal, minVal, stepVal, 2, False) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, minVal, startVal, stepVal, 3, False) Then GoTo Fail
        Case K2450_IV_DIR_START_MIN_MAX_START
            If Not K2450_AppendLinearSegment(points, segments, startVal, minVal, stepVal, 1, True) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, minVal, maxVal, stepVal, 2, False) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, maxVal, startVal, stepVal, 3, False) Then GoTo Fail
        Case K2450_IV_DIR_START_MAX_START
            If Not K2450_AppendLinearSegment(points, segments, startVal, maxVal, stepVal, 1, True) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, maxVal, startVal, stepVal, 2, False) Then GoTo Fail
        Case K2450_IV_DIR_START_MIN_START
            If Not K2450_AppendLinearSegment(points, segments, startVal, minVal, stepVal, 1, True) Then GoTo Fail
            If Not K2450_AppendLinearSegment(points, segments, minVal, startVal, stepVal, 2, False) Then GoTo Fail
        Case Else
            MV_SetError "Unknown IV direction mode: " & CStr(directionMode)
            GoTo Fail
    End Select

    K2450_IV_BuildSetpointsCore = K2450_IsArrayAllocatedD(points)
    Exit Function
Fail:
    K2450_IV_BuildSetpointsCore = False
End Function

Public Function K2450_IV_BuildSetpoints(ByVal startVal As Double, ByVal maxVal As Double, ByVal minVal As Double, ByVal stepVal As Double, ByVal directionMode As Integer, ByRef points() As Double) As Boolean
    Dim segments() As Integer
    K2450_IV_BuildSetpoints = K2450_IV_BuildSetpointsCore(startVal, maxVal, minVal, stepVal, directionMode, points, segments)
End Function

Private Function K2450_RampSourceTo(ByVal sourceMode As String, ByVal targetVal As Double, ByVal ratePerS As Double) As Boolean
    Dim modeKey As String
    Dim currentVal As Double
    Dim delta As Double
    Dim stepSize As Double
    Dim stepTime_s As Double
    Dim stepCount As Long
    Dim i As Long
    Dim nextVal As Double

    modeKey = K2450_NormalizeSourceMode(sourceMode)
    If modeKey = "" Then
        MV_SetError "Invalid source mode for ramp: " & sourceMode
        K2450_RampSourceTo = False
        Exit Function
    End If

    currentVal = MV_K2450G_SourceSetpoint
    delta = targetVal - currentVal

    If Abs(delta) <= MV_K2450_EPS Then
        K2450_RampSourceTo = True
        Exit Function
    End If

    If ratePerS <= 0# Then
        If modeKey = "CURRENT" Then
            K2450_RampSourceTo = K2450_SetCurrent(targetVal)
        Else
            K2450_RampSourceTo = K2450_SetVoltage(targetVal)
        End If
        Exit Function
    End If

    stepTime_s = MV_DEFAULT_POLL_S
    stepSize = Abs(ratePerS) * stepTime_s
    If stepSize <= MV_K2450_EPS Then
        stepSize = Abs(delta)
    End If

    stepCount = CLng(Int(Abs(delta) / stepSize))
    If (CDbl(stepCount) * stepSize) < Abs(delta) Then
        stepCount = stepCount + 1
    End If
    If stepCount < 1 Then stepCount = 1

    For i = 1 To stepCount
        nextVal = currentVal + delta * (CDbl(i) / CDbl(stepCount))
        If modeKey = "CURRENT" Then
            If Not K2450_SetCurrent(nextVal) Then
                K2450_RampSourceTo = False
                Exit Function
            End If
        Else
            If Not K2450_SetVoltage(nextVal) Then
                K2450_RampSourceTo = False
                Exit Function
            End If
        End If
        If i < stepCount Then MV_WaitSeconds stepTime_s
        DoEvents
    Next

    K2450_RampSourceTo = True
End Function

Public Function K2450_RampSourceToZero(Optional ByVal ratePerS As Double = 0#) As Boolean
    Dim modeKey As String

    modeKey = MV_K2450G_SourceMode
    If modeKey = "" Then modeKey = "CURRENT"

    K2450_RampSourceToZero = K2450_RampSourceTo(modeKey, 0#, ratePerS)
End Function

Public Function K2450_IV_Run(ByVal ch As String, ByVal sourceMode As String, ByVal startVal As Double, ByVal maxVal As Double, ByVal minVal As Double, ByVal stepVal As Double, ByVal directionMode As Integer, ByVal settle_s As Double, Optional ByVal rampToStart As Boolean = True, Optional ByVal rampRatePerS As Double = 0#, Optional ByVal comment As String = "") As Boolean
    Dim points() As Double
    Dim segments() As Integer
    Dim i As Long
    Dim v As Double
    Dim c As Double
    Dim r As Double
    Dim statusTxt As String
    Dim outputWasOn As Boolean
    Dim modeKey As String
    Dim chNorm As String

    modeKey = K2450_NormalizeSourceMode(sourceMode)
    If modeKey = "" Then
        MV_SetError "Invalid IV source mode: " & sourceMode
        K2450_IV_Run = False
        Exit Function
    End If

    chNorm = K2450_NormalizeCh(ch)

    If Not K2450_IV_BuildSetpointsCore(startVal, maxVal, minVal, stepVal, directionMode, points, segments) Then
        K2450_IV_Run = False
        Exit Function
    End If

    outputWasOn = K2450_IsOutputOn()
    If Not outputWasOn Then
        If Not K2450_OutputOn() Then
            K2450_IV_Run = False
            Exit Function
        End If
    End If

    If rampToStart Then
        If Not K2450_RampSourceTo(modeKey, startVal, rampRatePerS) Then GoTo Fail
    End If

    For i = LBound(points) To UBound(points)
        If modeKey = "CURRENT" Then
            If Not K2450_SetCurrent(points(i)) Then GoTo Fail
        Else
            If Not K2450_SetVoltage(points(i)) Then GoTo Fail
        End If

        If settle_s > 0# Then MV_WaitSeconds settle_s

        v = K2450_MeasureVoltage_V(chNorm, 0#)
        c = K2450_MeasureCurrent_A(chNorm, 0#)
        If MV_IsFinite(v) And MV_IsFinite(c) And Abs(c) > MV_K2450_EPS Then
            r = v / c
        Else
            r = -9.9E99
        End If

        statusTxt = "OK"
        If (Not MV_IsFinite(v)) Or (Not MV_IsFinite(c)) Then statusTxt = "READ_FAIL"

        If Not K2450_LogPointMeasured(chNorm, comment, v, c, r, directionMode, segments(i), i - LBound(points), points(i), settle_s, rampToStart, statusTxt) Then
            GoTo Fail
        End If
    Next

    If Not outputWasOn Then
        Call K2450_OutputOff
    End If

    K2450_IV_Run = True
    Exit Function

Fail:
    If Not outputWasOn Then
        Call K2450_OutputOff
    End If
    K2450_IV_Run = False
End Function

Public Function K2450_SetRunId(ByVal runId As String) As Boolean
    MV_K2450G_RunId = Trim$(runId)
    If MV_K2450G_RunId = "" Then MV_K2450G_RunId = "K2450_Run"
    K2450_SetRunId = True
End Function
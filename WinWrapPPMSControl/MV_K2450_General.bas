'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
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
Public Const MV_K2450_EPS As Double = 0.000000000001
Private Const MV_K2450_FAST_CHUNK_POINTS As Long = 2500  ' instrument max list size via SOUR:LIST + APPend
Private Const MV_K2450_FAST_BATCH_MAX_CHARS As Long = 200 ' max CSV payload chars per SOUR:LIST or :APPend write
Private Const MV_K2450_FAST_WAIT_TIMEOUT_S As Double = 30#
Private Const MV_K2450_FAST_TRACE_RETRIES As Integer = 4
Private Const MV_K2450_FAST_TRACE_QUERY_WINDOW As Long = 5000
Private Const MV_K2450_FAST_TRACE_QUERY_TIMEOUT_S As Double = 20#

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
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:CURR:READ:BACK ON") Then GoTo Fail
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
    If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:VOLT:READ:BACK ON") Then GoTo Fail
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

    If UCase$(Trim$(MV_K2450G_SourceMode)) <> "CURRENT" Then
        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC CURR") Then
            K2450_SetCurrent = False
            Exit Function
        End If
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

    If UCase$(Trim$(MV_K2450G_SourceMode)) <> "VOLTAGE" Then
        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:FUNC VOLT") Then
            K2450_SetVoltage = False
            Exit Function
        End If
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

' Query the SOUR element of the last entry in defbuffer1 — returns True and fills outVal
' if SOUR:READ:BACK is ON and the readback is finite; otherwise False (caller uses setpoint).
Private Function K2450_QueryLastSourceReadback(ByRef outVal As Double) As Boolean
    ' defbuffer1 grows by avgCount entries per measurement call.
    ' TRAC:ACT? returns the current fill count; read the last entry for the
    ' most recent source readback value.
    Dim actTxt As String
    Dim actVal As Double
    Dim lastIdx As Long
    Dim q As String
    Dim parsed As Double

    If Not MV_GPIB_Query(MV_K2450_Device, "TRAC:ACT?", actTxt) Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If
    If Not K2450_ParseDouble(actTxt, actVal) Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If
    lastIdx = CLng(actVal)
    If lastIdx < 1 Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If

    If Not MV_GPIB_Query(MV_K2450_Device, "TRAC:DATA? " & CStr(lastIdx) & ", " & CStr(lastIdx) & ", ""defbuffer1"", SOUR", q) Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If
    If Not K2450_ParseDouble(q, parsed) Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If
    If Not MV_IsFinite(parsed) Then
        K2450_QueryLastSourceReadback = False
        Exit Function
    End If
    outVal = parsed
    K2450_QueryLastSourceReadback = True
End Function

Public Function K2450_MeasureAll(ByRef outV As Double, ByRef outI As Double, ByRef outR As Double, Optional ByVal ch As String = "", Optional ByVal settle_s As Double = 0.05) As Boolean
    Dim modeKey As String
    Dim srcReadback As Double

    modeKey = UCase$(Trim$(MV_K2450G_SourceMode))

    If modeKey = "CURRENT" Then
        ' Measure voltage; SOUR:CURR:READ:BACK ON means defbuffer1 also holds actual sourced current.
        outV = K2450_MeasureVoltage_V(ch, settle_s)
        If K2450_QueryLastSourceReadback(srcReadback) Then
            outI = srcReadback
        Else
            outI = MV_K2450G_SourceSetpoint  ' fallback to commanded value
        End If
    ElseIf modeKey = "VOLTAGE" Then
        ' Measure current; SOUR:VOLT:READ:BACK ON means defbuffer1 also holds actual sourced voltage.
        outI = K2450_MeasureCurrent_A(ch, settle_s)
        If K2450_QueryLastSourceReadback(srcReadback) Then
            outV = srcReadback
        Else
            outV = MV_K2450G_SourceSetpoint  ' fallback to commanded value
        End If
    Else
        outV = K2450_MeasureVoltage_V(ch, settle_s)
        outI = K2450_MeasureCurrent_A(ch, 0#)
    End If

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
    If Not K2450_OutputOn() Then
        K2450_IV_Run = False
        Exit Function
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

        If K2450_MeasureAll(v, c, r, chNorm, settle_s) Then
            statusTxt = "OK"
        Else
            statusTxt = "READ_FAIL"
        End If

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

Private Function K2450_CsvFromDoubleRange(ByRef values() As Double, ByVal startIdx As Long, ByVal endIdx As Long) As String
    Dim i As Long
    Dim txt As String

    txt = ""
    For i = startIdx To endIdx
        If txt <> "" Then txt = txt & ","
        txt = txt & CStr(values(i))
    Next

    K2450_CsvFromDoubleRange = txt
End Function

Private Function K2450_ParseCsvDoubles(ByVal txt As String, ByRef outValues() As Double) As Boolean
    Dim parts() As String
    Dim i As Long
    Dim v As Double

    txt = Trim$(txt)
    If txt = "" Then
        K2450_ParseCsvDoubles = False
        Exit Function
    End If

    parts = Split(txt, ",")
    If UBound(parts) < LBound(parts) Then
        K2450_ParseCsvDoubles = False
        Exit Function
    End If

    ReDim outValues(0 To UBound(parts) - LBound(parts))
    For i = LBound(parts) To UBound(parts)
        If Not K2450_ParseDouble(parts(i), v) Then
            K2450_ParseCsvDoubles = False
            Exit Function
        End If
        outValues(i - LBound(parts)) = v
    Next

    K2450_ParseCsvDoubles = True
End Function

Private Function K2450_ParseFirstCsvValue(ByVal txt As String, ByRef outValue As Double) As Boolean
    Dim token As String
    Dim p As Long

    token = Trim$(txt)
    p = InStr(1, token, ",")
    If p > 0 Then token = Left$(token, p - 1)

    K2450_ParseFirstCsvValue = K2450_ParseDouble(token, outValue)
End Function

Private Function K2450_ParseLongScalar(ByVal txt As String, ByRef outVal As Long) As Boolean
    Dim t As String
    Dim d As Double

    t = Trim$(txt)
    If t = "" Then
        K2450_ParseLongScalar = False
        Exit Function
    End If
    If InStr(1, t, ",") > 0 Then
        K2450_ParseLongScalar = False
        Exit Function
    End If
    If Not K2450_ParseDouble(t, d) Then
        K2450_ParseLongScalar = False
        Exit Function
    End If

    outVal = CLng(d)
    If Abs(d - CDbl(outVal)) > 0.0000001 Then
        K2450_ParseLongScalar = False
    Else
        K2450_ParseLongScalar = True
    End If
End Function

Private Function K2450_QueryTraceRangeCsvSingle(ByVal startIdx As Long, ByVal endIdx As Long, ByVal elementName As String, ByRef outValues() As Double) As Boolean
    Dim attempt As Integer
    Dim q As String
    Dim expectedCount As Long
    Dim gotCount As Long
    Dim cmd As String

    expectedCount = endIdx - startIdx + 1
    If expectedCount <= 0 Then
        K2450_QueryTraceRangeCsvSingle = False
        Exit Function
    End If

    cmd = "TRAC:DATA? " & CStr(startIdx) & ", " & CStr(endIdx) & ", ""defbuffer1"", " & elementName

    For attempt = 1 To MV_K2450_FAST_TRACE_RETRIES
        If MV_GPIB_QueryWithTimeout(MV_K2450_Device, cmd, q, MV_K2450_FAST_TRACE_QUERY_TIMEOUT_S, True) Then
            If K2450_ParseCsvDoubles(q, outValues) Then
                gotCount = UBound(outValues) - LBound(outValues) + 1
                If gotCount = expectedCount Then
                    K2450_QueryTraceRangeCsvSingle = True
                    Exit Function
                End If
                If MV_GPIBDebug Then MV_Log "[K2450][FAST][TRACE][retry " & CStr(attempt) & "] " & elementName & " count mismatch got=" & CStr(gotCount) & " expected=" & CStr(expectedCount)
                Call MV_GPIB_DrainDeviceReadBuffer(MV_K2450_Device)
            Else
                If MV_GPIBDebug Then MV_Log "[K2450][FAST][TRACE][retry " & CStr(attempt) & "] " & elementName & " non-CSV reply='" & q & "'"
                Call MV_GPIB_DrainDeviceReadBuffer(MV_K2450_Device)
            End If
        End If

        MV_WaitSeconds 0.01
        DoEvents
    Next

    K2450_QueryTraceRangeCsvSingle = False
End Function

Private Function K2450_QueryTraceRangeCsv(ByVal startIdx As Long, ByVal endIdx As Long, ByVal elementName As String, ByRef outValues() As Double) As Boolean
    Dim expectedCount As Long
    Dim windowStart As Long
    Dim windowEnd As Long
    Dim windowVals() As Double
    Dim writeIdx As Long
    Dim windowCount As Long
    Dim i As Long

    expectedCount = endIdx - startIdx + 1
    If expectedCount <= 0 Then
        K2450_QueryTraceRangeCsv = False
        Exit Function
    End If

    If expectedCount <= MV_K2450_FAST_TRACE_QUERY_WINDOW Then
        K2450_QueryTraceRangeCsv = K2450_QueryTraceRangeCsvSingle(startIdx, endIdx, elementName, outValues)
        Exit Function
    End If

    ReDim outValues(0 To expectedCount - 1)
    writeIdx = 0
    windowStart = startIdx

    Do While windowStart <= endIdx
        windowEnd = windowStart + MV_K2450_FAST_TRACE_QUERY_WINDOW - 1
        If windowEnd > endIdx Then windowEnd = endIdx

        If Not K2450_QueryTraceRangeCsvSingle(windowStart, windowEnd, elementName, windowVals) Then
            K2450_QueryTraceRangeCsv = False
            Exit Function
        End If

        windowCount = UBound(windowVals) - LBound(windowVals) + 1
        For i = 0 To windowCount - 1
            outValues(writeIdx + i) = windowVals(i)
        Next
        writeIdx = writeIdx + windowCount
        windowStart = windowEnd + 1
    Loop

    K2450_QueryTraceRangeCsv = (writeIdx = expectedCount)
End Function

Private Sub K2450_CopySetpointsToSource(ByRef points() As Double, ByVal fromIdx As Long, ByVal toIdx As Long, ByRef outSource() As Double)
    Dim i As Long
    Dim n As Long

    n = toIdx - fromIdx + 1
    If n <= 0 Then Exit Sub

    ReDim outSource(0 To n - 1)
    For i = 0 To n - 1
        outSource(i) = points(fromIdx + i)
    Next
End Sub

Private Function K2450_QueryTraceScalar(ByVal idx1 As Long, ByVal elementName As String, ByRef outVal As Double) As Boolean
    Dim q As String

    If Not MV_GPIB_Query(MV_K2450_Device, "TRAC:DATA? " & CStr(idx1) & ", " & CStr(idx1) & ", ""defbuffer1"", " & elementName, q) Then
        K2450_QueryTraceScalar = False
        Exit Function
    End If

    If Not K2450_ParseFirstCsvValue(q, outVal) Then
        K2450_QueryTraceScalar = False
        Exit Function
    End If

    K2450_QueryTraceScalar = MV_IsFinite(outVal)
End Function

    Private Function K2450_ReadChunkByPoint(ByVal chunkCount As Long, ByRef outRead() As Double) As Boolean
    Dim i As Long
    Dim vRead As Double

    If chunkCount <= 0 Then
        K2450_ReadChunkByPoint = False
        Exit Function
    End If

    ReDim outRead(0 To chunkCount - 1)

    For i = 1 To chunkCount
        If Not K2450_QueryTraceScalar(i, "READ", vRead) Then
            If Not K2450_QueryTraceScalar(i, "READING", vRead) Then
                K2450_ReadChunkByPoint = False
                Exit Function
            End If
        End If

        outRead(i - 1) = vRead
    Next

    K2450_ReadChunkByPoint = True
End Function

' sweepModelReady: set to True by caller after the first successful chunk so that
' SOUR:SWE:CURR:LIST (which rebuilds the trigger model and blinks the output LED)
' is only issued once per sweep run, not on every chunk.
'
' List upload strategy (per manual):
'   - SOUR:LIST:CURR accepts up to 100 values per write (first write)
'   - SOUR:LIST:CURR:APPend accepts up to 100 more per write, total max 2500
'   We send the full point range as batches of MV_K2450_FAST_LIST_BATCH (100),
'   then INIT+WAI once for the entire chunk — one INIT per call instead of one per ~24 points.
Private Function K2450_FastRunChunk(ByVal modeKey As String, ByRef points() As Double, ByVal fromIdx As Long, ByVal toIdx As Long, ByVal settle_s As Double, ByRef outRead() As Double, ByRef outSource() As Double, ByRef sweepModelReady As Boolean) As Boolean
    Dim chunkCount As Long
    Dim readVals() As Double
    Dim okReadBulk As Boolean
    Dim batchCsv As String
    Dim valStr As String
    Dim firstBatch As Boolean
    Dim i As Long

    chunkCount = toIdx - fromIdx + 1
    If chunkCount <= 0 Then
        MV_SetError "K2450 fast chunk count is zero"
        K2450_FastRunChunk = False
        Exit Function
    End If

    Call MV_ClearError

    ' Upload source list in writes that stay within MV_K2450_FAST_BATCH_MAX_CHARS.
    ' First write uses SOUR:LIST:CURR; subsequent writes use :APPend.
    ' We build each batch value-by-value so the CSV never overruns the SCPI input buffer.
    firstBatch = True
    batchCsv = ""
    For i = fromIdx To toIdx
        valStr = CStr(points(i))
        ' Flush current batch before it would exceed the char limit.
        If batchCsv <> "" Then
            If Len(batchCsv) + 1 + Len(valStr) > MV_K2450_FAST_BATCH_MAX_CHARS Then
                If firstBatch Then
                    If modeKey = "CURRENT" Then
                        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:CURR " & batchCsv) Then GoTo Fail
                    Else
                        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:VOLT " & batchCsv) Then GoTo Fail
                    End If
                    firstBatch = False
                Else
                    If modeKey = "CURRENT" Then
                        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:CURR:APP " & batchCsv) Then GoTo Fail
                    Else
                        If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:VOLT:APP " & batchCsv) Then GoTo Fail
                    End If
                End If
                batchCsv = ""
            End If
        End If
        If batchCsv = "" Then
            batchCsv = valStr
        Else
            batchCsv = batchCsv & "," & valStr
        End If
    Next i

    ' Flush remaining values.
    If batchCsv <> "" Then
        If firstBatch Then
            If modeKey = "CURRENT" Then
                If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:CURR " & batchCsv) Then GoTo Fail
            Else
                If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:VOLT " & batchCsv) Then GoTo Fail
            End If
        Else
            If modeKey = "CURRENT" Then
                If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:CURR:APP " & batchCsv) Then GoTo Fail
            Else
                If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:LIST:VOLT:APP " & batchCsv) Then GoTo Fail
            End If
        End If
    End If

    If settle_s < 0# Then settle_s = 0#

    If Not MV_GPIB_Write(MV_K2450_Device, "TRAC:CLE ""defbuffer1""") Then GoTo Fail

    ' Build the trigger model only on the first chunk.  Re-running SOUR:SWE:*:LIST on
    ' every chunk reconfigures the instrument's source engine and causes a visible
    ' output-state transition (LED blink) even though OUTP is never toggled by us.
    If Not sweepModelReady Then
        If modeKey = "CURRENT" Then
            If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:SWE:CURR:LIST 1, " & CStr(settle_s)) Then GoTo Fail
        Else
            If Not MV_GPIB_Write(MV_K2450_Device, "SOUR:SWE:VOLT:LIST 1, " & CStr(settle_s)) Then GoTo Fail
        End If
        sweepModelReady = True
    End If

    If Not MV_GPIB_Write(MV_K2450_Device, "INIT") Then GoTo Fail
    If Not MV_GPIB_Write(MV_K2450_Device, "*WAI") Then GoTo Fail

    ' Drain any stale output-buffer text (for example from a prior timed-out OUTP?)
    ' without issuing device clear/reset commands that can disturb trigger state.
    Call MV_GPIB_DrainDeviceReadBuffer(MV_K2450_Device)
    Call MV_ClearError

    okReadBulk = K2450_QueryTraceRangeCsv(1, chunkCount, "READ", readVals)

    If Not okReadBulk Then
        okReadBulk = K2450_QueryTraceRangeCsv(1, chunkCount, "READING", readVals)
    End If

    If Not okReadBulk Then
        If Not K2450_ReadChunkByPoint(chunkCount, readVals) Then
            MV_SetError "K2450 fast read count mismatch"
            K2450_FastRunChunk = False
            Exit Function
        End If
    End If

    outRead = readVals
    Call K2450_CopySetpointsToSource(points, fromIdx, toIdx, outSource)
    K2450_FastRunChunk = True
    Exit Function

Fail:
    K2450_FastRunChunk = False
End Function

Public Function K2450_IV_RunFast(ByVal ch As String, ByVal sourceMode As String, ByVal startVal As Double, ByVal maxVal As Double, ByVal minVal As Double, ByVal stepVal As Double, ByVal directionMode As Integer, ByVal settle_s As Double, Optional ByVal rampToStart As Boolean = True, Optional ByVal rampRatePerS As Double = 0#, Optional ByVal comment As String = "", Optional ByVal tbRefresh_s As Double = 1#) As Boolean
    Dim points() As Double
    Dim segments() As Integer
    Dim vAll() As Double
    Dim iAll() As Double
    Dim rAll() As Double
    Dim chunkRead() As Double
    Dim chunkSource() As Double
    Dim i As Long
    Dim fromIdx As Long
    Dim toIdx As Long
    Dim pointCount As Long
    Dim chunkCount As Long
    Dim chunkSize As Long
    Dim writeIdx As Long
    Dim j As Long
    Dim modeKey As String
    Dim outputWasOn As Boolean
    Dim chNorm As String
    Dim statusTxt As String
    Dim lastPointIdx As Long
    Dim acqStartDate As Date
    Dim acqStartTimer As Double
    Dim logStartDate As Date
    Dim logStartTimer As Double
    Dim acqElapsed_s As Double
    Dim logElapsed_s As Double
    Dim cachedTempK As Double
    Dim cachedFieldOe As Double
    Dim lastTBRefreshDate As Date
    Dim lastTBRefreshTimer As Double
    Dim tbAge_s As Double
    Dim sweepModelReady As Boolean

    modeKey = K2450_NormalizeSourceMode(sourceMode)
    If modeKey = "" Then
        MV_SetError "Invalid IV source mode: " & sourceMode
        K2450_IV_RunFast = False
        Exit Function
    End If

    chNorm = K2450_NormalizeCh(ch)

    If Not K2450_IV_BuildSetpointsCore(startVal, maxVal, minVal, stepVal, directionMode, points, segments) Then
        K2450_IV_RunFast = False
        Exit Function
    End If

    pointCount = UBound(points) - LBound(points) + 1
    If pointCount <= 0 Then
        MV_SetError "K2450 fast sweep has no points"
        K2450_IV_RunFast = False
        Exit Function
    End If

    ReDim vAll(0 To pointCount - 1)
    ReDim iAll(0 To pointCount - 1)

    outputWasOn = K2450_IsOutputOn()

    ' Ensure instrument is idle before editing trace buffer settings.
    Call MV_GPIB_Write(MV_K2450_Device, "ABOR")
    Call MV_GPIB_Write(MV_K2450_Device, "TRIG:LOAD ""EMPTY""")

    ' Pre-size defbuffer1 to exactly the number of sweep points so the instrument
    ' does not need to reallocate memory mid-sweep.  If resize fails on this
    ' firmware/state, continue with existing buffer size instead of aborting startup.
    If Not MV_GPIB_Write(MV_K2450_Device, "TRAC:POIN " & CStr(pointCount) & ", ""defbuffer1""") Then
        If MV_GPIBDebug Then MV_Log "[K2450][FAST][WARN] TRAC:POIN resize failed; continuing"
        Call MV_ClearError
    End If

    If Not K2450_OutputOn() Then
        K2450_IV_RunFast = False
        Exit Function
    End If

    If rampToStart Then
        If Not K2450_RampSourceTo(modeKey, startVal, rampRatePerS) Then GoTo Fail
    End If

    acqStartDate = Date
    acqStartTimer = Timer

    sweepModelReady = False
    writeIdx = 0
    ' Chunk at the instrument list maximum (2500).  K2450_FastRunChunk uploads in
    ' sub-batches of 100 internally, so no -363 overrun risk here.
    chunkSize = MV_K2450_FAST_CHUNK_POINTS
    fromIdx = LBound(points)
    Do While fromIdx <= UBound(points)
        toIdx = fromIdx + chunkSize - 1
        If toIdx > UBound(points) Then toIdx = UBound(points)

    Call MV_ClearError
        If Not K2450_FastRunChunk(modeKey, points, fromIdx, toIdx, settle_s, chunkRead, chunkSource, sweepModelReady) Then
            GoTo Fail
        End If

        chunkCount = UBound(chunkRead) - LBound(chunkRead) + 1
        If chunkCount <= 0 Then GoTo Fail

        If (writeIdx + chunkCount) > pointCount Then
            MV_SetError "K2450 fast sweep chunk overflow"
            GoTo Fail
        End If

        If modeKey = "CURRENT" Then
            For j = 0 To chunkCount - 1
                vAll(writeIdx + j) = chunkRead(j)
                iAll(writeIdx + j) = chunkSource(j)
            Next
        Else
            For j = 0 To chunkCount - 1
                iAll(writeIdx + j) = chunkRead(j)
                vAll(writeIdx + j) = chunkSource(j)
            Next
        End If

        writeIdx = writeIdx + chunkCount

        fromIdx = toIdx + 1
    Loop

    If writeIdx <> pointCount Then
        MV_SetError "K2450 fast sweep point count mismatch"
        GoTo Fail
    End If

    acqElapsed_s = (CDbl(Date - acqStartDate) * 86400#) + (Timer - acqStartTimer)
    If acqElapsed_s < 0# Then acqElapsed_s = 0#

    ReDim rAll(0 To pointCount - 1)
    For i = 0 To pointCount - 1
        If MV_IsFinite(vAll(i)) And MV_IsFinite(iAll(i)) And Abs(iAll(i)) > MV_K2450_EPS Then
            rAll(i) = vAll(i) / iAll(i)
        Else
            rAll(i) = -9.9E99
        End If
    Next

    logStartDate = Date
    logStartTimer = Timer
    If tbRefresh_s < 0# Then tbRefresh_s = 0#

    cachedTempK = DYNA_GetTemperature_K()
    cachedFieldOe = DYNA_GetField_Oe()
    lastTBRefreshDate = Date
    lastTBRefreshTimer = Timer

    statusTxt = "OK"
    For i = LBound(points) To UBound(points)
        j = i - LBound(points)
        If Not MV_IsFinite(vAll(j)) Or Not MV_IsFinite(iAll(j)) Then
            statusTxt = "READ_FAIL"
        Else
            statusTxt = "OK"
        End If

        If K2450_LogUsesFastSchema() Then
            tbAge_s = (CDbl(Date - lastTBRefreshDate) * 86400#) + (Timer - lastTBRefreshTimer)
            If tbAge_s < 0# Then tbAge_s = 0#
            If tbRefresh_s > 0# And tbAge_s >= tbRefresh_s Then
                cachedTempK = DYNA_GetTemperature_K()
                cachedFieldOe = DYNA_GetField_Oe()
                lastTBRefreshDate = Date
                lastTBRefreshTimer = Timer
            End If

            If Not K2450_LogPointFastMeasuredTB(comment, vAll(j), iAll(j), rAll(j), j, statusTxt, cachedTempK, cachedFieldOe) Then
                GoTo Fail
            End If
        Else
            If Not K2450_LogPointMeasured(chNorm, comment, vAll(j), iAll(j), rAll(j), directionMode, segments(i), j, points(i), settle_s, rampToStart, statusTxt) Then
                GoTo Fail
            End If
        End If
    Next

    logElapsed_s = (CDbl(Date - logStartDate) * 86400#) + (Timer - logStartTimer)
    If logElapsed_s < 0# Then logElapsed_s = 0#
    If MV_GPIBDebug Then
        MV_Log "[K2450][FAST] points=" & CStr(pointCount) & ", acq_s=" & Format$(acqElapsed_s, "0.000") & ", post_log_s=" & Format$(logElapsed_s, "0.000")
    End If

    lastPointIdx = UBound(points)
    MV_K2450G_SourceSetpoint = points(lastPointIdx)
    MV_K2450G_SourceMode = modeKey

    If Not outputWasOn Then
        Call K2450_OutputOff
    End If

    K2450_IV_RunFast = True
    Exit Function

Fail:
    If Not outputWasOn Then
        Call K2450_OutputOff
    End If
    K2450_IV_RunFast = False
End Function
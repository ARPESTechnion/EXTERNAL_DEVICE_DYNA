'#Uses "..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_DynaHelpers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_General.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"

Option Explicit

Private MV_K2450DataFile As Object
Private MV_K2450LogPath As String
Private MV_K2450LogSeq As Long
Private MV_K2450LogDetailed As Boolean

Private Const COL_CH As String = "Ch"
Private Const COL_SEQ As String = "Sequence Index"
Private Const COL_RUN_ID As String = "Run ID"
Private Const COL_TEMP_K As String = "Temperature (K)"
Private Const COL_FIELD_OE As String = "Field (Oe)"
Private Const COL_SOURCE_MODE As String = "K2450 Source Mode"
Private Const COL_SOURCE_SETPOINT As String = "K2450 Source Setpoint"
Private Const COL_COMPLIANCE As String = "K2450 Compliance"
Private Const COL_NPLC As String = "K2450 NPLC"
Private Const COL_AVG As String = "K2450 Avg Count"
Private Const COL_WIRE As String = "K2450 Wire Mode"
Private Const COL_AR As String = "K2450 AutoRange"
Private Const COL_OUTPUT As String = "K2450 Output State"
Private Const COL_TARGET_SETPOINT As String = "K2450 Target Setpoint"
Private Const COL_V As String = "K2450 Meas Voltage (V)"
Private Const COL_I As String = "K2450 Meas Current (A)"
Private Const COL_R As String = "K2450 Meas Resistance (Ohm)"
Private Const COL_IV_DIR As String = "IV Direction Mode"
Private Const COL_IV_SEG As String = "IV Segment Index"
Private Const COL_IV_POINT As String = "IV Point Index"
Private Const COL_IV_SETTLE As String = "IV Settle (s)"
Private Const COL_IV_RAMP As String = "IV RampToStart"
Private Const COL_STATUS As String = "Measurement Status"
Private Const COL_VALID As String = "Validity Flag"
Private Const COL_LAST_ERROR As String = "Last Error"

Private Sub K2450Log_SetNumericOrBlank(ByRef rowData() As Variant, ByVal idxLabel As Integer, ByVal idxValue As Integer, ByVal colName As String, ByVal value As Double)
    rowData(idxLabel) = colName
    If MV_IsFinite(value) Then
        rowData(idxValue) = value
    Else
        rowData(idxValue) = ""
    End If
End Sub

Private Function K2450Log_EndsWithIgnoreCase(ByVal txt As String, ByVal suffix As String) As Boolean
    Dim lt As String
    Dim ls As String
    lt = LCase$(txt)
    ls = LCase$(suffix)
    If Len(lt) < Len(ls) Then
        K2450Log_EndsWithIgnoreCase = False
    Else
        K2450Log_EndsWithIgnoreCase = (Right$(lt, Len(ls)) = ls)
    End If
End Function

Private Function K2450Log_BoolText(ByVal x As Boolean) As String
    If x Then
        K2450Log_BoolText = "1"
    Else
        K2450Log_BoolText = "0"
    End If
End Function

Public Function K2450_LogInit(ByVal datPath As String, ByVal runTitle As String, Optional ByVal detailed As Boolean = True) As Boolean
    On Error GoTo EH

    MV_K2450LogPath = datPath
    If Not K2450Log_EndsWithIgnoreCase(MV_K2450LogPath, ".dat") Then
        MV_K2450LogPath = MV_K2450LogPath & ".dat"
    End If

    MV_K2450LogSeq = 0
    MV_K2450LogDetailed = detailed

    If Trim$(runTitle) = "" Then runTitle = "K2450 live log"
    Call K2450_SetRunId(runTitle)

    Set MV_K2450DataFile = New MultiVuDataFile

    MV_K2450DataFile.AddColumn COL_CH
    MV_K2450DataFile.AddColumn COL_SEQ
    MV_K2450DataFile.AddColumn COL_RUN_ID
    MV_K2450DataFile.AddColumn COL_TEMP_K
    MV_K2450DataFile.AddColumn COL_FIELD_OE
    MV_K2450DataFile.AddColumn COL_SOURCE_MODE
    MV_K2450DataFile.AddColumn COL_SOURCE_SETPOINT
    MV_K2450DataFile.AddColumn COL_COMPLIANCE
    MV_K2450DataFile.AddColumn COL_NPLC
    MV_K2450DataFile.AddColumn COL_AVG
    MV_K2450DataFile.AddColumn COL_WIRE
    MV_K2450DataFile.AddColumn COL_AR
    MV_K2450DataFile.AddColumn COL_OUTPUT
    MV_K2450DataFile.AddColumn COL_TARGET_SETPOINT
    MV_K2450DataFile.AddColumn COL_V, mvStartupAxisY1
    MV_K2450DataFile.AddColumn COL_I, mvStartupAxisY2
    MV_K2450DataFile.AddColumn COL_R, mvStartupAxisY3
    MV_K2450DataFile.AddColumn COL_IV_DIR
    MV_K2450DataFile.AddColumn COL_IV_SEG
    MV_K2450DataFile.AddColumn COL_IV_POINT
    MV_K2450DataFile.AddColumn COL_IV_SETTLE
    MV_K2450DataFile.AddColumn COL_IV_RAMP
    MV_K2450DataFile.AddColumn COL_STATUS
    MV_K2450DataFile.AddColumn COL_VALID
    MV_K2450DataFile.AddColumn COL_LAST_ERROR

    MV_K2450DataFile.CreateFileAndWriteHeader MV_K2450LogPath, runTitle, "; WinWrapPPMSControl Keithley2450 live log"

    K2450_LogInit = True
    Exit Function
EH:
    MV_SetError "Init K2450 log failed: " & Err.Description
    K2450_LogInit = False
End Function

Public Function K2450_LogClose() As Boolean
    On Error Resume Next
    Set MV_K2450DataFile = Nothing
    MV_K2450LogPath = ""
    K2450_LogClose = True
End Function

Public Function K2450_LogPoint(Optional ByVal ch As String = "", Optional ByVal comment As String = "") As Boolean
    Dim v As Double
    Dim c As Double
    Dim r As Double
    Dim statusTxt As String

    If Not K2450_MeasureAll(v, c, r, ch, 0.05) Then
        statusTxt = "READ_FAIL"
    Else
        statusTxt = "OK"
    End If

    K2450_LogPoint = K2450_LogPointMeasured(K2450_NormalizeCh(ch), comment, v, c, r, -1, -1, -1, K2450_GetSourceSetpoint(), 0.05, False, statusTxt)
End Function

Public Function K2450_LogPointMeasured(ByVal ch As String, ByVal comment As String, ByVal measV As Double, ByVal measI As Double, ByVal measR As Double, Optional ByVal ivDirectionMode As Integer = -1, Optional ByVal ivSegmentIndex As Long = -1, Optional ByVal ivPointIndex As Long = -1, Optional ByVal targetSetpoint As Double = -9.9E99, Optional ByVal settle_s As Double = 0#, Optional ByVal rampToStart As Boolean = False, Optional ByVal statusTxt As String = "OK") As Boolean
    On Error GoTo EH
    Dim rowData(1 To 52) As Variant
    Dim idx As Integer
    Dim tempK As Double
    Dim fieldOe As Double
    Dim validFlag As String
    Dim chNorm As String

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450 log writer not initialized"
        K2450_LogPointMeasured = False
        Exit Function
    End If

    chNorm = K2450_NormalizeCh(ch)
    tempK = DYNA_GetTemperature_K()
    fieldOe = DYNA_GetField_Oe()

    If MV_IsFinite(measV) And MV_IsFinite(measI) Then
        validFlag = "1"
    Else
        validFlag = "0"
    End If

    MV_K2450LogSeq = MV_K2450LogSeq + 1

    idx = 1
    rowData(idx) = MV_K2450DataFile.GetCommentCol(): idx = idx + 1
    rowData(idx) = comment: idx = idx + 1

    rowData(idx) = COL_CH: idx = idx + 1
    rowData(idx) = chNorm: idx = idx + 1

    rowData(idx) = COL_SEQ: idx = idx + 1
    rowData(idx) = MV_K2450LogSeq: idx = idx + 1

    rowData(idx) = COL_RUN_ID: idx = idx + 1
    rowData(idx) = K2450_GetRunId(): idx = idx + 1

    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_TEMP_K, tempK): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_FIELD_OE, fieldOe): idx = idx + 2

    rowData(idx) = COL_SOURCE_MODE: idx = idx + 1
    rowData(idx) = K2450_GetSourceModeText(): idx = idx + 1

    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_SOURCE_SETPOINT, K2450_GetSourceSetpoint()): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_COMPLIANCE, K2450_GetCompliance()): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_NPLC, K2450_GetNPLC()): idx = idx + 2

    rowData(idx) = COL_AVG: idx = idx + 1
    rowData(idx) = K2450_GetAvgCount(): idx = idx + 1

    rowData(idx) = COL_WIRE: idx = idx + 1
    rowData(idx) = K2450_GetWireModeText(): idx = idx + 1

    rowData(idx) = COL_AR: idx = idx + 1
    rowData(idx) = K2450_GetAutoRangeText(): idx = idx + 1

    rowData(idx) = COL_OUTPUT: idx = idx + 1
    rowData(idx) = K2450Log_BoolText(K2450_IsOutputOn()): idx = idx + 1

    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_TARGET_SETPOINT, targetSetpoint): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_V, measV): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_I, measI): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_R, measR): idx = idx + 2

    rowData(idx) = COL_IV_DIR: idx = idx + 1
    rowData(idx) = ivDirectionMode: idx = idx + 1

    rowData(idx) = COL_IV_SEG: idx = idx + 1
    rowData(idx) = ivSegmentIndex: idx = idx + 1

    rowData(idx) = COL_IV_POINT: idx = idx + 1
    rowData(idx) = ivPointIndex: idx = idx + 1

    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_IV_SETTLE, settle_s): idx = idx + 2

    rowData(idx) = COL_IV_RAMP: idx = idx + 1
    rowData(idx) = K2450Log_BoolText(rampToStart): idx = idx + 1

    rowData(idx) = COL_STATUS: idx = idx + 1
    rowData(idx) = statusTxt: idx = idx + 1

    rowData(idx) = COL_VALID: idx = idx + 1
    rowData(idx) = validFlag: idx = idx + 1

    rowData(idx) = COL_LAST_ERROR: idx = idx + 1
    rowData(idx) = K2450_GetLastError(): idx = idx + 1

    Call MV_K2450DataFile.WriteDataUsingArray(rowData, False)

    K2450_LogPointMeasured = True
    Exit Function
EH:
    MV_SetError "Write K2450 log row failed: " & Err.Description
    K2450_LogPointMeasured = False
End Function
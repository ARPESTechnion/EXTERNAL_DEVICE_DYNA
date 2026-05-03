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
Private MV_K2450LogStartDate As Date
Private MV_K2450LogStartTimer As Double
Private MV_K2450LastElapsed_s As Double
Private MV_K2450BatchWrite As Boolean
Private MV_K2450LogSchema As Integer
Private MV_K2450FastRowBuffer As String
Private MV_K2450FastRowCount As Long

Private Const K2450_LOG_SCHEMA_FULL As Integer = 0
Private Const K2450_LOG_SCHEMA_FAST_MIN As Integer = 1
Private Const K2450_FAST_LOG_FLUSH_ROWS As Long = 200

Private Function K2450Log_ElapsedSeconds() As Double
    Dim elapsed As Double
    elapsed = (CDbl(Date - MV_K2450LogStartDate) * 86400#) + (Timer - MV_K2450LogStartTimer)
    If elapsed < 0# Then elapsed = 0#

    ' Keep log time monotonic in case system clock/timer jumps backwards.
    If elapsed < MV_K2450LastElapsed_s Then elapsed = MV_K2450LastElapsed_s
    MV_K2450LastElapsed_s = elapsed

    K2450Log_ElapsedSeconds = elapsed
End Function

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

Private Function K2450Log_FileExists(ByVal filePath As String) As Boolean
    On Error Resume Next
    K2450Log_FileExists = (Dir$(filePath) <> "")
End Function

Private Function K2450Log_BoolText(ByVal x As Boolean) As String
    If x Then
        K2450Log_BoolText = "1"
    Else
        K2450Log_BoolText = "0"
    End If
End Function

Private Function K2450Log_NumOrBlankText(ByVal value As Double) As String
    If MV_IsFinite(value) Then
        K2450Log_NumOrBlankText = CStr(value)
    Else
        K2450Log_NumOrBlankText = ""
    End If
End Function

Private Function K2450Log_AppendFastRows(ByVal rowsText As String) As Boolean
    Dim fn As Integer

    If rowsText = "" Then
        K2450Log_AppendFastRows = True
        Exit Function
    End If

    On Error GoTo EH
    fn = FreeFile
    Open MV_K2450LogPath For Append As #fn
    Print #fn, rowsText
    Close #fn
    K2450Log_AppendFastRows = True
    Exit Function
EH:
    On Error Resume Next
    If fn <> 0 Then Close #fn
    MV_SetError "Write K2450 fast log batch failed: " & Err.Description
    K2450Log_AppendFastRows = False
End Function

Private Function K2450Log_FlushFastRows() As Boolean
    If MV_K2450FastRowCount <= 0 Or MV_K2450FastRowBuffer = "" Then
        K2450Log_FlushFastRows = True
        Exit Function
    End If

    If Not K2450Log_AppendFastRows(MV_K2450FastRowBuffer) Then
        K2450Log_FlushFastRows = False
        Exit Function
    End If

    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    K2450Log_FlushFastRows = True
End Function

Private Function K2450Log_ParseSchema(ByVal schemaMode As String) As Integer
    Dim m As String

    m = UCase$(Trim$(schemaMode))
    If m = "" Or m = "FULL" Then
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FULL
    ElseIf m = "FAST_MIN" Then
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FAST_MIN
    Else
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FULL
    End If
End Function

Public Function K2450_LogUsesFastSchema() As Boolean
    K2450_LogUsesFastSchema = (MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN)
End Function

Public Function K2450_LogInit(ByVal datPath As String, ByVal runTitle As String, Optional ByVal detailed As Boolean = True, Optional ByVal bufferedWrite As Boolean = False, Optional ByVal schemaMode As String = "FULL", Optional ByVal headerNote As String = "", Optional ByVal appendExisting As Boolean = False) As Boolean
    On Error GoTo EH
    Dim headerText As String
    Dim fileExists As Boolean

    MV_K2450LogPath = datPath
    If Not K2450Log_EndsWithIgnoreCase(MV_K2450LogPath, ".dat") Then
        MV_K2450LogPath = MV_K2450LogPath & ".dat"
    End If

    MV_K2450LogSeq = 0
    MV_K2450LogDetailed = detailed
    MV_K2450BatchWrite = bufferedWrite
    MV_K2450LogSchema = K2450Log_ParseSchema(schemaMode)
    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    fileExists = K2450Log_FileExists(MV_K2450LogPath)

    ' Preserve one time origin when appending multiple IV sweeps to the same file.
    If appendExisting And fileExists Then
        If CDbl(MV_K2450LogStartDate) = 0# Then
            MV_K2450LogStartDate = Date
            MV_K2450LogStartTimer = Timer
            MV_K2450LastElapsed_s = 0#
        End If
    Else
        MV_K2450LogStartDate = Date
        MV_K2450LogStartTimer = Timer
        MV_K2450LastElapsed_s = 0#
    End If

    If Trim$(runTitle) = "" Then runTitle = "K2450 live log"
    Call K2450_SetRunId(runTitle)

    Set MV_K2450DataFile = New MultiVuDataFile

    If MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN Then
        MV_K2450DataFile.AddColumn COL_TEMP_K
        MV_K2450DataFile.AddColumn COL_FIELD_OE
        MV_K2450DataFile.AddColumn COL_V, mvStartupAxisY1
        MV_K2450DataFile.AddColumn COL_I, mvStartupAxisY2
        MV_K2450DataFile.AddColumn COL_R, mvStartupAxisY3
        MV_K2450DataFile.AddColumn COL_IV_POINT
        MV_K2450DataFile.AddColumn COL_STATUS
        headerText = "; Keithley2450 fast log (Time,Temp,Field,V,I,R,IV Point,Status)"
    Else
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
        headerText = "; Keithley2450 live log"
    End If

    If Trim$(headerNote) <> "" Then
        headerText = headerText & " | " & headerNote
    End If

    If appendExisting And fileExists Then
        ' Keep existing file/header and append new rows to it.
    Else
        MV_K2450DataFile.CreateFileAndWriteHeader MV_K2450LogPath, runTitle, headerText
    End If
    If MV_K2450BatchWrite And Not (appendExisting And fileExists) Then
        Call MV_K2450DataFile.BeginBatchWrite
    End If

    K2450_LogInit = True
    Exit Function
EH:
    MV_SetError "Init K2450 log failed: " & Err.Description
    MV_K2450BatchWrite = False
    MV_K2450LogSchema = K2450_LOG_SCHEMA_FULL
    K2450_LogInit = False
End Function

Public Function K2450_LogClose() As Boolean
    On Error Resume Next
    If MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN Then
        Call K2450Log_FlushFastRows
    End If
    If Not MV_K2450DataFile Is Nothing Then
        If MV_K2450BatchWrite Then
            Call MV_K2450DataFile.EndBatchWrite
        End If
    End If
    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    MV_K2450BatchWrite = False
    MV_K2450LogSchema = K2450_LOG_SCHEMA_FULL
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
    Dim rowData(1 To 54) As Variant
    Dim idx As Integer
    Dim tempK As Double
    Dim fieldOe As Double
    Dim elapsed_s As Double
    Dim validFlag As String
    Dim chNorm As String

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450 log writer not initialized"
        K2450_LogPointMeasured = False
        Exit Function
    End If

    If MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN Then
        K2450_LogPointMeasured = K2450_LogPointFastMeasured(comment, measV, measI, measR, ivPointIndex, statusTxt)
        Exit Function
    End If

    chNorm = K2450_NormalizeCh(ch)
    tempK = DYNA_GetTemperature_K()
    fieldOe = DYNA_GetField_Oe()
    elapsed_s = K2450Log_ElapsedSeconds()

    If MV_IsFinite(measV) And MV_IsFinite(measI) Then
        validFlag = "1"
    Else
        validFlag = "0"
    End If

    MV_K2450LogSeq = MV_K2450LogSeq + 1

    idx = 1
    rowData(idx) = MV_K2450DataFile.GetCommentCol(): idx = idx + 1
    rowData(idx) = comment: idx = idx + 1

    rowData(idx) = MV_K2450DataFile.GetTimeCol(): idx = idx + 1
    rowData(idx) = elapsed_s: idx = idx + 1

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

Public Function K2450_LogPointFastMeasuredTB(ByVal comment As String, ByVal measV As Double, ByVal measI As Double, ByVal measR As Double, ByVal ivPointIndex As Long, ByVal statusTxt As String, ByVal tempK As Double, ByVal fieldOe As Double) As Boolean
    On Error GoTo EH
    Dim rowData(1 To 18) As Variant
    Dim idx As Integer
    Dim elapsed_s As Double
    Dim rowLine As String

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450 log writer not initialized"
        K2450_LogPointFastMeasuredTB = False
        Exit Function
    End If

    elapsed_s = K2450Log_ElapsedSeconds()

    ' FAST_MIN + buffered mode: avoid per-row COM/object overhead by buffering rows
    ' and appending plain CSV in larger chunks.
    If MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN And MV_K2450BatchWrite Then
        rowLine = comment & "," & CStr(elapsed_s) & "," & _
                  K2450Log_NumOrBlankText(tempK) & "," & K2450Log_NumOrBlankText(fieldOe) & "," & _
                  K2450Log_NumOrBlankText(measV) & "," & K2450Log_NumOrBlankText(measI) & "," & _
                  K2450Log_NumOrBlankText(measR) & "," & CStr(ivPointIndex) & "," & statusTxt

        If MV_K2450FastRowBuffer = "" Then
            MV_K2450FastRowBuffer = rowLine
        Else
            MV_K2450FastRowBuffer = MV_K2450FastRowBuffer & vbCrLf & rowLine
        End If
        MV_K2450FastRowCount = MV_K2450FastRowCount + 1

        If MV_K2450FastRowCount >= K2450_FAST_LOG_FLUSH_ROWS Then
            If Not K2450Log_FlushFastRows() Then
                K2450_LogPointFastMeasuredTB = False
                Exit Function
            End If
        End If

        K2450_LogPointFastMeasuredTB = True
        Exit Function
    End If

    idx = 1
    rowData(idx) = MV_K2450DataFile.GetCommentCol(): idx = idx + 1
    rowData(idx) = comment: idx = idx + 1

    rowData(idx) = MV_K2450DataFile.GetTimeCol(): idx = idx + 1
    rowData(idx) = elapsed_s: idx = idx + 1

    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_TEMP_K, tempK): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_FIELD_OE, fieldOe): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_V, measV): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_I, measI): idx = idx + 2
    Call K2450Log_SetNumericOrBlank(rowData, idx, idx + 1, COL_R, measR): idx = idx + 2

    rowData(idx) = COL_IV_POINT: idx = idx + 1
    rowData(idx) = ivPointIndex: idx = idx + 1

    rowData(idx) = COL_STATUS: idx = idx + 1
    rowData(idx) = statusTxt: idx = idx + 1

    Call MV_K2450DataFile.WriteDataUsingArray(rowData, False)

    K2450_LogPointFastMeasuredTB = True
    Exit Function
EH:
    MV_SetError "Write K2450 fast log row failed: " & Err.Description
    K2450_LogPointFastMeasuredTB = False
End Function

Private Function K2450_LogPointFastMeasured(ByVal comment As String, ByVal measV As Double, ByVal measI As Double, ByVal measR As Double, ByVal ivPointIndex As Long, ByVal statusTxt As String) As Boolean
    Dim tempK As Double
    Dim fieldOe As Double

    tempK = DYNA_GetTemperature_K()
    fieldOe = DYNA_GetField_Oe()

    K2450_LogPointFastMeasured = K2450_LogPointFastMeasuredTB(comment, measV, measI, measR, ivPointIndex, statusTxt, tempK, fieldOe)
End Function

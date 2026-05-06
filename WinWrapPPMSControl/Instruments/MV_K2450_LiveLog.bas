'#Uses "..\..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses ".\MV_K2450_General.bas"
'#Uses ".\MV_K2450_Hall.bas"

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
Private MV_K2450FastFlushRows As Long
Private MV_K2450FastRowLines() As String
Private MV_K2450FastRowLineCount As Long
Private MV_K2450FastLogFileHandle As Integer   ' Fallback file handle for FAST_MIN schema when batch write unavailable
Private MV_K2450FastLogKeepOpen As Boolean     ' True if keeping file open for FAST_MIN writes

Private Const K2450_LOG_SCHEMA_FULL As Integer = 0
Private Const K2450_LOG_SCHEMA_FAST_MIN As Integer = 1
Private Const K2450_LOG_SCHEMA_CHANNEL_WIDE As Integer = 2
Private Const K2450_FAST_LOG_FLUSH_ROWS_DEFAULT As Long = 1000
Private Const K2450_FAST_LOG_FLUSH_ROWS_MIN As Long = 64
Private Const K2450_FAST_LOG_FLUSH_ROWS_MAX As Long = 4000
Private Const K2450_FAST_LOG_TARGET_CHUNKS As Long = 6

' CHANNEL_WIDE schema state
Private MV_K2450WideChannels() As String   ' channel names registered at log init
Private MV_K2450WideChCount As Long        ' number of registered channels

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

    ' If file handle is open (fallback mode), write directly to it
    If MV_K2450FastLogKeepOpen And MV_K2450FastLogFileHandle <> 0 Then
        Print #MV_K2450FastLogFileHandle, rowsText
        K2450Log_AppendFastRows = True
        Exit Function
    End If

    ' Otherwise open, write, close (slower but always works)
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
    Dim rowsText As String
    Dim i As Long
    Dim tmp() As String

    If MV_K2450FastRowLineCount <= 0 Then
        K2450Log_FlushFastRows = True
        Exit Function
    End If

    If MV_K2450FastRowLineCount = UBound(MV_K2450FastRowLines) Then
        rowsText = Join(MV_K2450FastRowLines, vbCrLf)
    Else
        ReDim tmp(1 To MV_K2450FastRowLineCount)
        For i = 1 To MV_K2450FastRowLineCount
            tmp(i) = MV_K2450FastRowLines(i)
        Next
        rowsText = Join(tmp, vbCrLf)
    End If

    If Not K2450Log_AppendFastRows(rowsText) Then
        K2450Log_FlushFastRows = False
        Exit Function
    End If

    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    MV_K2450FastRowLineCount = 0
    K2450Log_FlushFastRows = True
End Function

Private Function K2450Log_ParseSchema(ByVal schemaMode As String) As Integer
    Dim m As String

    m = UCase$(Trim$(schemaMode))
    If m = "" Or m = "FULL" Then
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FULL
    ElseIf m = "FAST_MIN" Then
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FAST_MIN
    ElseIf m = "CHANNEL_WIDE" Then
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_CHANNEL_WIDE
    Else
        K2450Log_ParseSchema = K2450_LOG_SCHEMA_FULL
    End If
End Function

Private Function K2450Log_AutoFlushRows(ByVal expectedIvPoints As Long) As Long
    Dim target As Long

    If expectedIvPoints <= 0 Then
        K2450Log_AutoFlushRows = K2450_FAST_LOG_FLUSH_ROWS_DEFAULT
        Exit Function
    End If

    ' Aim for a small fixed number of flushes per IV so most write work
    ' happens during acquisition, while still bounding memory usage.
    If expectedIvPoints <= (2 * K2450_FAST_LOG_FLUSH_ROWS_MIN) Then
        target = expectedIvPoints
    Else
        target = CLng((expectedIvPoints + K2450_FAST_LOG_TARGET_CHUNKS - 1) / K2450_FAST_LOG_TARGET_CHUNKS)
    End If

    If target < K2450_FAST_LOG_FLUSH_ROWS_MIN Then target = K2450_FAST_LOG_FLUSH_ROWS_MIN
    If target > K2450_FAST_LOG_FLUSH_ROWS_MAX Then target = K2450_FAST_LOG_FLUSH_ROWS_MAX
    K2450Log_AutoFlushRows = target
End Function

Public Function K2450_LogUsesFastSchema() As Boolean
    K2450_LogUsesFastSchema = (MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN)
End Function

Public Function K2450_LogUsesChannelWideSchema() As Boolean
    K2450_LogUsesChannelWideSchema = (MV_K2450LogSchema = K2450_LOG_SCHEMA_CHANNEL_WIDE)
End Function

Public Function K2450_LogGetElapsedSeconds() As Double
    K2450_LogGetElapsedSeconds = K2450Log_ElapsedSeconds()
End Function

' Write all fast-sweep rows in one call, avoiding per-point function call overhead.
' vArr/iAll/rArr are 0-based arrays of length pointCount.
' tempK and fieldOe are the cached T/B values captured just before post-log.
' logBaseElapsed_s is the elapsed time at the start of post-log phase.
' acqElapsed_s is used to distribute timestamps evenly across the points.
Public Function K2450_LogFastBulkWrite(ByVal comment As String, ByRef vArr() As Double, ByRef iArr() As Double, ByRef rArr() As Double, ByVal pointCount As Long, ByVal tempK As Double, ByVal fieldOe As Double, ByVal logBaseElapsed_s As Double, ByVal acqElapsed_s As Double) As Boolean
    On Error GoTo EH
    Dim i As Long
    Dim elapsed_s As Double
    Dim stepElapsed_s As Double
    Dim tempKTxt As String
    Dim fieldOeTxt As String
    Dim vFin As Boolean
    Dim iFin As Boolean

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450 log writer not initialized"
        K2450_LogFastBulkWrite = False
        Exit Function
    End If

    If MV_K2450LogSchema <> K2450_LOG_SCHEMA_FAST_MIN Then
        MV_SetError "K2450_LogFastBulkWrite: only valid for FAST_MIN schema"
        K2450_LogFastBulkWrite = False
        Exit Function
    End If

    If Not (MV_K2450BatchWrite Or (MV_K2450FastLogKeepOpen And MV_K2450FastLogFileHandle <> 0)) Then
        MV_SetError "K2450_LogFastBulkWrite: no buffered write path available"
        K2450_LogFastBulkWrite = False
        Exit Function
    End If

    If pointCount <= 0 Then
        K2450_LogFastBulkWrite = True
        Exit Function
    End If

    ' Pre-allocate the entire array for all points in one ReDim — no resizing during loop.
    ReDim MV_K2450FastRowLines(1 To pointCount)
    MV_K2450FastRowLineCount = 0

    stepElapsed_s = 0#
    If pointCount > 1 And acqElapsed_s > 0# Then
        stepElapsed_s = acqElapsed_s / CDbl(pointCount - 1)
    End If

    ' Pre-convert shared columns once to avoid per-row function calls.
    tempKTxt = K2450Log_NumOrBlankText(tempK)
    fieldOeTxt = K2450Log_NumOrBlankText(fieldOe)

    For i = 0 To pointCount - 1
        elapsed_s = logBaseElapsed_s + CDbl(i) * stepElapsed_s
        If elapsed_s < MV_K2450LastElapsed_s Then elapsed_s = MV_K2450LastElapsed_s
        MV_K2450LastElapsed_s = elapsed_s

        ' Inline finite checks — avoid K2450Log_NumOrBlankText function call per row.
        vFin = MV_IsFinite(vArr(i))
        iFin = MV_IsFinite(iArr(i))

        MV_K2450FastRowLineCount = MV_K2450FastRowLineCount + 1
        If vFin And iFin Then
            ' rArr(i) is finite by construction (v/i with guard in caller) — CStr is safe.
            MV_K2450FastRowLines(MV_K2450FastRowLineCount) = _
                comment & "," & CStr(elapsed_s) & "," & _
                tempKTxt & "," & fieldOeTxt & "," & _
                CStr(vArr(i)) & "," & CStr(iArr(i)) & "," & _
                CStr(rArr(i)) & "," & CStr(i) & ",OK"
        Else
            MV_K2450FastRowLines(MV_K2450FastRowLineCount) = _
                comment & "," & CStr(elapsed_s) & "," & _
                tempKTxt & "," & fieldOeTxt & "," & _
                K2450Log_NumOrBlankText(vArr(i)) & "," & _
                K2450Log_NumOrBlankText(iArr(i)) & "," & _
                K2450Log_NumOrBlankText(rArr(i)) & "," & CStr(i) & ",READ_FAIL"
        End If
    Next i

    MV_K2450FastRowCount = MV_K2450FastRowLineCount

    ' Single flush of all rows — one Join + one Print instead of N intermediate flushes.
    If Not K2450Log_FlushFastRows() Then
        K2450_LogFastBulkWrite = False
        Exit Function
    End If

    K2450_LogFastBulkWrite = True
    Exit Function
EH:
    MV_SetError "K2450_LogFastBulkWrite failed: " & Err.Description
    K2450_LogFastBulkWrite = False
End Function

Public Function K2450_LogInit(ByVal datPath As String, ByVal runTitle As String, Optional ByVal detailed As Boolean = True, Optional ByVal bufferedWrite As Boolean = False, Optional ByVal schemaMode As String = "FULL", Optional ByVal headerNote As String = "", Optional ByVal appendExisting As Boolean = False, Optional ByVal expectedIvPoints As Long = 0) As Boolean
    On Error GoTo EH
    Dim headerText As String
    Dim fileExists As Boolean

    MV_K2450LogPath = datPath
    If Not MV_EndsWithIgnoreCase(MV_K2450LogPath, ".dat") Then
        MV_K2450LogPath = MV_K2450LogPath & ".dat"
    End If

    MV_K2450LogSeq = 0
    MV_K2450LogDetailed = detailed
    MV_K2450BatchWrite = bufferedWrite
    MV_K2450LogSchema = K2450Log_ParseSchema(schemaMode)
    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    MV_K2450FastFlushRows = K2450_FAST_LOG_FLUSH_ROWS_DEFAULT
    MV_K2450FastRowLineCount = 0
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

    ' For FAST_MIN schema, prefer direct keep-open append path for buffered mode.
    ' This avoids COM row-write overhead and per-flush open/close cycles.
    If MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN Then
        MV_K2450FastFlushRows = K2450Log_AutoFlushRows(expectedIvPoints)
        ReDim MV_K2450FastRowLines(1 To MV_K2450FastFlushRows)
        MV_K2450FastLogFileHandle = 0
        MV_K2450FastLogKeepOpen = False
        If bufferedWrite Then
            On Error Resume Next
            MV_K2450FastLogFileHandle = FreeFile
            Open MV_K2450LogPath For Append As #MV_K2450FastLogFileHandle
            If Err.Number = 0 Then
                MV_K2450FastLogKeepOpen = True
            Else
                Err.Clear
                MV_K2450FastLogKeepOpen = False
            End If
            On Error GoTo EH

            If Not MV_K2450FastLogKeepOpen Then
                ' Degrade gracefully: row-buffering still works, but each flush
                ' will use open/append/close in K2450Log_AppendFastRows.
            End If

            MV_K2450BatchWrite = False
        End If
    ElseIf MV_K2450BatchWrite And Not (appendExisting And fileExists) Then
        ' Non-FAST_MIN path: try batch write with error handling
        On Error Resume Next
        Call MV_K2450DataFile.BeginBatchWrite
        If Err.Number <> 0 Then
            Err.Clear
            MV_K2450BatchWrite = False
        End If
        On Error GoTo EH
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
    ' Close fallback file handle if open
    If MV_K2450FastLogKeepOpen And MV_K2450FastLogFileHandle <> 0 Then
        Close #MV_K2450FastLogFileHandle
        MV_K2450FastLogFileHandle = 0
        MV_K2450FastLogKeepOpen = False
    End If
    If Not MV_K2450DataFile Is Nothing Then
        If MV_K2450BatchWrite Then
            Call MV_K2450DataFile.EndBatchWrite
        End If
    End If
    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    MV_K2450FastRowLineCount = 0
    MV_K2450BatchWrite = False
    MV_K2450LogSchema = K2450_LOG_SCHEMA_FULL
    MV_K2450WideChCount = 0
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

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_TEMP_K, tempK): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_FIELD_OE, fieldOe): idx = idx + 2

    rowData(idx) = COL_SOURCE_MODE: idx = idx + 1
    rowData(idx) = K2450_GetSourceModeText(): idx = idx + 1

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_SOURCE_SETPOINT, K2450_GetSourceSetpoint()): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_COMPLIANCE, K2450_GetCompliance()): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_NPLC, K2450_GetNPLC()): idx = idx + 2

    rowData(idx) = COL_AVG: idx = idx + 1
    rowData(idx) = K2450_GetAvgCount(): idx = idx + 1

    rowData(idx) = COL_WIRE: idx = idx + 1
    rowData(idx) = K2450_GetWireModeText(): idx = idx + 1

    rowData(idx) = COL_AR: idx = idx + 1
    rowData(idx) = K2450_GetAutoRangeText(): idx = idx + 1

    rowData(idx) = COL_OUTPUT: idx = idx + 1
    rowData(idx) = K2450Log_BoolText(K2450_IsOutputOn()): idx = idx + 1

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_TARGET_SETPOINT, targetSetpoint): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_V, measV): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_I, measI): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_R, measR): idx = idx + 2

    rowData(idx) = COL_IV_DIR: idx = idx + 1
    rowData(idx) = ivDirectionMode: idx = idx + 1

    rowData(idx) = COL_IV_SEG: idx = idx + 1
    rowData(idx) = ivSegmentIndex: idx = idx + 1

    rowData(idx) = COL_IV_POINT: idx = idx + 1
    rowData(idx) = ivPointIndex: idx = idx + 1

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_IV_SETTLE, settle_s): idx = idx + 2

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

Public Function K2450_LogPointFastMeasuredTB(ByVal comment As String, ByVal measV As Double, ByVal measI As Double, ByVal measR As Double, ByVal ivPointIndex As Long, ByVal statusTxt As String, ByVal tempK As Double, ByVal fieldOe As Double, Optional ByVal elapsedOverride_s As Double = -1#) As Boolean
    On Error GoTo EH
    Dim rowData(1 To 18) As Variant
    Dim idx As Integer
    Dim elapsed_s As Double
    Dim rowLine As String
    Dim useRowBuffering As Boolean

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450 log writer not initialized"
        K2450_LogPointFastMeasuredTB = False
        Exit Function
    End If

    If elapsedOverride_s >= 0# Then
        elapsed_s = elapsedOverride_s
        If elapsed_s < MV_K2450LastElapsed_s Then elapsed_s = MV_K2450LastElapsed_s
        MV_K2450LastElapsed_s = elapsed_s
    Else
        elapsed_s = K2450Log_ElapsedSeconds()
    End If

    ' FAST_MIN + buffered mode: avoid per-row COM/object overhead by buffering rows
    ' and appending plain CSV in larger chunks. Buffer if either:
    '   - Batch write is active (MultiVuDataFile.BeginBatchWrite), OR
    '   - Fallback file-keep-open is active (direct file I/O)
    useRowBuffering = (MV_K2450LogSchema = K2450_LOG_SCHEMA_FAST_MIN) And _
                      (MV_K2450BatchWrite Or (MV_K2450FastLogKeepOpen And MV_K2450FastLogFileHandle <> 0))

    If useRowBuffering Then
        rowLine = comment & "," & CStr(elapsed_s) & "," & _
                  K2450Log_NumOrBlankText(tempK) & "," & K2450Log_NumOrBlankText(fieldOe) & "," & _
                  K2450Log_NumOrBlankText(measV) & "," & K2450Log_NumOrBlankText(measI) & "," & _
                  K2450Log_NumOrBlankText(measR) & "," & CStr(ivPointIndex) & "," & statusTxt

        MV_K2450FastRowLineCount = MV_K2450FastRowLineCount + 1
        If MV_K2450FastRowLineCount > UBound(MV_K2450FastRowLines) Then
            ReDim Preserve MV_K2450FastRowLines(1 To UBound(MV_K2450FastRowLines) + MV_K2450FastFlushRows)
        End If
        MV_K2450FastRowLines(MV_K2450FastRowLineCount) = rowLine
        MV_K2450FastRowCount = MV_K2450FastRowLineCount

        If MV_K2450FastRowLineCount >= MV_K2450FastFlushRows Then
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

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_TEMP_K, tempK): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_FIELD_OE, fieldOe): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_V, measV): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_I, measI): idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, COL_R, measR): idx = idx + 2

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

' ============================================================
' CHANNEL_WIDE SCHEMA — one file, wide per-channel columns
' for live trace selection in MultiVu.
'
' Schema columns:
'   Time, Temperature (K), Field (Oe), Ch, Source Setpoint,
'   Status, then per registered channel:
'     "V_<ch>"  (Y1), "I_<ch>"  (Y2), "R_<ch>"  (Y3)
'
' Each data row fills only the three columns for the active
' channel; all other channel columns are left blank.  This
' lets MultiVu display an independent live trace per channel.
' ============================================================

' -- Column name helpers -----------------------------------------
Private Function K2450Wide_ColV(ByVal ch As String) As String
    K2450Wide_ColV = "V_" & ch & " (V)"
End Function
Private Function K2450Wide_ColI(ByVal ch As String) As String
    K2450Wide_ColI = "I_" & ch & " (A)"
End Function
Private Function K2450Wide_ColR(ByVal ch As String) As String
    K2450Wide_ColR = "R_" & ch & " (Ohm)"
End Function

' -- Shared metadata column names --------------------------------
Private Const WCOL_TEMP   As String = "Temperature (K)"
Private Const WCOL_FIELD  As String = "Field (Oe)"
Private Const WCOL_CH     As String = "Active Ch"
Private Const WCOL_SRC    As String = "K2450 Source (A)"
Private Const WCOL_STATUS As String = "Status"

' ----------------------------------------------------------------
' K2450_LogInitWide
'   datPath    : full path of the .dat output file (extension added if missing)
'   runTitle   : title string written into the file header
'   chNames()  : 0-based string array of logical channel names, e.g. ("A","B","C","D")
' Returns True on success.
' ----------------------------------------------------------------
Public Function K2450_LogInitWide(ByVal datPath As String, ByVal runTitle As String, ByRef chNames() As String) As Boolean
    On Error GoTo EH
    Dim i As Long
    Dim nCh As Long
    Dim headerText As String

    ' Reset shared module state
    MV_K2450LogPath = datPath
    If Not MV_EndsWithIgnoreCase(MV_K2450LogPath, ".dat") Then
        MV_K2450LogPath = MV_K2450LogPath & ".dat"
    End If

    MV_K2450LogSeq = 0
    MV_K2450LogDetailed = True
    MV_K2450BatchWrite = False
    MV_K2450LogSchema = K2450_LOG_SCHEMA_CHANNEL_WIDE
    MV_K2450FastRowBuffer = ""
    MV_K2450FastRowCount = 0
    MV_K2450LogStartDate = Date
    MV_K2450LogStartTimer = Timer
    MV_K2450LastElapsed_s = 0#

    nCh = UBound(chNames) - LBound(chNames) + 1
    If nCh <= 0 Then
        MV_SetError "K2450_LogInitWide: chNames array is empty"
        K2450_LogInitWide = False
        Exit Function
    End If

    ' Store channel list for row writer
    MV_K2450WideChCount = nCh
    ReDim MV_K2450WideChannels(0 To nCh - 1)
    For i = 0 To nCh - 1
        MV_K2450WideChannels(i) = Trim$(chNames(LBound(chNames) + i))
    Next i

    If Trim$(runTitle) = "" Then runTitle = "K2450 channel-wide log"
    Call K2450_SetRunId(runTitle)

    Set MV_K2450DataFile = New MultiVuDataFile

    ' Shared metadata columns
    MV_K2450DataFile.AddColumn WCOL_TEMP
    MV_K2450DataFile.AddColumn WCOL_FIELD
    MV_K2450DataFile.AddColumn WCOL_CH
    MV_K2450DataFile.AddColumn WCOL_SRC
    MV_K2450DataFile.AddColumn WCOL_STATUS

    ' Per-channel V/I/R columns — each triple is a separate live trace in MultiVu
    For i = 0 To nCh - 1
        MV_K2450DataFile.AddColumn K2450Wide_ColV(MV_K2450WideChannels(i)), mvStartupAxisY1
        MV_K2450DataFile.AddColumn K2450Wide_ColI(MV_K2450WideChannels(i)), mvStartupAxisY2
        MV_K2450DataFile.AddColumn K2450Wide_ColR(MV_K2450WideChannels(i)), mvStartupAxisY3
    Next i

    headerText = "; Keithley2450 channel-wide log | channels=" & Join(MV_K2450WideChannels, ",")
    MV_K2450DataFile.CreateFileAndWriteHeader MV_K2450LogPath, runTitle, headerText

    K2450_LogInitWide = True
    Exit Function
EH:
    MV_SetError "K2450_LogInitWide failed: " & Err.Description
    K2450_LogInitWide = False
End Function

' ----------------------------------------------------------------
' K2450_LogWidePoint
'   activeCh  : logical channel name that was just measured (must match a name from init)
'   measV     : measured voltage (V); use -9.9E99 to mark invalid/blank
'   measI     : measured current (A)
'   measR     : measured resistance (Ohm)
'   comment   : row comment text (written to MultiVu comment column)
'   statusTxt : "OK" or error label written to Status column
' Returns True on success.
' ----------------------------------------------------------------
Public Function K2450_LogWidePoint(ByVal activeCh As String, ByVal measV As Double, ByVal measI As Double, ByVal measR As Double, Optional ByVal comment As String = "", Optional ByVal statusTxt As String = "OK") As Boolean
    On Error GoTo EH
    Dim nCols As Long
    Dim rowData() As Variant
    Dim idx As Integer
    Dim i As Long
    Dim tempK As Double
    Dim fieldOe As Double
    Dim elapsed_s As Double
    Dim chNorm As String
    Dim activeIdx As Long

    If MV_K2450DataFile Is Nothing Then
        MV_SetError "K2450_LogWidePoint: log not initialized (call K2450_LogInitWide first)"
        K2450_LogWidePoint = False
        Exit Function
    End If
    If MV_K2450LogSchema <> K2450_LOG_SCHEMA_CHANNEL_WIDE Then
        MV_SetError "K2450_LogWidePoint: wrong schema (expected CHANNEL_WIDE)"
        K2450_LogWidePoint = False
        Exit Function
    End If

    chNorm = Trim$(activeCh)
    activeIdx = -1
    For i = 0 To MV_K2450WideChCount - 1
        If LCase$(MV_K2450WideChannels(i)) = LCase$(chNorm) Then
            activeIdx = i
            Exit For
        End If
    Next i
    ' Unknown channel: still write a row but fill no per-channel columns
    If activeIdx < 0 Then
        MV_Log "[K2450][WIDE][WARN] active channel '" & chNorm & "' not found in registered channels; row written with blank channel columns"
    End If

    tempK    = DYNA_GetTemperature_K()
    fieldOe  = DYNA_GetField_Oe()
    elapsed_s = K2450Log_ElapsedSeconds()
    MV_K2450LogSeq = MV_K2450LogSeq + 1

    ' 2 prefix slots (comment col + time col) + 5 shared metadata + 3 * nCh per-channel
    nCols = 2 + 2 + 5 * 2 + MV_K2450WideChCount * 3 * 2
    ReDim rowData(1 To nCols)

    idx = 1
    rowData(idx) = MV_K2450DataFile.GetCommentCol(): idx = idx + 1
    rowData(idx) = comment: idx = idx + 1

    rowData(idx) = MV_K2450DataFile.GetTimeCol(): idx = idx + 1
    rowData(idx) = elapsed_s: idx = idx + 1

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, WCOL_TEMP,  tempK):   idx = idx + 2
    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, WCOL_FIELD, fieldOe): idx = idx + 2

    rowData(idx) = WCOL_CH:  idx = idx + 1
    rowData(idx) = chNorm:   idx = idx + 1

    Call MV_SetNumericOrBlank(rowData, idx, idx + 1, WCOL_SRC, K2450_GetSourceSetpoint()): idx = idx + 2

    rowData(idx) = WCOL_STATUS: idx = idx + 1
    rowData(idx) = statusTxt:   idx = idx + 1

    ' Per-channel V/I/R columns — blank for all except the active channel
    For i = 0 To MV_K2450WideChCount - 1
        If i = activeIdx Then
            Call MV_SetNumericOrBlank(rowData, idx, idx + 1, K2450Wide_ColV(MV_K2450WideChannels(i)), measV): idx = idx + 2
            Call MV_SetNumericOrBlank(rowData, idx, idx + 1, K2450Wide_ColI(MV_K2450WideChannels(i)), measI): idx = idx + 2
            Call MV_SetNumericOrBlank(rowData, idx, idx + 1, K2450Wide_ColR(MV_K2450WideChannels(i)), measR): idx = idx + 2
        Else
            rowData(idx) = K2450Wide_ColV(MV_K2450WideChannels(i)): idx = idx + 1
            rowData(idx) = "":                                        idx = idx + 1
            rowData(idx) = K2450Wide_ColI(MV_K2450WideChannels(i)): idx = idx + 1
            rowData(idx) = "":                                        idx = idx + 1
            rowData(idx) = K2450Wide_ColR(MV_K2450WideChannels(i)): idx = idx + 1
            rowData(idx) = "":                                        idx = idx + 1
        End If
    Next i

    Call MV_K2450DataFile.WriteDataUsingArray(rowData, False)

    K2450_LogWidePoint = True
    Exit Function
EH:
    MV_SetError "K2450_LogWidePoint failed: " & Err.Description
    K2450_LogWidePoint = False
End Function

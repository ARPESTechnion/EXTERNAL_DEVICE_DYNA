'#Uses "..\..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "..\Core\MV_Constants.bas"

Option Explicit

' =========================================================
' Column indices in the QD ETO RT data file (0-based, CSV)
' =========================================================
Private Const RT_COL_TEMP  As Long = 2   ' Temperature (K)
Private Const RT_COL_FIELD As Long = 3   ' Field (Oe)
Private Const RT_COL_R_CH1 As Long = 6   ' Resistance Ch1 (Ohms) — populated on Ch1 rows
Private Const RT_COL_R_CH2 As Long = 26  ' Resistance Ch2 (Ohms) — populated on Ch2 rows

Private Const RT_MAX_ROWS As Long = 50000

' =========================================================
' Output column name constants
' =========================================================
Private Const COL_RT_TEMP_K    As String = "Temperature (K)"
Private Const COL_RT_FIELD_OE  As String = "Field (Oe)"
Private Const COL_RT_CH1_R_OHM As String = "Ch1_Resistance_Ohm"
Private Const COL_RT_CH1_DRDT  As String = "Ch1_abs_dRdT_OhmPerK"
Private Const COL_RT_CH2_R_OHM As String = "Ch2_Resistance_Ohm"
Private Const COL_RT_CH2_DRDT  As String = "Ch2_abs_dRdT_OhmPerK"

' =========================================================
' Internal helpers
' =========================================================
' RT_AnalyzeFile
'
'   Reads a QD ETO RT file (alternating Ch1/Ch2 rows),
'   computes per-channel |dR/dT| via central differences,
'   and writes "<source>_Analyzed.dat" with columns:
'     Temperature (K) [X], Field (Oe),
'     Ch1_Resistance_Ohm [Y1], Ch1_abs_dRdT_OhmPerK [Y2],
'     Ch2_Resistance_Ohm [Y3], Ch2_abs_dRdT_OhmPerK [Y4]
'   Off-channel value cells are written blank.
'
'   Returns True on success; False and MV_LastError on failure.
' =========================================================
Public Function RT_AnalyzeFile(ByVal dataFilePath As String, _
                                ByVal analyzeCh1 As Boolean, _
                                ByVal analyzeCh2 As Boolean) As Boolean
    On Error GoTo EH

    If (Not analyzeCh1) And (Not analyzeCh2) Then
        MV_SetError "RT_AnalyzeFile: nothing to analyze (both channels disabled)"
        RT_AnalyzeFile = False
        Exit Function
    End If

    ' ---- Open source file ----
    Dim fso  As Object
    Dim file As Object
    Set fso = CreateObject("Scripting.FileSystemObject")

    If Not fso.FileExists(dataFilePath) Then
        MV_SetError "RT_AnalyzeFile: source file not found: " & dataFilePath
        RT_AnalyzeFile = False
        Exit Function
    End If

    Set file = fso.OpenTextFile(dataFilePath, 1) ' ForReading
    If file Is Nothing Then
        MV_SetError "RT_AnalyzeFile: cannot open file: " & dataFilePath
        RT_AnalyzeFile = False
        Exit Function
    End If

    ' ---- Seek to [Data] section ----
    Dim lineText      As String
    Dim isDataSection As Boolean
    isDataSection = False

    While Not file.AtEndOfStream
        lineText = file.ReadLine
        If InStr(lineText, "[Data]") > 0 Then
            isDataSection = True
            Exit While
        End If
    Wend

    If Not isDataSection Then
        file.Close
        MV_SetError "RT_AnalyzeFile: no [Data] section in: " & dataFilePath
        RT_AnalyzeFile = False
        Exit Function
    End If

    ' Skip CSV column header row
    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine

    ' Skip blank separator line (QD ETO format: one blank line follows the column header)
    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine

    ' ---- Pre-allocate storage ----
    ' Per-row arrays
    Dim rowTemps()  As Double
    Dim rowFields() As Double
    ReDim rowTemps(0 To RT_MAX_ROWS - 1)
    ReDim rowFields(0 To RT_MAX_ROWS - 1)

    ' Per-channel arrays
    Dim ch1Temps()  As Double
    Dim ch1Rs()     As Double
    Dim ch1RowIdx() As Long
    Dim ch2Temps()  As Double
    Dim ch2Rs()     As Double
    Dim ch2RowIdx() As Long
    ReDim ch1Temps(0 To RT_MAX_ROWS - 1)
    ReDim ch1Rs(0 To RT_MAX_ROWS - 1)
    ReDim ch1RowIdx(0 To RT_MAX_ROWS - 1)
    ReDim ch2Temps(0 To RT_MAX_ROWS - 1)
    ReDim ch2Rs(0 To RT_MAX_ROWS - 1)
    ReDim ch2RowIdx(0 To RT_MAX_ROWS - 1)

    Dim rowTotal As Long
    Dim ch1Count As Long
    Dim ch2Count As Long
    rowTotal = 0
    ch1Count = 0
    ch2Count = 0

    ' ---- Read all data rows ----
    Dim parts()   As String
    Dim tempVal   As Double
    Dim fieldVal  As Double
    Dim rCh1Val   As Double
    Dim rCh2Val   As Double
    Dim okTemp    As Boolean
    Dim okField   As Boolean
    Dim okR1      As Boolean
    Dim okR2      As Boolean

    While Not file.AtEndOfStream And rowTotal < RT_MAX_ROWS
        lineText = file.ReadLine
        If Len(Trim$(lineText)) > 0 Then
            parts = Split(lineText, ",")

            okTemp  = False
            okField = False
            If UBound(parts) >= RT_COL_TEMP Then
                okTemp = MV_TryParseDouble(parts(RT_COL_TEMP), tempVal)
            End If
            If UBound(parts) >= RT_COL_FIELD Then
                okField = MV_TryParseDouble(parts(RT_COL_FIELD), fieldVal)
            End If

            If okTemp And okField Then
                okR1 = False
                okR2 = False
                If UBound(parts) >= RT_COL_R_CH1 Then
                    okR1 = MV_TryParseDouble(parts(RT_COL_R_CH1), rCh1Val)
                End If
                If UBound(parts) >= RT_COL_R_CH2 Then
                    okR2 = MV_TryParseDouble(parts(RT_COL_R_CH2), rCh2Val)
                End If

                rowTemps(rowTotal)  = tempVal
                rowFields(rowTotal) = fieldVal

                If okR1 Then
                    ch1Temps(ch1Count)  = tempVal
                    ch1Rs(ch1Count)     = rCh1Val
                    ch1RowIdx(ch1Count) = rowTotal
                    ch1Count = ch1Count + 1
                End If

                If okR2 Then
                    ch2Temps(ch2Count)  = tempVal
                    ch2Rs(ch2Count)     = rCh2Val
                    ch2RowIdx(ch2Count) = rowTotal
                    ch2Count = ch2Count + 1
                End If

                rowTotal = rowTotal + 1
            End If
        End If
    Wend

    file.Close
    Set file = Nothing

    MV_Log "[RT-ANALYSIS] Parsed " & CStr(rowTotal) & " rows; Ch1=" & CStr(ch1Count) & "  Ch2=" & CStr(ch2Count)

    If rowTotal = 0 Then
        MV_SetError "RT_AnalyzeFile: no valid data rows found in: " & dataFilePath
        RT_AnalyzeFile = False
        Exit Function
    End If

    ' ---- Compute |dR/dT| per channel — central differences ----
    Dim ch1dRdT() As Double
    Dim ch2dRdT() As Double
    ReDim ch1dRdT(0 To RT_MAX_ROWS - 1)
    ReDim ch2dRdT(0 To RT_MAX_ROWS - 1)

    Dim idx As Long
    Dim dT  As Double
    Dim dR  As Double

    If analyzeCh1 And ch1Count > 0 Then
        For idx = 0 To ch1Count - 1
            If ch1Count <= 1 Then
                dT = 0#
                dR = 0#
            ElseIf idx = 0 Then
                dT = ch1Temps(1) - ch1Temps(0)
                dR = ch1Rs(1) - ch1Rs(0)
            ElseIf idx = ch1Count - 1 Then
                dT = ch1Temps(ch1Count - 1) - ch1Temps(ch1Count - 2)
                dR = ch1Rs(ch1Count - 1) - ch1Rs(ch1Count - 2)
            Else
                dT = ch1Temps(idx + 1) - ch1Temps(idx - 1)
                dR = ch1Rs(idx + 1) - ch1Rs(idx - 1)
            End If
            If Abs(dT) < 0.000001 Then
                ch1dRdT(idx) = 0#
            Else
                ch1dRdT(idx) = Abs(dR / dT)
            End If
        Next idx
    End If

    If analyzeCh2 And ch2Count > 0 Then
        For idx = 0 To ch2Count - 1
            If ch2Count <= 1 Then
                dT = 0#
                dR = 0#
            ElseIf idx = 0 Then
                dT = ch2Temps(1) - ch2Temps(0)
                dR = ch2Rs(1) - ch2Rs(0)
            ElseIf idx = ch2Count - 1 Then
                dT = ch2Temps(ch2Count - 1) - ch2Temps(ch2Count - 2)
                dR = ch2Rs(ch2Count - 1) - ch2Rs(ch2Count - 2)
            Else
                dT = ch2Temps(idx + 1) - ch2Temps(idx - 1)
                dR = ch2Rs(idx + 1) - ch2Rs(idx - 1)
            End If
            If Abs(dT) < 0.000001 Then
                ch2dRdT(idx) = 0#
            Else
                ch2dRdT(idx) = Abs(dR / dT)
            End If
        Next idx
    End If

    ' ---- Build reverse map: row index → per-channel sub-index ----
    Dim rowToCh1Idx() As Long
    Dim rowToCh2Idx() As Long
    ReDim rowToCh1Idx(0 To rowTotal - 1)
    ReDim rowToCh2Idx(0 To rowTotal - 1)

    Dim r As Long
    For r = 0 To rowTotal - 1
        rowToCh1Idx(r) = -1
        rowToCh2Idx(r) = -1
    Next r
    For idx = 0 To ch1Count - 1
        rowToCh1Idx(ch1RowIdx(idx)) = idx
    Next idx
    For idx = 0 To ch2Count - 1
        rowToCh2Idx(ch2RowIdx(idx)) = idx
    Next idx

    ' ---- Build output path: strip last .dat → _Analyzed.dat ----
    Dim outPath  As String
    Dim lastDot  As Long
    lastDot = InStrRev(dataFilePath, ".")
    If lastDot > 0 Then
        outPath = Left$(dataFilePath, lastDot - 1) & "_Analyzed.dat"
    Else
        outPath = dataFilePath & "_Analyzed.dat"
    End If

    MV_Log "[RT-ANALYSIS] Output: " & outPath

    ' ---- Create output MultiVuDataFile ----
    Dim outFile As Object
    Set outFile = New MultiVuDataFile

    outFile.AddColumn COL_RT_TEMP_K, mvStartupAxisX
    outFile.AddColumn COL_RT_FIELD_OE

    If analyzeCh1 Then
        outFile.AddColumn COL_RT_CH1_R_OHM, mvStartupAxisY1
        outFile.AddColumn COL_RT_CH1_DRDT,  mvStartupAxisY2
    End If

    If analyzeCh2 Then
        outFile.AddColumn COL_RT_CH2_R_OHM, mvStartupAxisY3
        outFile.AddColumn COL_RT_CH2_DRDT,  mvStartupAxisY4
    End If

    outFile.CreateFileAndWriteHeader outPath, "RT post-analysis", "; RT |dR/dT| analysis output"

    ' ---- Compute column base offsets (label at base, value at base+1) ----
    '   rowData layout: label/value pairs in AddColumn order
    '   Indices:  0/1 = Temp,  2/3 = Field,
    '             (if Ch1) 4/5 = Ch1_R,  6/7 = Ch1_dRdT
    '             (if Ch2) ch2Base/ch2Base+1 = Ch2_R,  ch2Base+2/ch2Base+3 = Ch2_dRdT
    Dim ch2Base As Long
    If analyzeCh1 Then
        ch2Base = 8
    Else
        ch2Base = 4
    End If

    Dim nEntries As Long
    nEntries = 4  ' Temp + Field
    If analyzeCh1 Then nEntries = nEntries + 4
    If analyzeCh2 Then nEntries = nEntries + 4

    Dim rowData() As Variant
    ReDim rowData(0 To nEntries - 1)

    ' Pre-fill static label positions (never change)
    rowData(0) = COL_RT_TEMP_K
    rowData(2) = COL_RT_FIELD_OE
    If analyzeCh1 Then
        rowData(4) = COL_RT_CH1_R_OHM
        rowData(6) = COL_RT_CH1_DRDT
    End If
    If analyzeCh2 Then
        rowData(ch2Base)     = COL_RT_CH2_R_OHM
        rowData(ch2Base + 2) = COL_RT_CH2_DRDT
    End If

    ' ---- Write one output row per source data row ----
    Dim chIdx As Long

    For r = 0 To rowTotal - 1
        rowData(1) = rowTemps(r)
        rowData(3) = rowFields(r)

        If analyzeCh1 Then
            chIdx = rowToCh1Idx(r)
            If chIdx >= 0 Then
                rowData(5) = ch1Rs(chIdx)
                rowData(7) = ch1dRdT(chIdx)
            Else
                rowData(5) = ""
                rowData(7) = ""
            End If
        End If

        If analyzeCh2 Then
            chIdx = rowToCh2Idx(r)
            If chIdx >= 0 Then
                rowData(ch2Base + 1) = ch2Rs(chIdx)
                rowData(ch2Base + 3) = ch2dRdT(chIdx)
            Else
                rowData(ch2Base + 1) = ""
                rowData(ch2Base + 3) = ""
            End If
        End If

        Call outFile.WriteDataUsingArray(rowData, False)
    Next r

    Set outFile = Nothing
    MV_Log "[RT-ANALYSIS] Done. " & CStr(rowTotal) & " rows written to: " & outPath
    RT_AnalyzeFile = True
    Exit Function

EarlyEOF:
    If Not (file Is Nothing) Then
        On Error Resume Next
        file.Close
        On Error GoTo 0
    End If
    MV_SetError "RT_AnalyzeFile: unexpected end of file in: " & dataFilePath
    RT_AnalyzeFile = False
    Exit Function

EH:
    If Not (file Is Nothing) Then
        On Error Resume Next
        file.Close
        On Error GoTo 0
    End If
    MV_SetError "RT_AnalyzeFile failed: " & Err.Description
    RT_AnalyzeFile = False
End Function

'#Uses "..\Core\MV_Constants.bas"

Option Explicit

' IV Block Analysis Result Structure
Public Type IV_BlockResult
    ' Block location
    startRowIndex As Long       ' First row of this IV block (0-indexed)
    endRowIndex As Long         ' Last row of this IV block (0-indexed)
    blockIndex As Long          ' Sequential block counter (0-indexed)
    
    ' Linear fit results: V = slope * I + intercept
    resistance_Ohm As Double    ' Slope: dV/dI in Ohms
    offset_V As Double          ' Intercept: V when I=0 in Volts
    fitQuality_R2 As Double     ' R-squared: fit quality [0..1]
    
    ' Row count and validity
    rowCount As Long            ' Number of valid data points in block
    isValid As Boolean          ' True if fit succeeded and data is meaningful
End Type

Public Function IV_LinearRegression(currentArray() As Double, _
                                     voltageArray() As Double, _
                                     ByRef slope As Double, _
                                     ByRef intercept As Double, _
                                     ByRef r2 As Double) As Boolean
    ' Perform least-squares linear regression: V = slope*I + intercept
    ' Inputs: Arrays of current (A) and voltage (V) measurements
    ' Outputs: slope (R in Ohms), intercept (V offset), r2 (fit quality [0..1])
    ' Returns False if input arrays are empty or identical
    
    Dim n As Long
    Dim i As Long
    Dim sumI As Double, sumV As Double, sumI2 As Double, sumIV As Double, sumV2 As Double
    Dim meanI As Double, meanV As Double
    Dim ssReg As Double, ssTot As Double
    Dim denom As Double
    
    If UBound(currentArray) - LBound(currentArray) < 0 Then
        ' Empty array
        IV_LinearRegression = False
        Exit Function
    End If
    
    n = UBound(currentArray) - LBound(currentArray) + 1
    
    If n < 2 Then
        ' Need at least 2 points
        IV_LinearRegression = False
        Exit Function
    End If
    
    ' Compute sums
    For i = LBound(currentArray) To UBound(currentArray)
        sumI = sumI + currentArray(i)
        sumV = sumV + voltageArray(i)
        sumI2 = sumI2 + currentArray(i) * currentArray(i)
        sumIV = sumIV + currentArray(i) * voltageArray(i)
        sumV2 = sumV2 + voltageArray(i) * voltageArray(i)
    Next i
    
    meanI = sumI / n
    meanV = sumV / n
    
    ' Compute slope and intercept
    denom = sumI2 - (sumI * sumI / n)
    
    If Abs(denom) < 1E-12 Then
        ' All currents are identical, no valid fit
        IV_LinearRegression = False
        Exit Function
    End If
    
    slope = (sumIV - (sumI * sumV / n)) / denom
    intercept = meanV - slope * meanI
    
    ' Compute R-squared
    For i = LBound(currentArray) To UBound(currentArray)
        Dim yPred As Double
        yPred = slope * currentArray(i) + intercept
        ssReg = ssReg + (yPred - meanV) * (yPred - meanV)
        ssTot = ssTot + (voltageArray(i) - meanV) * (voltageArray(i) - meanV)
    Next i
    
    If ssTot < 1E-12 Then
        r2 = 0#
    Else
        r2 = ssReg / ssTot
        If r2 < 0# Then r2 = 0#
        If r2 > 1# Then r2 = 1#
    End If
    
    IV_LinearRegression = True
End Function

Public Function IV_ExtractBlockFromFile(filePath As String, _
                                         blockIndex As Long, _
                                         currentColIndex As Long, _
                                         voltageColIndex As Long, _
                                         ByRef result As IV_BlockResult) As Boolean
    ' Extract single IV block from ETO .dat file and compute linear fit.
    ' blockIndex: which block to extract (0-indexed; each block is 1023 rows)
    ' currentColIndex: column index for current data (stored in mA in ETO files)
    ' voltageColIndex: column index for voltage data
    ' Returns True on success with results in 'result' structure
    
    Dim avgTime_s As Double
    Dim gainValue As Double
    Dim hasAvg As Boolean
    Dim hasGain As Boolean

    IV_ExtractBlockFromFile = IV_ExtractBlockWithMetadataFromFile(filePath, _
                                                                  blockIndex, _
                                                                  currentColIndex, _
                                                                  voltageColIndex, _
                                                                  -1, _
                                                                  -1, _
                                                                  result, _
                                                                  avgTime_s, _
                                                                  gainValue, _
                                                                  hasAvg, _
                                                                  hasGain)
End Function

Public Function IV_ExtractBlockWithMetadataFromFile(filePath As String, _
                                                     blockIndex As Long, _
                                                     currentColIndex As Long, _
                                                     voltageColIndex As Long, _
                                                     averagingTimeColIndex As Long, _
                                                     gainColIndex As Long, _
                                                     ByRef result As IV_BlockResult, _
                                                     ByRef averagingTime_s As Double, _
                                                     ByRef gainValue As Double, _
                                                     Optional ByRef hasAveragingTime As Boolean = False, _
                                                     Optional ByRef hasGain As Boolean = False) As Boolean
    Dim fso As Object
    Dim file As Object
    Dim currentArray() As Double
    Dim voltageArray() As Double
    Dim rowCount As Long
    Dim lineText As String
    Dim parts() As String
    Dim i As Long
    Dim isDataSection As Boolean
    Dim blockStartRow As Long
    Dim iA_mA As Double
    Dim vV As Double
    Dim okI As Boolean
    Dim okV As Boolean

    On Error GoTo EH

    averagingTime_s = 0#
    gainValue = 0#
    hasAveragingTime = False
    hasGain = False

    ' Initialize result
    result.blockIndex = blockIndex
    result.startRowIndex = blockIndex * 1023
    result.endRowIndex = result.startRowIndex + 1022
    result.resistance_Ohm = 0#
    result.offset_V = 0#
    result.fitQuality_R2 = 0#
    result.rowCount = 0
    result.isValid = False

    ' Open file
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(filePath) Then
        MV_SetError "IV file not found: " & filePath
        IV_ExtractBlockWithMetadataFromFile = False
        Exit Function
    End If

    Set file = fso.OpenTextFile(filePath, 1) ' ForReading
    If file Is Nothing Then
        MV_SetError "Cannot open IV file: " & filePath
        IV_ExtractBlockWithMetadataFromFile = False
        Exit Function
    End If

    ReDim currentArray(0 To 1022)
    ReDim voltageArray(0 To 1022)

    ' Find [Data] marker
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
        MV_SetError "No [Data] section found in IV file"
        IV_ExtractBlockWithMetadataFromFile = False
        Exit Function
    End If

    ' Skip CSV header row right after [Data]
    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine

    ' Skip blank separator line (QD ETO format: one blank line follows the column header)
    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine

    ' Skip rows until start of target block
    blockStartRow = result.startRowIndex
    For i = 1 To blockStartRow
        If file.AtEndOfStream Then GoTo EarlyEOF
        lineText = file.ReadLine
    Next i

    rowCount = 0
    For i = 1 To 1023
        If file.AtEndOfStream Then Exit For

        lineText = file.ReadLine
        parts = Split(lineText, ",")

        If UBound(parts) >= currentColIndex And UBound(parts) >= voltageColIndex Then
            okI = MV_TryParseDouble(parts(currentColIndex), iA_mA)
            okV = MV_TryParseDouble(parts(voltageColIndex), vV)

            If okI And okV Then
                currentArray(rowCount) = iA_mA / 1000#
                voltageArray(rowCount) = vV

                If (Not hasAveragingTime) And averagingTimeColIndex >= 0 Then
                    If UBound(parts) >= averagingTimeColIndex Then
                        hasAveragingTime = MV_TryParseDouble(parts(averagingTimeColIndex), averagingTime_s)
                    End If
                End If

                If (Not hasGain) And gainColIndex >= 0 Then
                    If UBound(parts) >= gainColIndex Then
                        hasGain = MV_TryParseDouble(parts(gainColIndex), gainValue)
                    End If
                End If

                rowCount = rowCount + 1
            End If
        End If
    Next i

    file.Close

    If rowCount < 2 Then
        result.rowCount = rowCount
        result.isValid = False
        IV_ExtractBlockWithMetadataFromFile = True
        Exit Function
    End If

    ReDim Preserve currentArray(0 To rowCount - 1)
    ReDim Preserve voltageArray(0 To rowCount - 1)

    result.rowCount = rowCount

    If Not IV_LinearRegression(currentArray, voltageArray, result.resistance_Ohm, result.offset_V, result.fitQuality_R2) Then
        result.isValid = False
        IV_ExtractBlockWithMetadataFromFile = True
        Exit Function
    End If

    result.isValid = True
    IV_ExtractBlockWithMetadataFromFile = True
    Exit Function

EarlyEOF:
    file.Close
    MV_SetError "Unexpected end of file while reading IV block " & CStr(blockIndex)
    IV_ExtractBlockWithMetadataFromFile = False
    Exit Function

EH:
    On Error Resume Next
    If Not file Is Nothing Then file.Close
    MV_SetError "IV_ExtractBlockWithMetadataFromFile error: " & Err.Description
    IV_ExtractBlockWithMetadataFromFile = False
End Function

Public Function IV_ExtractBlockTempFieldFromFile(filePath As String, _
                                                 blockIndex As Long, _
                                                 ByRef temp_K As Double, _
                                                 ByRef field_Oe As Double) As Boolean
    Dim fso As Object
    Dim file As Object
    Dim lineText As String
    Dim parts() As String
    Dim i As Long
    Dim blockStartRow As Long
    Dim isDataSection As Boolean
    Dim okTemp As Boolean
    Dim okField As Boolean

    On Error GoTo EH

    temp_K = -9.9E99
    field_Oe = -9.9E99

    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(filePath) Then
        MV_SetError "IV file not found: " & filePath
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

    Set file = fso.OpenTextFile(filePath, 1)
    If file Is Nothing Then
        MV_SetError "Cannot open IV file: " & filePath
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

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
        MV_SetError "No [Data] section found in IV file"
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine   ' CSV column header

    ' Skip blank separator line (QD ETO format: one blank line follows the column header)
    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine

    blockStartRow = blockIndex * 1023
    For i = 1 To blockStartRow
        If file.AtEndOfStream Then GoTo EarlyEOF
        lineText = file.ReadLine
    Next i

    If file.AtEndOfStream Then GoTo EarlyEOF
    lineText = file.ReadLine
    parts = Split(lineText, ",")

    If UBound(parts) < 3 Then
        file.Close
        MV_SetError "IV block row does not contain temperature/field columns"
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

    okTemp = MV_TryParseDouble(parts(2), temp_K)
    okField = MV_TryParseDouble(parts(3), field_Oe)

    file.Close

    If Not okTemp Then temp_K = -9.9E99
    If Not okField Then field_Oe = -9.9E99

    IV_ExtractBlockTempFieldFromFile = True
    Exit Function

EarlyEOF:
    file.Close
    MV_SetError "Unexpected end of file while reading IV block context " & CStr(blockIndex)
    IV_ExtractBlockTempFieldFromFile = False
    Exit Function

EH:
    On Error Resume Next
    If Not file Is Nothing Then file.Close
    MV_SetError "IV_ExtractBlockTempFieldFromFile error: " & Err.Description
    IV_ExtractBlockTempFieldFromFile = False
End Function

Public Function PostMeasureAnalysis(filePath As String, _
                                     blockIndex As Long, _
                                     currentColIndex As Long, _
                                     voltageColIndex As Long, _
                                     ByRef result As IV_BlockResult) As Boolean
    ' Post-measure IV analysis orchestrator.
    ' Extracts single IV block from ETO .dat file, computes linear regression fit.
    ' blockIndex: sequential block number (0-indexed; each block is 1023 rows)
    ' currentColIndex, voltageColIndex: column indices in CSV data
    ' result: Output IV_BlockResult structure with resistance, offset, R²
    ' Returns True on success, handles all errors internally
    
    PostMeasureAnalysis = IV_ExtractBlockFromFile(filePath, blockIndex, currentColIndex, voltageColIndex, result)
End Function

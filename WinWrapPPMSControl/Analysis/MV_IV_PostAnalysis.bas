'#Uses "..\Core\MV_Constants.bas"

Option Explicit

Private Const IV_BLOCK_ROWS As Long = 1023

Private IV_StreamFile As Object
Private IV_StreamPath As String
Private IV_StreamReady As Boolean
Private IV_StreamNextBlock As Long
Private IV_StreamBlockCache As Object

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
    Dim blockLines As Variant

    On Error GoTo EH

    If Not IV_TryGetBlockLines(filePath, blockIndex, blockLines) Then
        IV_ExtractBlockWithMetadataFromFile = False
        Exit Function
    End If

    IV_ExtractBlockWithMetadataFromFile = IV_AnalyzeBlockLines(blockLines, _
                                                               blockIndex, _
                                                               currentColIndex, _
                                                               voltageColIndex, _
                                                               averagingTimeColIndex, _
                                                               gainColIndex, _
                                                               result, _
                                                               averagingTime_s, _
                                                               gainValue, _
                                                               hasAveragingTime, _
                                                               hasGain)
    Exit Function

EH:
    MV_SetError "IV_ExtractBlockWithMetadataFromFile error: " & Err.Description
    IV_ExtractBlockWithMetadataFromFile = False
End Function

Public Function IV_ExtractTwoBlocksWithMetadataFromFile(ByVal filePath As String, _
                                                         ByVal blockCh1 As Long, _
                                                         ByVal blockCh2 As Long, _
                                                         ByVal ch1CurrentColIndex As Long, _
                                                         ByVal ch1VoltageColIndex As Long, _
                                                         ByVal ch1AveragingTimeColIndex As Long, _
                                                         ByVal ch1GainColIndex As Long, _
                                                         ByVal ch2CurrentColIndex As Long, _
                                                         ByVal ch2VoltageColIndex As Long, _
                                                         ByVal ch2AveragingTimeColIndex As Long, _
                                                         ByVal ch2GainColIndex As Long, _
                                                         ByRef resultCh1 As IV_BlockResult, _
                                                         ByRef ch1Avg_s As Double, _
                                                         ByRef ch1Gain As Double, _
                                                         ByRef ch1HasAvg As Boolean, _
                                                         ByRef ch1HasGain As Boolean, _
                                                         ByRef resultCh2 As IV_BlockResult, _
                                                         ByRef ch2Avg_s As Double, _
                                                         ByRef ch2Gain As Double, _
                                                         ByRef ch2HasAvg As Boolean, _
                                                         ByRef ch2HasGain As Boolean) As Boolean
    Dim maxBlock As Long
    Dim linesCh1 As Variant
    Dim linesCh2 As Variant

    On Error GoTo EH

    If blockCh1 >= blockCh2 Then
        maxBlock = blockCh1
    Else
        maxBlock = blockCh2
    End If

    If Not IV_StreamEnsureBlockCached(filePath, maxBlock) Then
        IV_ExtractTwoBlocksWithMetadataFromFile = False
        Exit Function
    End If

    If Not IV_TryGetCachedBlockLines(blockCh1, linesCh1) Then
        IV_ExtractTwoBlocksWithMetadataFromFile = False
        Exit Function
    End If

    If Not IV_TryGetCachedBlockLines(blockCh2, linesCh2) Then
        IV_ExtractTwoBlocksWithMetadataFromFile = False
        Exit Function
    End If

    If Not IV_AnalyzeBlockLines(linesCh1, _
                                blockCh1, _
                                ch1CurrentColIndex, _
                                ch1VoltageColIndex, _
                                ch1AveragingTimeColIndex, _
                                ch1GainColIndex, _
                                resultCh1, _
                                ch1Avg_s, _
                                ch1Gain, _
                                ch1HasAvg, _
                                ch1HasGain) Then
        IV_ExtractTwoBlocksWithMetadataFromFile = False
        Exit Function
    End If

    If Not IV_AnalyzeBlockLines(linesCh2, _
                                blockCh2, _
                                ch2CurrentColIndex, _
                                ch2VoltageColIndex, _
                                ch2AveragingTimeColIndex, _
                                ch2GainColIndex, _
                                resultCh2, _
                                ch2Avg_s, _
                                ch2Gain, _
                                ch2HasAvg, _
                                ch2HasGain) Then
        IV_ExtractTwoBlocksWithMetadataFromFile = False
        Exit Function
    End If

    IV_ExtractTwoBlocksWithMetadataFromFile = True
    Exit Function
EH:
    MV_SetError "IV_ExtractTwoBlocksWithMetadataFromFile error: " & Err.Description
    IV_ExtractTwoBlocksWithMetadataFromFile = False
End Function

Public Function IV_ExtractBlockTempFieldFromFile(filePath As String, _
                                                 blockIndex As Long, _
                                                 ByRef temp_K As Double, _
                                                 ByRef field_Oe As Double) As Boolean
    Dim lineText As String
    Dim blockLines As Variant
    Dim parts() As String
    Dim okTemp As Boolean
    Dim okField As Boolean

    On Error GoTo EH

    temp_K = -9.9E99
    field_Oe = -9.9E99

    If Not IV_TryGetBlockLines(filePath, blockIndex, blockLines) Then
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

    lineText = blockLines(1)
    parts = Split(lineText, ",")

    If UBound(parts) < 3 Then
        MV_SetError "IV block row does not contain temperature/field columns"
        IV_ExtractBlockTempFieldFromFile = False
        Exit Function
    End If

    okTemp = MV_TryParseDouble(parts(2), temp_K)
    okField = MV_TryParseDouble(parts(3), field_Oe)

    If Not okTemp Then temp_K = -9.9E99
    If Not okField Then field_Oe = -9.9E99

    IV_ExtractBlockTempFieldFromFile = True
    Exit Function

EH:
    MV_SetError "IV_ExtractBlockTempFieldFromFile error: " & Err.Description
    IV_ExtractBlockTempFieldFromFile = False
End Function

Public Sub IV_ResetParserCache()
    On Error Resume Next
    If Not IV_StreamFile Is Nothing Then
        IV_StreamFile.Close
    End If
    Set IV_StreamFile = Nothing
    Set IV_StreamBlockCache = Nothing
    IV_StreamPath = ""
    IV_StreamReady = False
    IV_StreamNextBlock = 0
End Sub

Private Function IV_TryGetBlockLines(ByVal filePath As String, ByVal blockIndex As Long, ByRef blockLines As Variant) As Boolean
    If Not IV_StreamEnsureBlockCached(filePath, blockIndex) Then
        IV_TryGetBlockLines = False
        Exit Function
    End If

    IV_TryGetBlockLines = IV_TryGetCachedBlockLines(blockIndex, blockLines)
End Function

Private Function IV_StreamEnsureBlockCached(ByVal filePath As String, ByVal blockIndex As Long) As Boolean
    Dim blockLines() As String
    Dim i As Long

    On Error GoTo EH

    If blockIndex < 0 Then
        MV_SetError "IV block index must be >= 0"
        IV_StreamEnsureBlockCached = False
        Exit Function
    End If

    If Not IV_StreamEnsureOpen(filePath) Then
        IV_StreamEnsureBlockCached = False
        Exit Function
    End If

    If IV_StreamBlockCache.Exists(CStr(blockIndex)) Then
        IV_StreamEnsureBlockCached = True
        Exit Function
    End If

    Do While IV_StreamNextBlock <= blockIndex
        ReDim blockLines(1 To IV_BLOCK_ROWS)
        For i = 1 To IV_BLOCK_ROWS
            If IV_StreamFile.AtEndOfStream Then
                MV_SetError "IV block " & CStr(IV_StreamNextBlock) & " not ready yet in file: " & filePath
                IV_StreamEnsureBlockCached = False
                Exit Function
            End If
            blockLines(i) = IV_StreamFile.ReadLine
        Next i

        IV_StreamBlockCache.Add CStr(IV_StreamNextBlock), blockLines
        IV_StreamNextBlock = IV_StreamNextBlock + 1
    Loop

    IV_StreamEnsureBlockCached = True
    Exit Function
EH:
    MV_SetError "IV_StreamEnsureBlockCached error: " & Err.Description
    IV_StreamEnsureBlockCached = False
End Function

Private Function IV_StreamEnsureOpen(ByVal filePath As String) As Boolean
    Dim fso As Object
    Dim lineText As String
    Dim foundData As Boolean

    On Error GoTo EH

    If IV_StreamReady Then
        If StrComp(IV_StreamPath, filePath, vbTextCompare) = 0 Then
            IV_StreamEnsureOpen = True
            Exit Function
        End If
        IV_ResetParserCache
    End If

    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(filePath) Then
        MV_SetError "IV file not found: " & filePath
        IV_StreamEnsureOpen = False
        Exit Function
    End If

    Set IV_StreamFile = fso.OpenTextFile(filePath, 1)
    If IV_StreamFile Is Nothing Then
        MV_SetError "Cannot open IV file: " & filePath
        IV_StreamEnsureOpen = False
        Exit Function
    End If

    foundData = False
    While Not IV_StreamFile.AtEndOfStream
        lineText = IV_StreamFile.ReadLine
        If InStr(lineText, "[Data]") > 0 Then
            foundData = True
            Exit While
        End If
    Wend

    If Not foundData Then
        IV_ResetParserCache
        MV_SetError "No [Data] section found in IV file"
        IV_StreamEnsureOpen = False
        Exit Function
    End If

    If IV_StreamFile.AtEndOfStream Then
        IV_ResetParserCache
        MV_SetError "Unexpected end of file before CSV header"
        IV_StreamEnsureOpen = False
        Exit Function
    End If
    lineText = IV_StreamFile.ReadLine

    If IV_StreamFile.AtEndOfStream Then
        IV_ResetParserCache
        MV_SetError "Unexpected end of file before data rows"
        IV_StreamEnsureOpen = False
        Exit Function
    End If
    lineText = IV_StreamFile.ReadLine

    Set IV_StreamBlockCache = CreateObject("Scripting.Dictionary")
    IV_StreamPath = filePath
    IV_StreamReady = True
    IV_StreamNextBlock = 0
    IV_StreamEnsureOpen = True
    Exit Function
EH:
    IV_ResetParserCache
    MV_SetError "IV_StreamEnsureOpen error: " & Err.Description
    IV_StreamEnsureOpen = False
End Function

Private Function IV_TryGetCachedBlockLines(ByVal blockIndex As Long, ByRef blockLines As Variant) As Boolean
    If IV_StreamBlockCache Is Nothing Then
        IV_TryGetCachedBlockLines = False
        Exit Function
    End If

    If Not IV_StreamBlockCache.Exists(CStr(blockIndex)) Then
        IV_TryGetCachedBlockLines = False
        Exit Function
    End If

    blockLines = IV_StreamBlockCache(CStr(blockIndex))
    IV_TryGetCachedBlockLines = True
End Function

Private Function IV_AnalyzeBlockLines(ByRef blockLines As Variant, _
                                      ByVal blockIndex As Long, _
                                      ByVal currentColIndex As Long, _
                                      ByVal voltageColIndex As Long, _
                                      ByVal averagingTimeColIndex As Long, _
                                      ByVal gainColIndex As Long, _
                                      ByRef result As IV_BlockResult, _
                                      ByRef averagingTime_s As Double, _
                                      ByRef gainValue As Double, _
                                      ByRef hasAveragingTime As Boolean, _
                                      ByRef hasGain As Boolean) As Boolean
    Dim currentArray() As Double
    Dim voltageArray() As Double
    Dim rowCount As Long
    Dim parts() As String
    Dim i As Long
    Dim iA_mA As Double
    Dim vV As Double
    Dim okI As Boolean
    Dim okV As Boolean
    Dim lineText As String

    On Error GoTo EH

    averagingTime_s = 0#
    gainValue = 0#
    hasAveragingTime = False
    hasGain = False

    result.blockIndex = blockIndex
    result.startRowIndex = blockIndex * IV_BLOCK_ROWS
    result.endRowIndex = result.startRowIndex + (IV_BLOCK_ROWS - 1)
    result.resistance_Ohm = 0#
    result.offset_V = 0#
    result.fitQuality_R2 = 0#
    result.rowCount = 0
    result.isValid = False

    ReDim currentArray(0 To IV_BLOCK_ROWS - 1)
    ReDim voltageArray(0 To IV_BLOCK_ROWS - 1)

    rowCount = 0
    For i = 1 To IV_BLOCK_ROWS
        lineText = blockLines(i)
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

    If rowCount < 2 Then
        result.rowCount = rowCount
        result.isValid = False
        IV_AnalyzeBlockLines = True
        Exit Function
    End If

    ReDim Preserve currentArray(0 To rowCount - 1)
    ReDim Preserve voltageArray(0 To rowCount - 1)

    result.rowCount = rowCount

    If Not IV_LinearRegression(currentArray, voltageArray, result.resistance_Ohm, result.offset_V, result.fitQuality_R2) Then
        result.isValid = False
        IV_AnalyzeBlockLines = True
        Exit Function
    End If

    result.isValid = True
    IV_AnalyzeBlockLines = True
    Exit Function
EH:
    MV_SetError "IV_AnalyzeBlockLines error: " & Err.Description
    IV_AnalyzeBlockLines = False
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

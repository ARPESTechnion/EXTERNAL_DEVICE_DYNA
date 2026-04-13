'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"

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
    
    Dim fso As Object
    Dim file As Object
    Dim currentArray() As Double
    Dim voltageArray() As Double
    Dim rowCount As Long
    Dim startRow As Long
    Dim endRow As Long
    Dim currentRow As Long
    Dim lineText As String
    Dim parts() As String
    Dim i As Long
    Dim j As Long
    Dim dataIdx As Long
    Dim isDataSection As Boolean
    
    On Error GoTo EH
    
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
        IV_ExtractBlockFromFile = False
        Exit Function
    End If
    
    Set file = fso.OpenTextFile(filePath, 1) ' ForReading
    If file Is Nothing Then
        MV_SetError "Cannot open IV file: " & filePath
        IV_ExtractBlockFromFile = False
        Exit Function
    End If
    
    ' Skip header and find [Data] section
    isDataSection = False
    currentRow = 0
    dataIdx = 0
    
    ReDim currentArray(0 To 1022)
    ReDim voltageArray(0 To 1022)
    
    While Not file.AtEndOfStream
        lineText = file.ReadLine
        
        ' Look for [Data] section marker
        If InStr(lineText, "[Data]") > 0 Then
            isDataSection = True
            GoTo SkipToBlock
        End If
    Wend
    
SkipToBlock:
    If Not isDataSection Then
        ' [Data] section not found
        file.Close
        MV_SetError "No [Data] section found in IV file"
        IV_ExtractBlockFromFile = False
        Exit Function
    End If
    
    ' Skip rows until we reach the start of the target block
    For i = 1 To result.startRowIndex
        If file.AtEndOfStream Then GoTo EarlyEOF
        lineText = file.ReadLine
    Next i
    
    ' Read 1023 rows for this block
    rowCount = 0
    For i = 1 To 1023
        If file.AtEndOfStream Then GoTo BlockComplete
        
        lineText = file.ReadLine
        
        ' Parse CSV: split by comma
        parts = Split(lineText, ",")
        
        If UBound(parts) >= voltageColIndex Then
            On Error Resume Next
            currentArray(rowCount) = CDbl(parts(currentColIndex)) / 1000#
            voltageArray(rowCount) = CDbl(parts(voltageColIndex))
            On Error GoTo EH
            rowCount = rowCount + 1
        End If
    Next i
    
BlockComplete:
    file.Close
    
    If rowCount < 2 Then
        ' Not enough valid data points
        result.rowCount = rowCount
        result.isValid = False
        IV_ExtractBlockFromFile = True
        Exit Function
    End If
    
    ' Resize arrays to actual count
    ReDim Preserve currentArray(0 To rowCount - 1)
    ReDim Preserve voltageArray(0 To rowCount - 1)
    
    result.rowCount = rowCount
    
    ' Perform linear regression
    If Not IV_LinearRegression(currentArray, voltageArray, result.resistance_Ohm, result.offset_V, result.fitQuality_R2) Then
        result.isValid = False
        IV_ExtractBlockFromFile = True
        Exit Function
    End If
    
    result.isValid = True
    IV_ExtractBlockFromFile = True
    Exit Function
    
EarlyEOF:
    file.Close
    MV_SetError "Unexpected end of file while reading IV block " & CStr(blockIndex)
    IV_ExtractBlockFromFile = False
    Exit Function
    
EH:
    On Error Resume Next
    If Not file Is Nothing Then file.Close
    MV_SetError "IV_ExtractBlockFromFile error: " & Err.Description
    IV_ExtractBlockFromFile = False
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

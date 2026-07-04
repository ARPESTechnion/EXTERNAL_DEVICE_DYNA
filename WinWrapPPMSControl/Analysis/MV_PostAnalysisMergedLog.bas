'#Uses "..\..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses ".\MV_IV_PostAnalysis.bas"

Option Explicit

Private MV_MergedDataFile As Object
Private MV_MergedLogPath As String

Private Const COL_TEMP_K As String = "Temperature (K)"
Private Const COL_FIELD_OE As String = "Field (Oe)"
Private Const COL_HELM_FIELD_OE As String = "Helmholtz Field (Oe)"
Private Const COL_TOTAL_CURRENT_A As String = "Helmholtz Current Total (A)"
Private Const COL_CURRENT_A_A As String = "Applied Current ChA (A)"
Private Const COL_CURRENT_B_A As String = "Applied Current ChB (A)"
Private Const COL_HELM_COMPLIANCE_V As String = "Helmholtz Compliance (V)"
Private Const COL_HELM_NPLC As String = "Helmholtz NPLC"
Private Const COL_RES_A_OHM As String = "Resistance ChA (Ohms)"
Private Const COL_RES_B_OHM As String = "Resistance ChB (Ohms)"
Private Const COL_HALL_CURRENT_mA As String = "Hall Current (mA)"
Private Const COL_HALL_COMPLIANCE_V As String = "Hall Compliance (V)"
Private Const COL_HALL_NPLC As String = "Hall NPLC"
Private Const COL_HALL_VOLTAGE_V As String = "Hall Voltage (V)"
Private Const COL_HALL_FIELD_OE As String = "Hall Field (Oe)"

Private Const COL_CH1_R_OHM As String = "Ch1 Resistance Ohm"
Private Const COL_CH1_OFFSET_V As String = "Ch1 Offset V"
Private Const COL_CH1_R2 As String = "Ch1 Fit R2"
Private Const COL_CH1_ROWCOUNT As String = "Ch1 RowCount"
Private Const COL_CH1_VALID As String = "Ch1 Valid"
Private Const COL_CH1_AVG_S As String = "Ch1 AveragingTime s"
Private Const COL_CH1_GAIN As String = "Ch1 Gain"

Private Const COL_CH2_R_OHM As String = "Ch2 Resistance Ohm"
Private Const COL_CH2_OFFSET_V As String = "Ch2 Offset V"
Private Const COL_CH2_R2 As String = "Ch2 Fit R2"
Private Const COL_CH2_ROWCOUNT As String = "Ch2 RowCount"
Private Const COL_CH2_VALID As String = "Ch2 Valid"
Private Const COL_CH2_AVG_S As String = "Ch2 AveragingTime s"
Private Const COL_CH2_GAIN As String = "Ch2 Gain"

Private Const COL_FIELD_CORRECTED_OE As String = "Field Corrected Oe"
Private Const COL_BG_ZERO_PRE_OE As String = "Bg Zero Pre Oe"
Private Const COL_BG_ZERO_POST_OE As String = "Bg Zero Post Oe"
Private Const COL_BG_FIT_R2 As String = "Bg Fit R2"
Private Const COL_BG_FIT_RMS As String = "Bg Fit RMS"
Private Const COL_BG_SOURCE_CODE As String = "Bg Correction Source Code"

Private Sub Merged_SetLongOrBlank(ByRef rowData() As Variant, ByVal idxLabel As Integer, ByVal idxValue As Integer, ByVal colName As String, ByVal value As Long, ByVal isPresent As Boolean)
    rowData(idxLabel) = colName
    If isPresent Then
        rowData(idxValue) = value
    Else
        rowData(idxValue) = ""
    End If
End Sub

Private Sub Merged_SetBoolAsIntOrBlank(ByRef rowData() As Variant, ByVal idxLabel As Integer, ByVal idxValue As Integer, ByVal colName As String, ByVal value As Boolean, ByVal isPresent As Boolean)
    rowData(idxLabel) = colName
    If isPresent Then
        If value Then
            rowData(idxValue) = 1
        Else
            rowData(idxValue) = 0
        End If
    Else
        rowData(idxValue) = ""
    End If
End Sub

Public Function Merged_InitPostAnalysisLog(ByVal filePath As String) As Boolean
    On Error GoTo EH

    Call IV_ResetParserCache()

    MV_MergedLogPath = filePath
    If Not MV_EndsWithIgnoreCase(MV_MergedLogPath, ".dat") Then
        MV_MergedLogPath = MV_MergedLogPath & ".dat"
    End If

    Set MV_MergedDataFile = New MultiVuDataFile

    MV_MergedDataFile.AddColumn COL_TEMP_K
    MV_MergedDataFile.AddColumn COL_FIELD_OE
    MV_MergedDataFile.AddColumn COL_HELM_FIELD_OE
    MV_MergedDataFile.AddColumn COL_TOTAL_CURRENT_A
    MV_MergedDataFile.AddColumn COL_CURRENT_A_A
    MV_MergedDataFile.AddColumn COL_CURRENT_B_A
    MV_MergedDataFile.AddColumn COL_HELM_COMPLIANCE_V
    MV_MergedDataFile.AddColumn COL_HELM_NPLC
    MV_MergedDataFile.AddColumn COL_RES_A_OHM
    MV_MergedDataFile.AddColumn COL_RES_B_OHM
    MV_MergedDataFile.AddColumn COL_HALL_CURRENT_mA
    MV_MergedDataFile.AddColumn COL_HALL_COMPLIANCE_V
    MV_MergedDataFile.AddColumn COL_HALL_NPLC
    MV_MergedDataFile.AddColumn COL_HALL_VOLTAGE_V
    MV_MergedDataFile.AddColumn COL_HALL_FIELD_OE

    MV_MergedDataFile.AddColumn COL_CH1_R_OHM, mvStartupAxisY1
    MV_MergedDataFile.AddColumn COL_CH1_OFFSET_V
    MV_MergedDataFile.AddColumn COL_CH1_R2, mvStartupAxisY3
    MV_MergedDataFile.AddColumn COL_CH1_ROWCOUNT
    MV_MergedDataFile.AddColumn COL_CH1_VALID
    MV_MergedDataFile.AddColumn COL_CH1_AVG_S
    MV_MergedDataFile.AddColumn COL_CH1_GAIN

    MV_MergedDataFile.AddColumn COL_CH2_R_OHM, mvStartupAxisY2
    MV_MergedDataFile.AddColumn COL_CH2_OFFSET_V
    MV_MergedDataFile.AddColumn COL_CH2_R2, mvStartupAxisY3
    MV_MergedDataFile.AddColumn COL_CH2_ROWCOUNT
    MV_MergedDataFile.AddColumn COL_CH2_VALID
    MV_MergedDataFile.AddColumn COL_CH2_AVG_S
    MV_MergedDataFile.AddColumn COL_CH2_GAIN

    MV_MergedDataFile.AddColumn COL_FIELD_CORRECTED_OE
    MV_MergedDataFile.AddColumn COL_BG_ZERO_PRE_OE
    MV_MergedDataFile.AddColumn COL_BG_ZERO_POST_OE
    MV_MergedDataFile.AddColumn COL_BG_FIT_R2
    MV_MergedDataFile.AddColumn COL_BG_FIT_RMS
    MV_MergedDataFile.AddColumn COL_BG_SOURCE_CODE

    MV_MergedDataFile.CreateFileAndWriteHeader MV_MergedLogPath, "Post-analysis merged log", "; Post-analysis merged log"

    Merged_InitPostAnalysisLog = True
    Exit Function
EH:
    MV_SetError "Init merged post-analysis log failed: " & Err.Description
    Merged_InitPostAnalysisLog = False
End Function

Public Function Merged_ClosePostAnalysisLog() As Boolean
    On Error Resume Next
    Call IV_ResetParserCache()
    Set MV_MergedDataFile = Nothing
    Merged_ClosePostAnalysisLog = True
End Function

Public Function PostAnalysis_AppendMergedRow(ByVal etoDataPath As String, _
                                             ByVal stepIndex As Long, _
                                             ByVal hallMeasuredThisStep As Boolean, _
                                             ByVal measureCh1 As Boolean, _
                                             ByVal measureCh2 As Boolean, _
                                             ByVal channelsShareBlock As Boolean, _
                                             ByVal dualBlockOrderCh1First As Boolean, _
                                             ByVal ch1CurrentColIndex As Long, _
                                             ByVal ch1VoltageColIndex As Long, _
                                             ByVal ch1AveragingTimeColIndex As Long, _
                                             ByVal ch1GainColIndex As Long, _
                                             ByVal ch2CurrentColIndex As Long, _
                                             ByVal ch2VoltageColIndex As Long, _
                                             ByVal ch2AveragingTimeColIndex As Long, _
                                             ByVal ch2GainColIndex As Long, _
                                             Optional ByVal overrideTemp_K As Double = -9.9E99, _
                                             Optional ByVal overrideField_Oe As Double = -9.9E99, _
                                             Optional ByVal hallVoltage_V As Double = -9.9E99, _
                                             Optional ByVal hallField_Oe As Double = -9.9E99, _
                                             Optional ByVal correctedField_Oe As Double = -9.9E99, _
                                             Optional ByVal bgZeroPre_Oe As Double = -9.9E99, _
                                             Optional ByVal bgZeroPost_Oe As Double = -9.9E99, _
                                             Optional ByVal bgFitR2 As Double = -9.9E99, _
                                             Optional ByVal bgFitRMS As Double = -9.9E99, _
                                             Optional ByVal bgSourceCode As Long = -999999) As Boolean
    On Error GoTo EH

    Dim blockCh1 As Long
    Dim blockCh2 As Long
    Dim useDualBlock As Boolean

    Dim resultCh1 As IV_BlockResult
    Dim resultCh2 As IV_BlockResult

    Dim ch1Avg_s As Double
    Dim ch1Gain As Double
    Dim ch2Avg_s As Double
    Dim ch2Gain As Double
    Dim ch1HasAvg As Boolean
    Dim ch1HasGain As Boolean
    Dim ch2HasAvg As Boolean
    Dim ch2HasGain As Boolean

    Dim okCh1 As Boolean
    Dim okCh2 As Boolean

    Dim tRel As Double
    Dim tempK As Double
    Dim fieldOe As Double
    Dim helmField_Oe As Double
    Dim rowData(1 To 72) As Variant

    If MV_MergedDataFile Is Nothing Then
        MV_SetError "Merged post-analysis log writer not initialized"
        PostAnalysis_AppendMergedRow = False
        Exit Function
    End If

    If (Not measureCh1) And (Not measureCh2) Then
        MV_SetError "PostAnalysis append requires at least one measured channel"
        PostAnalysis_AppendMergedRow = False
        Exit Function
    End If

    useDualBlock = (measureCh1 And measureCh2 And (Not channelsShareBlock))

    If measureCh1 And measureCh2 And channelsShareBlock Then
        blockCh1 = stepIndex
        blockCh2 = stepIndex
    ElseIf useDualBlock Then
        If dualBlockOrderCh1First Then
            blockCh1 = 2 * stepIndex
            blockCh2 = blockCh1 + 1
        Else
            blockCh2 = 2 * stepIndex
            blockCh1 = blockCh2 + 1
        End If
    Else
        blockCh1 = stepIndex
        blockCh2 = stepIndex
    End If

    okCh1 = False
    okCh2 = False

    If measureCh1 And measureCh2 Then
        okCh1 = IV_ExtractTwoBlocksWithMetadataFromFile(etoDataPath, _
                                                        blockCh1, _
                                                        blockCh2, _
                                                        ch1CurrentColIndex, _
                                                        ch1VoltageColIndex, _
                                                        ch1AveragingTimeColIndex, _
                                                        ch1GainColIndex, _
                                                        ch2CurrentColIndex, _
                                                        ch2VoltageColIndex, _
                                                        ch2AveragingTimeColIndex, _
                                                        ch2GainColIndex, _
                                                        resultCh1, _
                                                        ch1Avg_s, _
                                                        ch1Gain, _
                                                        ch1HasAvg, _
                                                        ch1HasGain, _
                                                        resultCh2, _
                                                        ch2Avg_s, _
                                                        ch2Gain, _
                                                        ch2HasAvg, _
                                                        ch2HasGain)
        okCh2 = okCh1
        If Not okCh1 Then
            PostAnalysis_AppendMergedRow = False
            Exit Function
        End If
    ElseIf measureCh1 Then
        okCh1 = IV_ExtractBlockWithMetadataFromFile(etoDataPath, _
                                                    blockCh1, _
                                                    ch1CurrentColIndex, _
                                                    ch1VoltageColIndex, _
                                                    ch1AveragingTimeColIndex, _
                                                    ch1GainColIndex, _
                                                    resultCh1, _
                                                    ch1Avg_s, _
                                                    ch1Gain, _
                                                    ch1HasAvg, _
                                                    ch1HasGain)
        If Not okCh1 Then
            PostAnalysis_AppendMergedRow = False
            Exit Function
        End If
    End If

    If measureCh2 Then
        okCh2 = IV_ExtractBlockWithMetadataFromFile(etoDataPath, _
                                                    blockCh2, _
                                                    ch2CurrentColIndex, _
                                                    ch2VoltageColIndex, _
                                                    ch2AveragingTimeColIndex, _
                                                    ch2GainColIndex, _
                                                    resultCh2, _
                                                    ch2Avg_s, _
                                                    ch2Gain, _
                                                    ch2HasAvg, _
                                                    ch2HasGain)
        If Not okCh2 Then
            PostAnalysis_AppendMergedRow = False
            Exit Function
        End If
    End If

    tRel = MV_GetSessionElapsedSeconds()
    If MV_IsFinite(overrideTemp_K) Then
        tempK = overrideTemp_K
    Else
        tempK = DYNA_GetTemperature_K()
    End If

    If MV_IsFinite(overrideField_Oe) Then
        fieldOe = overrideField_Oe
    Else
        fieldOe = DYNA_GetField_Oe()
    End If
    helmField_Oe = (MV_LastCurrentA_A + MV_LastCurrentB_A) * MV_HELM_G_PER_A_TOTAL

    If Not hallMeasuredThisStep Then
        hallVoltage_V = -9.9E99
        hallField_Oe = -9.9E99
    End If

    rowData(1) = MV_MergedDataFile.GetTimeCol()
    rowData(2) = tRel

    rowData(3) = COL_TEMP_K
    rowData(4) = tempK
    rowData(5) = COL_FIELD_OE
    rowData(6) = fieldOe
    rowData(7) = COL_HELM_FIELD_OE
    rowData(8) = helmField_Oe
    rowData(9) = COL_TOTAL_CURRENT_A
    rowData(10) = MV_LastCurrentA_A + MV_LastCurrentB_A
    rowData(11) = COL_CURRENT_A_A
    rowData(12) = MV_LastCurrentA_A
    rowData(13) = COL_CURRENT_B_A
    rowData(14) = MV_LastCurrentB_A
    rowData(15) = COL_HELM_COMPLIANCE_V
    rowData(16) = MV_HelmCompliance_V
    rowData(17) = COL_HELM_NPLC
    rowData(18) = MV_HelmNPLC
    rowData(19) = COL_RES_A_OHM
    rowData(20) = ""
    rowData(21) = COL_RES_B_OHM
    rowData(22) = ""
    rowData(23) = COL_HALL_CURRENT_mA
    rowData(24) = MV_HallCurrent_mA
    rowData(25) = COL_HALL_COMPLIANCE_V
    rowData(26) = MV_HallCompliance_V
    rowData(27) = COL_HALL_NPLC
    rowData(28) = MV_HallNPLC
    Call MV_SetNumericOrBlank(rowData, 29, 30, COL_HALL_VOLTAGE_V, hallVoltage_V)
    Call MV_SetNumericOrBlank(rowData, 31, 32, COL_HALL_FIELD_OE, hallField_Oe)

    If measureCh1 Then
        Call MV_SetNumericOrBlank(rowData, 33, 34, COL_CH1_R_OHM, resultCh1.resistance_Ohm)
        Call MV_SetNumericOrBlank(rowData, 35, 36, COL_CH1_OFFSET_V, resultCh1.offset_V)
        Call MV_SetNumericOrBlank(rowData, 37, 38, COL_CH1_R2, resultCh1.fitQuality_R2)
        Call Merged_SetLongOrBlank(rowData, 39, 40, COL_CH1_ROWCOUNT, resultCh1.rowCount, True)
        Call Merged_SetBoolAsIntOrBlank(rowData, 41, 42, COL_CH1_VALID, resultCh1.isValid, True)
        If ch1HasAvg Then
            Call MV_SetNumericOrBlank(rowData, 43, 44, COL_CH1_AVG_S, ch1Avg_s)
        Else
            rowData(43) = COL_CH1_AVG_S
            rowData(44) = ""
        End If
        If ch1HasGain Then
            Call MV_SetNumericOrBlank(rowData, 45, 46, COL_CH1_GAIN, ch1Gain)
        Else
            rowData(45) = COL_CH1_GAIN
            rowData(46) = ""
        End If
    Else
        rowData(33) = COL_CH1_R_OHM: rowData(34) = ""
        rowData(35) = COL_CH1_OFFSET_V: rowData(36) = ""
        rowData(37) = COL_CH1_R2: rowData(38) = ""
        rowData(39) = COL_CH1_ROWCOUNT: rowData(40) = ""
        rowData(41) = COL_CH1_VALID: rowData(42) = ""
        rowData(43) = COL_CH1_AVG_S: rowData(44) = ""
        rowData(45) = COL_CH1_GAIN: rowData(46) = ""
    End If

    If measureCh2 Then
        Call MV_SetNumericOrBlank(rowData, 47, 48, COL_CH2_R_OHM, resultCh2.resistance_Ohm)
        Call MV_SetNumericOrBlank(rowData, 49, 50, COL_CH2_OFFSET_V, resultCh2.offset_V)
        Call MV_SetNumericOrBlank(rowData, 51, 52, COL_CH2_R2, resultCh2.fitQuality_R2)
        Call Merged_SetLongOrBlank(rowData, 53, 54, COL_CH2_ROWCOUNT, resultCh2.rowCount, True)
        Call Merged_SetBoolAsIntOrBlank(rowData, 55, 56, COL_CH2_VALID, resultCh2.isValid, True)
        If ch2HasAvg Then
            Call MV_SetNumericOrBlank(rowData, 57, 58, COL_CH2_AVG_S, ch2Avg_s)
        Else
            rowData(57) = COL_CH2_AVG_S
            rowData(58) = ""
        End If
        If ch2HasGain Then
            Call MV_SetNumericOrBlank(rowData, 59, 60, COL_CH2_GAIN, ch2Gain)
        Else
            rowData(59) = COL_CH2_GAIN
            rowData(60) = ""
        End If
    Else
        rowData(47) = COL_CH2_R_OHM: rowData(48) = ""
        rowData(49) = COL_CH2_OFFSET_V: rowData(50) = ""
        rowData(51) = COL_CH2_R2: rowData(52) = ""
        rowData(53) = COL_CH2_ROWCOUNT: rowData(54) = ""
        rowData(55) = COL_CH2_VALID: rowData(56) = ""
        rowData(57) = COL_CH2_AVG_S: rowData(58) = ""
        rowData(59) = COL_CH2_GAIN: rowData(60) = ""
    End If

    Call MV_SetNumericOrBlank(rowData, 61, 62, COL_FIELD_CORRECTED_OE, correctedField_Oe)
    Call MV_SetNumericOrBlank(rowData, 63, 64, COL_BG_ZERO_PRE_OE, bgZeroPre_Oe)
    Call MV_SetNumericOrBlank(rowData, 65, 66, COL_BG_ZERO_POST_OE, bgZeroPost_Oe)
    Call MV_SetNumericOrBlank(rowData, 67, 68, COL_BG_FIT_R2, bgFitR2)
    Call MV_SetNumericOrBlank(rowData, 69, 70, COL_BG_FIT_RMS, bgFitRMS)
    rowData(71) = COL_BG_SOURCE_CODE
    If bgSourceCode = -999999 Then
        rowData(72) = ""
    Else
        rowData(72) = bgSourceCode
    End If

    Call MV_MergedDataFile.WriteDataUsingArray(rowData, False)

    PostAnalysis_AppendMergedRow = True
    Exit Function
EH:
    MV_SetError "PostAnalysis_AppendMergedRow failed: " & Err.Description
    PostAnalysis_AppendMergedRow = False
End Function

'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"

Option Explicit

Private Const HOFF_BAD_VALUE As Double = -9.9E99

Public Sub Macro_Run_Hall_Offset_ETO()
    Dim Use_Average As Boolean
    Dim Average_Count As Long
    Dim Measure_Channel As Long

    Dim Temp_K As Double
    Dim Field_Oe As Double
    Dim Field_Rate_Oe_s As Double
    Dim Wait_Stable_s As Long

    Dim IV_Current_mA As Double
    Dim IV_Frequency_Hz As Double
    Dim IV_Averaging As Long
    Dim IV_Gain_Code As String
    Dim IV_Sweep_Code As String

    Dim BaseFolder As String
    Dim OutputPrefix As String

    Dim etodfPath As String
    Dim etoParams As String
    Dim i As Long
    Dim n As Long
    Dim chIndex As Long
    Dim currCol As Long
    Dim voltCol As Long
    Dim avgCol As Long
    Dim gainCol As Long
    Dim validCount As Long

    Dim block As IV_BlockResult
    Dim avg_s As Double
    Dim gainValue As Double
    Dim hasAvg As Boolean
    Dim hasGain As Boolean

    Dim offsetV As Double
    Dim meanOffset As Double
    Dim m2 As Double
    Dim delta As Double
    Dim stdOffset As Double

    ' --------------- User configuration -----------------
    Use_Average = True
    Average_Count = 10
    Measure_Channel = 0  ' 0 = Ch1, 1 = Ch2

    Temp_K = 300
    Field_Oe = 0#
    Field_Rate_Oe_s = 10#
    Wait_Stable_s = 10

    IV_Current_mA = 2
    IV_Frequency_Hz = 0.3051758
    IV_Averaging = 10
    IV_Gain_Code = "3 2 1"
    IV_Sweep_Code = "0 0 0"

    BaseFolder = "C:\QdDynacool\Data\ETO\"
    OutputPrefix = "HallOffsetETO"
    ' ----------------------------------------------------

    If Measure_Channel <> 0 And Measure_Channel <> 1 Then
        MV_SetError "Measure_Channel must be 0 or 1"
        Exit Sub
    End If

    If Use_Average Then
        n = Average_Count
        If n < 1 Then n = 1
    Else
        n = 1
    End If

    chIndex = Measure_Channel
    If chIndex = 0 Then
        currCol = 9
        voltCol = 10
        avgCol = 12
        gainCol = 23
    Else
        currCol = 29
        voltCol = 30
        avgCol = 32
        gainCol = 43
    End If

    etoParams = DoubleToCommandText(IV_Current_mA) & " " & _
                DoubleToCommandText(IV_Frequency_Hz) & " 0 " & _
                CStr(IV_Averaging) & " 0 " & _
                IV_Gain_Code & " " & IV_Sweep_Code

    etodfPath = BaseFolder & OutputPrefix & "_" & Format$(Now, "yyyymmdd_hhnnss") & ".dat"

    Debug.Clear
    MV_ClearError

    MV_Log "[MACRO][HALL-OFFSET-ETO] Starting"
    MV_Log "[MACRO][HALL-OFFSET-ETO] Output file: " & etodfPath

    DynaCool.SetTemperature (Temp_K, 10, 0) 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0001 Set Temp
    DynaCool.WaitFor(1, Wait_Stable_s, 0) 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0002 Wait For %t stable

    DynaCool.SetField (Field_Oe, Field_Rate_Oe_s, 0, 0) 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0003 Set Field
    DynaCool.WaitFor(2, Wait_Stable_s, 0) 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0004 Wait For %t stable

    DynaCool.SequenceMeasure ("ETODF '" & etodfPath & "' 0 Untitled") 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0005 ETODF

    meanOffset = 0#
    m2 = 0#
    validCount = 0

    For i = 1 To n
        DynaCool.SequenceMeasure ("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 " & CStr(chIndex) & " " & etoParams) 'mvseq:Macro_Hall_Offset_ETO.seq(1)>0006 ETOIV

        If Not TryExtractOffsetWithRetry(etodfPath, i - 1, currCol, voltCol, avgCol, gainCol, block, offsetV) Then
            MV_Log "[MACRO][HALL-OFFSET-ETO][WARN] Failed to parse block " & CStr(i - 1)
            GoTo NextSample
        End If

        validCount = validCount + 1
        delta = offsetV - meanOffset
        meanOffset = meanOffset + (delta / CDbl(validCount))
        m2 = m2 + delta * (offsetV - meanOffset)

NextSample:
    Next i

    If validCount < 1 Then
        MV_SetError "No valid Hall offset samples extracted"
        MV_Log "[MACRO][HALL-OFFSET-ETO][FAIL] " & MV_LastError
        Exit Sub
    End If

    If validCount > 1 Then
        stdOffset = Sqr(m2 / CDbl(validCount - 1))
    Else
        stdOffset = 0#
    End If

    MV_Log "[MACRO][HALL-OFFSET-ETO] Recommended Hall offset V = " & CStr(meanOffset)
    MV_Log "[MACRO][HALL-OFFSET-ETO] Std V = " & CStr(stdOffset)
    MV_Log "[MACRO][HALL-OFFSET-ETO] Valid samples = " & CStr(validCount) & " / " & CStr(n)
    MV_Log "[MACRO][HALL-OFFSET-ETO] Set this in HallOffset_V of Macro_Run_PPMS_BSweep_HelmIP"
End Sub

Private Function TryExtractOffsetWithRetry(ByVal dataPath As String, _
                                           ByVal blockIndex As Long, _
                                           ByVal currCol As Long, _
                                           ByVal voltCol As Long, _
                                           ByVal avgCol As Long, _
                                           ByVal gainCol As Long, _
                                           ByRef outBlock As IV_BlockResult, _
                                           ByRef outOffsetV As Double) As Boolean
    Dim i As Long
    Dim avg_s As Double
    Dim gainValue As Double
    Dim hasAvg As Boolean
    Dim hasGain As Boolean

    outOffsetV = HOFF_BAD_VALUE

    For i = 1 To 25
        If IV_ExtractBlockWithMetadataFromFile(dataPath, _
                                               blockIndex, _
                                               currCol, _
                                               voltCol, _
                                               avgCol, _
                                               gainCol, _
                                               outBlock, _
                                               avg_s, _
                                               gainValue, _
                                               hasAvg, _
                                               hasGain) Then
            If outBlock.isValid Then
                outOffsetV = outBlock.offset_V
                TryExtractOffsetWithRetry = True
                Exit Function
            End If
        End If

        MV_WaitSeconds 0.2
        DoEvents
    Next i

    TryExtractOffsetWithRetry = False
End Function

Private Function DoubleToCommandText(ByVal Value As Double) As String
    Dim s As String

    s = Trim$(CStr(Value))
    s = Replace$(s, ",", ".")
    DoubleToCommandText = s
End Function

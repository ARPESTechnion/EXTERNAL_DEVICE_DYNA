'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"
'#Uses "..\MV_RunWrappers.bas"
'#Uses "..\..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"

Option Explicit

Private Const IV_CH1_CURR_COL As Long = 9
Private Const IV_CH1_VOLT_COL As Long = 10
Private Const IV_CH1_AVG_COL As Long = 12
Private Const IV_CH1_GAIN_COL As Long = 23

Private Const IV_CH2_CURR_COL As Long = 29
Private Const IV_CH2_VOLT_COL As Long = 30
Private Const IV_CH2_AVG_COL As Long = 32
Private Const IV_CH2_GAIN_COL As Long = 43

Private Const BAD_VALUE As Double = -9.9E99

Public Sub fn_PPMS_BSweep_Helm_IP( _
    ByVal OOP_Field_Start As Double, _
    ByVal OOP_Field_End As Double, _
    ByVal OOP_Field_Step As Double, _
    ByVal OOP_Field_Rate As Double, _
    ByVal IP_Helm_Start As Double, _
    ByVal IP_Helm_End As Double, _
    ByVal IP_Helm_Step As Double, _
    ByVal IP_Helm_Rate As Double, _
    ByVal IV_Current_mA As Double, _
    ByVal IV_Frequency_Hz As Double, _
    ByVal IV_Averaging As Long, _
    ByVal IV_Gain_Code As String, _
    ByVal IV_Sweep_Code As String, _
    ByVal Wait_For_Stable_s As Long, _
    ByVal IP_Field_Stable_Wait_s As Long, _
    ByVal Measure_Ch1_Hall As Boolean, _
    ByVal Temp_Start As Double, _
    ByVal Temp_End As Double, _
    ByVal Temp_Step As Double, _
    ByVal Enable_Background_Pre As Boolean, _
    ByVal Enable_Background_Post As Boolean, _
    ByVal Bg_Temperature_K As Double, _
    ByVal Bg_Field_Start As Double, _
    ByVal Bg_Field_End As Double, _
    ByVal Bg_Field_Step As Double, _
    ByVal Bg_Field_Rate As Double, _
    ByVal Bg_MinPointsForFit As Long, _
    ByVal K2600_resourceName As String, _
    ByVal BaseFolder As String)

    Dim ETO_DataFile As String
    Dim Helmholtz_LogFile As String
    Dim Merged_LogFile As String
    Dim Bg_DataFile As String
    Dim BaseName As String
    Dim RunSuffix As String
    Dim SweepSuffix As String
    Dim ETOIV_Params As String

    Dim N_Temps As Long
    Dim N_IP As Long
    Dim N_OOP As Long
    Dim IT As Long
    Dim IIP As Long
    Dim IOOP As Long

    Dim Temp_Step_Actual As Double
    Dim IP_Step_Actual As Double
    Dim OOP_Step_Actual As Double

    Dim Measurement_Temperature As Double
    Dim InPlane_Helm_Oe As Double
    Dim OOP_Field_Target As Double
    Dim fieldZero_Oe As Double
    Dim sourceCode As Long
    Dim fitR2 As Double
    Dim fitRms As Double
    Dim bgPreForRow As Double
    Dim bgPostForRow As Double
    Dim tStepStart As Double
    Dim tAfterETO As Double
    Dim tAfterWait As Double
    Dim waitMs As Double
    Dim appendMs As Double
    Dim totalMs As Double

    Dim appendOk As Boolean
    Dim preOk As Boolean
    Dim postOk As Boolean
    Dim preWasReused As Boolean
    Dim skipHelmSetWait As Boolean
    Dim currentHelmField_Oe As Double
    Dim preZero_Oe As Double
    Dim postZero_Oe As Double
    Dim preR2 As Double
    Dim preRms As Double
    Dim postR2 As Double
    Dim postRms As Double

    Dim prevPostZeroByIP() As Double
    Dim prevPostValidByIP() As Boolean

    ' Resolve loop counts and signed steps for Temp/IP/OOP scans.
    If Not BuildLoop(Temp_Start, Temp_End, Temp_Step, Temp_Step_Actual, N_Temps) Then Exit Sub
    If Not BuildLoop(IP_Helm_Start, IP_Helm_End, IP_Helm_Step, IP_Step_Actual, N_IP) Then Exit Sub
    If Not BuildLoop(OOP_Field_Start, OOP_Field_End, OOP_Field_Step, OOP_Step_Actual, N_OOP) Then Exit Sub

    If Bg_MinPointsForFit < 5 Then Bg_MinPointsForFit = 5

    ReDim prevPostZeroByIP(1 To N_IP)
    ReDim prevPostValidByIP(1 To N_IP)

    SweepSuffix = NumericTokenNoRound(OOP_Field_Start) & "_" & _
                  NumericTokenNoRound(Abs(OOP_Field_Step)) & "_" & _
                  NumericTokenNoRound(OOP_Field_End) & "G"
    BaseName = "BSweep_" & SweepSuffix

    ETOIV_Params = DoubleToCommandText(IV_Current_mA) & " " & _
                   DoubleToCommandText(IV_Frequency_Hz) & " 0 " & _
                   CStr(IV_Averaging) & " 0 " & _
                   IV_Gain_Code & " " & IV_Sweep_Code

    If IP_Field_Stable_Wait_s < 0 Then IP_Field_Stable_Wait_s = 0

    For IIP = 1 To N_IP
    For IT = 1 To N_Temps

        ' ------- Build run identity and per-run output file paths -------

        Measurement_Temperature = Temp_Start + CDbl(IT - 1) * Temp_Step_Actual
        InPlane_Helm_Oe = IP_Helm_Start + CDbl(IIP - 1) * IP_Step_Actual

        RunSuffix = "_T_" & NumericTokenNoRound(Measurement_Temperature) & "K" & _
                    "_IP_" & NumericTokenNoRound(InPlane_Helm_Oe) & "G"

        ETO_DataFile = BaseFolder & BaseName & RunSuffix & ".dat"
        Helmholtz_LogFile = BaseFolder & BaseName & RunSuffix & "_HelmholtzLog.dat"
        Merged_LogFile = BaseFolder & BaseName & RunSuffix & "_Analyzed.dat"

        If Not MV_InitSessionWithPostAnalysis("BSweep_" & RunSuffix, Helmholtz_LogFile, Merged_LogFile) Then
            MV_Log "[SEQ][ERROR] Session init failed for " & RunSuffix
            GoTo NextRun
        End If

        If Not K2600_Connect(K2600_resourceName) Then GoTo RunFail
        If Not Helm_ConfigSource(3, 1) Then GoTo RunFail

        ' ------- Bring instruments to known baseline before main sweep -------
        DynaCool.SetTemperature(2.8, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0001 Set T>2.8 K
        DynaCool.WaitFor(1, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0002 Wait For %t stable

        skipHelmSetWait = False
        If Abs(InPlane_Helm_Oe) < 1 Then
            currentHelmField_Oe = Helm_GetField_Oe()
            If currentHelmField_Oe > BAD_VALUE / 2# Then
                skipHelmSetWait = (Abs(currentHelmField_Oe) < 2#)
            End If
        End If

        If Not skipHelmSetWait Then
            If Not Helm_SetField(InPlane_Helm_Oe, IP_Helm_Rate) Then GoTo RunFail 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0003 Set Helm IP
            If Not Helm_WaitStable(10000, CDbl(IP_Field_Stable_Wait_s)) Then GoTo RunFail 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0004 Wait For Helm %t stable
        Else
            MV_Log "[SEQ][INFO] Skipping Helm set/wait because IP target is zero and current field is already near zero"
        End If

        preOk = False
        preWasReused = False
        preZero_Oe = BAD_VALUE
        preR2 = BAD_VALUE
        preRms = BAD_VALUE

        ' PRE source priority:
        ' 1) reuse previous temperature POST at same IP, 2) fresh PRE background sweep.
        If IT > 1 And prevPostValidByIP(IIP) Then
            preOk = True
            preWasReused = True
            preZero_Oe = prevPostZeroByIP(IIP)
            MV_Log "[BG][REUSE] Using POST of previous temperature as PRE for current step. B0=" & CStr(preZero_Oe)
        ElseIf Enable_Background_Pre Then
            Bg_DataFile = BaseFolder & BaseName & RunSuffix & "_BG_PRE.dat"
            preOk = RunBackgroundSweepAndFit( _
                        ETOIV_Params, _
                        Bg_DataFile, _
                        Wait_For_Stable_s, _
                        Bg_Temperature_K, _
                        Bg_Field_Start, _
                        Bg_Field_End, _
                        Bg_Field_Step, _
                        Bg_Field_Rate, _
                        Bg_MinPointsForFit, _
                        preZero_Oe, _
                        preR2, _
                        preRms)
            If preOk Then
                MV_Log "[BG][PRE] B0=" & CStr(preZero_Oe) & " R2=" & CStr(preR2) & " RMS=" & CStr(preRms)
            Else
                MV_Log "[BG][WARN] PRE fit failed; proceeding without correction"
            End If
        End If

        DynaCool.SetTemperature(Measurement_Temperature, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0005 Re-confirm Temp
        DynaCool.SetField(OOP_Field_Start, OOP_Field_Rate, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0006 Set OOP start field
        DynaCool.WaitFor(3, Wait_For_Stable_s, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0007 Wait For %t stable

        ' ------- Main OOP sweep with live append for fit/plot updates -------
        DynaCool.SequenceMeasure("ETODF '" & ETO_DataFile & "' 0 Untitled") 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0008 ETODF open
        bgPreForRow = BAD_VALUE
        If preOk Then bgPreForRow = preZero_Oe
        bgPostForRow = BAD_VALUE
        fitR2 = BAD_VALUE
        fitRms = BAD_VALUE
        If preOk Then
            fitR2 = preR2
            fitRms = preRms
        End If

        For IOOP = 1 To N_OOP
            tStepStart = Timer
            OOP_Field_Target = OOP_Field_Start + CDbl(IOOP - 1) * OOP_Step_Actual

            DynaCool.SetField(OOP_Field_Target, OOP_Field_Rate, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0009 Set OOP field point
            DynaCool.WaitFor(2, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0010 Brief settle OOP

            Call Helm_MeasureAndLog() 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0011 Helm measure log

            If Measure_Ch1_Hall Then
                DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 0 " & ETOIV_Params) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0012 ETOIV Ch1
            End If
            DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 1 " & ETOIV_Params) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0013 ETOIV Ch2
            tAfterETO = Timer

            ' During the main sweep we apply PRE-only correction for live output.
            sourceCode = 0
            fieldZero_Oe = BAD_VALUE
            If preOk Then
                fieldZero_Oe = preZero_Oe
                sourceCode = 1
            End If

            DynaCool.WaitFor(0, 1, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0013 Flush ETO buffer (main live append)
            tAfterWait = Timer
            appendOk = AppendWithRetry(ETO_DataFile, _
                                       Measure_Ch1_Hall, _
                                       OOP_Field_Target, _
                                       fieldZero_Oe, _
                                       bgPreForRow, _
                                       bgPostForRow, _
                                       fitR2, _
                                       fitRms, _
                                       sourceCode)
            waitMs = TimerElapsedMs(tAfterETO, tAfterWait)
            appendMs = TimerElapsedMs(tAfterWait, Timer)
            totalMs = TimerElapsedMs(tStepStart, Timer)
            If Not appendOk Then
                MV_Log "[SEQ][WARN] Main live append failed at OOP step " & CStr(IOOP)
            End If
            MV_Log "[SEQ][TIMING] step=" & CStr(IOOP) & " wait_ms=" & Format(waitMs, "0") & " append_ms=" & Format(appendMs, "0") & " total_ms=" & Format(totalMs, "0") & " append_ok=" & CStr(IIf(appendOk, 1, 0))
        Next IOOP

        ' ------- Post-run settle and optional POST background measurement -------
        DynaCool.SetTemperature(2.8, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>00014 Set temp above TC after sweep
        DynaCool.SetField(0, 10, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0015 Zero OOP field after sweep
        DynaCool.WaitFor(3, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0016 Wait For %t stable

        postOk = False
        postZero_Oe = BAD_VALUE
        postR2 = BAD_VALUE
        postRms = BAD_VALUE

        If Enable_Background_Post Then
            Bg_DataFile = BaseFolder & BaseName & RunSuffix & "_BG_POST.dat"
            postOk = RunBackgroundSweepAndFit( _
                        ETOIV_Params, _
                        Bg_DataFile, _
                        Wait_For_Stable_s, _
                        Bg_Temperature_K, _
                        Bg_Field_Start, _
                        Bg_Field_End, _
                        Bg_Field_Step, _
                        Bg_Field_Rate, _
                        Bg_MinPointsForFit, _
                        postZero_Oe, _
                        postR2, _
                        postRms)
            If postOk Then
                prevPostValidByIP(IIP) = True
                prevPostZeroByIP(IIP) = postZero_Oe
                MV_Log "[BG][POST] B0=" & CStr(postZero_Oe) & " R2=" & CStr(postR2) & " RMS=" & CStr(postRms)
            Else
                prevPostValidByIP(IIP) = False
                MV_Log "[BG][WARN] POST fit failed; next PRE will not be reused"
            End If
        Else
            prevPostValidByIP(IIP) = False
        End If

        If preWasReused Then
            MV_Log "[BG][INFO] PRE correction source was reused from previous POST"
        End If

        DynaCool.WaitFor(2, 1, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0018 Wait For %t OOP settle before close

        ' Always close session at end of run to reset instrument state.
        ' Call MV_CloseSession()
        GoTo NextRun

RunFail:
        MV_Log "[SEQ][FAIL] " & MV_LastError
        ' Call MV_CloseSession()

NextRun:
    Next IT
    Next IIP
End Sub

' =========================================================
' Loop construction helper
' =========================================================

Private Function BuildLoop(ByVal startValue As Double, _
                           ByVal endValue As Double, _
                           ByVal stepInput As Double, _
                           ByRef actualStep As Double, _
                           ByRef count As Long) As Boolean

    If startValue = endValue Then
        actualStep = 0#
        count = 1
        BuildLoop = True
        Exit Function
    End If

    If stepInput = 0# Then
        MV_SetError "Loop step cannot be zero when start and end differ"
        BuildLoop = False
        Exit Function
    End If

    actualStep = Sgn(endValue - startValue) * Abs(stepInput)
    count = CLng(Fix((Abs(endValue - startValue) / Abs(stepInput)) + 0.5)) + 1
    BuildLoop = True
End Function

' =========================================================
' Live append helpers
' =========================================================

Private Function AppendSweepWithCorrections(ByVal etoDataPath As String, _
                                            ByVal measureCh1 As Boolean, _
                                            ByRef cmdFieldByStep() As Double, _
                                            ByVal stepCount As Long, _
                                            ByVal preOk As Boolean, _
                                            ByVal preZero_Oe As Double, _
                                            ByVal preR2 As Double, _
                                            ByVal preRms As Double, _
                                            ByVal postOk As Boolean, _
                                            ByVal postZero_Oe As Double, _
                                            ByVal postR2 As Double, _
                                            ByVal postRms As Double) As Boolean
    Dim i As Long
    Dim frac As Double
    Dim rawField_Oe As Double
    Dim correctedField_Oe As Double
    Dim offsetUsed_Oe As Double
    Dim sourceCode As Long
    Dim fitR2 As Double
    Dim fitRms As Double
    Dim bgPreForRow As Double
    Dim bgPostForRow As Double

    If stepCount < 1 Then
        AppendSweepWithCorrections = False
        Exit Function
    End If

    bgPreForRow = BAD_VALUE
    bgPostForRow = BAD_VALUE
    If preOk Then bgPreForRow = preZero_Oe
    If postOk Then bgPostForRow = postZero_Oe

    For i = 1 To stepCount
        rawField_Oe = cmdFieldByStep(i)
        sourceCode = 0
        fitR2 = BAD_VALUE
        fitRms = BAD_VALUE
        offsetUsed_Oe = 0#

        If preOk And postOk Then
            If stepCount > 1 Then
                frac = CDbl(i - 1) / CDbl(stepCount - 1)
            Else
                frac = 0#
            End If
            offsetUsed_Oe = preZero_Oe + frac * (postZero_Oe - preZero_Oe)
            sourceCode = 3
            fitR2 = MeanFinite(preR2, postR2)
            fitRms = MeanFinite(preRms, postRms)
        ElseIf preOk Then
            offsetUsed_Oe = preZero_Oe
            sourceCode = 1
            fitR2 = preR2
            fitRms = preRms
        ElseIf postOk Then
            offsetUsed_Oe = postZero_Oe
            sourceCode = 2
            fitR2 = postR2
            fitRms = postRms
        End If

        correctedField_Oe = rawField_Oe - offsetUsed_Oe

        If Not AppendWithRetry(etoDataPath, _
                               measureCh1, _
                               rawField_Oe, _
                               correctedField_Oe, _
                               bgPreForRow, _
                               bgPostForRow, _
                               fitR2, _
                               fitRms, _
                               sourceCode) Then
            AppendSweepWithCorrections = False
            Exit Function
        End If
    Next i

    AppendSweepWithCorrections = True
End Function

Private Function AppendWithRetry(ByVal etoDataPath As String, _
                                 ByVal measureCh1 As Boolean, _
                                 ByVal rawField_Oe As Double, _
                                 ByVal fieldZero_Oe As Double, _
                                 ByVal bgZeroPre_Oe As Double, _
                                 ByVal bgZeroPost_Oe As Double, _
                                 ByVal bgFitR2 As Double, _
                                 ByVal bgFitRms As Double, _
                                 ByVal bgSourceCode As Long) As Boolean
    Dim i As Long
    Dim extractedTemp_K As Double
    Dim recordedField_Oe As Double
    Dim correctedField_Oe As Double

    For i = 1 To 25
        recordedField_Oe = rawField_Oe
        If IV_ExtractBlockTempFieldFromFile(etoDataPath, MV_PostAnalysisStepIndex, extractedTemp_K, recordedField_Oe) Then
            If Not MV_IsFinite(recordedField_Oe) Then
                recordedField_Oe = rawField_Oe
            End If
        Else
            MV_WaitSeconds 0.2
            DoEvents
            GoTo NextRetry
        End If

        correctedField_Oe = recordedField_Oe
        If MV_IsFinite(fieldZero_Oe) Then
            correctedField_Oe = recordedField_Oe - fieldZero_Oe
        End If

        If PostAnalysis_AppendAfterETO(etoDataPath, _
                                       False, _
                                       measureCh1, _
                                       True, _
                                       False, _
                                       True, _
                                       IV_CH1_CURR_COL, _
                                       IV_CH1_VOLT_COL, _
                                       IV_CH1_AVG_COL, _
                                       IV_CH1_GAIN_COL, _
                                       IV_CH2_CURR_COL, _
                                       IV_CH2_VOLT_COL, _
                                       IV_CH2_AVG_COL, _
                                       IV_CH2_GAIN_COL, _
                                       BAD_VALUE, _
                                       recordedField_Oe, _
                                       BAD_VALUE, _
                                       BAD_VALUE, _
                                       correctedField_Oe, _
                                       bgZeroPre_Oe, _
                                       bgZeroPost_Oe, _
                                       bgFitR2, _
                                       bgFitRms, _
                                       bgSourceCode) Then
            AppendWithRetry = True
            Exit Function
        End If

NextRetry:
        MV_WaitSeconds 0.2
        DoEvents
    Next i

    AppendWithRetry = False
End Function

' =========================================================
' Background sweep and fit helpers
' =========================================================

Private Function RunBackgroundSweepAndFit(ByVal etoiVParams As String, _
                                          ByVal bgDataPath As String, _
                                          ByVal waitStable_s As Long, _
                                          ByVal bgTemp_K As Double, _
                                          ByVal bgFieldStart As Double, _
                                          ByVal bgFieldEnd As Double, _
                                          ByVal bgFieldStep As Double, _
                                          ByVal bgFieldRate As Double, _
                                          ByVal minPoints As Long, _
                                          ByRef outZero_Oe As Double, _
                                          ByRef outR2 As Double, _
                                          ByRef outRms As Double) As Boolean

    Dim bgStepActual As Double
    Dim nBg As Long
    Dim i As Long
    Dim blockIndex As Long
    Dim commandField As Double
    Dim parsedField As Double
    Dim parsedTemp As Double
    Dim resOhm As Double
    Dim hasRes As Boolean

    Dim x() As Double
    Dim y() As Double
    Dim fitN As Long
    Dim coeff(0 To 4) As Double

    If Not BuildLoop(bgFieldStart, bgFieldEnd, bgFieldStep, bgStepActual, nBg) Then
        RunBackgroundSweepAndFit = False
        Exit Function
    End If

    ' Collect background R(B) points from ETO Ch2 and append live rows for visibility.
    ReDim x(1 To nBg)
    ReDim y(1 To nBg)

    DynaCool.SetTemperature bgTemp_K, 10, 0 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0019 BG: Set Temp
    DynaCool.SetField bgFieldStart, bgFieldRate, 0, 0 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0020 BG: Set field start
    DynaCool.WaitFor(3, 60, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0021 BG: Wait For %t and Field stable

    DynaCool.SequenceMeasure "ETODF '" & bgDataPath & "' 0 Untitled" 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0022 BG: ETODF open

    For i = 1 To nBg
        commandField = bgFieldStart + CDbl(i - 1) * bgStepActual

        DynaCool.SetField commandField, bgFieldRate, 0, 0 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0023 BG: Set field point
        DynaCool.WaitFor(2, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0024 BG: Wait For %t stable

        DynaCool.SequenceMeasure "ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 1 " & etoiVParams 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0025 BG: ETOIV Ch2
        DynaCool.WaitFor(0, 1, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0025a BG: Flush ETO buffer for live append

        If Not AppendWithRetry(bgDataPath, _
                               False, _
                               commandField, _
                               BAD_VALUE, _
                               BAD_VALUE, _
                               BAD_VALUE, _
                               BAD_VALUE, _
                               BAD_VALUE, _
                               10) Then
            MV_Log "[BG][WARN] Live append failed at BG step " & CStr(i)
        End If
    Next i

    DynaCool.WaitFor(0, 1, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>0026 BG: Flush ETO buffer

    fitN = 0
    For i = 1 To nBg
        blockIndex = i - 1
        hasRes = TryExtractResistanceWithRetry(bgDataPath, blockIndex, IV_CH2_CURR_COL, IV_CH2_VOLT_COL, IV_CH2_AVG_COL, IV_CH2_GAIN_COL, resOhm)

        If hasRes Then
            fitN = fitN + 1

            If IV_ExtractBlockTempFieldFromFile(bgDataPath, blockIndex, parsedTemp, parsedField) Then
                If parsedField > BAD_VALUE / 2# Then
                    x(fitN) = parsedField
                Else
                    x(fitN) = bgFieldStart + CDbl(i - 1) * bgStepActual
                End If
            Else
                x(fitN) = bgFieldStart + CDbl(i - 1) * bgStepActual
            End If

            y(fitN) = resOhm
        End If
    Next i

    DynaCool.SetTemperature(2.8, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>00027 Set temp above TC after sweep
    DynaCool.SetField(0, 10, 0, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>00028 Zero OOP field after sweep
    DynaCool.WaitFor(3, 10, 0) 'mvseq:fn_PPMS_BSweep_Helm_IP.seq(1)>00029 Wait For %t stable
    
    If fitN < minPoints Then
        MV_Log "[BG][WARN] Not enough points for polynomial fit: " & CStr(fitN)
        RunBackgroundSweepAndFit = False
        Exit Function
    End If

    If Not FitPolynomial4(x, y, fitN, coeff, outR2, outRms) Then
        RunBackgroundSweepAndFit = False
        Exit Function
    End If

    If Not EstimateZeroFromPoly4(coeff, bgFieldStart, bgFieldEnd, outZero_Oe) Then
        RunBackgroundSweepAndFit = False
        Exit Function
    End If

    ' Export dedicated background-fit plot file (raw points + fitted curves).
    Call WriteBackgroundFitPlot(bgDataPath, x, y, fitN, coeff)

    RunBackgroundSweepAndFit = True
End Function

Private Function TryExtractResistanceWithRetry(ByVal dataPath As String, _
                                               ByVal blockIndex As Long, _
                                               ByVal currCol As Long, _
                                               ByVal voltCol As Long, _
                                               ByVal avgCol As Long, _
                                               ByVal gainCol As Long, _
                                               ByRef outRes_Ohm As Double) As Boolean
    Dim i As Long
    Dim result As IV_BlockResult
    Dim avg_s As Double
    Dim gain As Double
    Dim hasAvg As Boolean
    Dim hasGain As Boolean

    outRes_Ohm = BAD_VALUE

    For i = 1 To 25
        If IV_ExtractBlockWithMetadataFromFile(dataPath, _
                                               blockIndex, _
                                               currCol, _
                                               voltCol, _
                                               avgCol, _
                                               gainCol, _
                                               result, _
                                               avg_s, _
                                               gain, _
                                               hasAvg, _
                                               hasGain) Then
            If result.isValid Then
                outRes_Ohm = result.resistance_Ohm
                TryExtractResistanceWithRetry = True
                Exit Function
            End If
        End If

        MV_WaitSeconds 0.2
        DoEvents
    Next i

    TryExtractResistanceWithRetry = False
End Function

' =========================================================
' Numeric utility helpers
' =========================================================

Private Function MeanFinite(ByVal a As Double, ByVal b As Double) As Double
    If MV_IsFinite(a) And MV_IsFinite(b) Then
        MeanFinite = 0.5 * (a + b)
    ElseIf MV_IsFinite(a) Then
        MeanFinite = a
    ElseIf MV_IsFinite(b) Then
        MeanFinite = b
    Else
        MeanFinite = BAD_VALUE
    End If
End Function

Private Function FitPolynomial4(ByRef x() As Double, _
                                ByRef y() As Double, _
                                ByVal n As Long, _
                                ByRef coeff() As Double, _
                                ByRef outR2 As Double, _
                                ByRef outRms As Double) As Boolean
    Dim sx(0 To 8) As Double
    Dim sxy(0 To 4) As Double
    Dim aug(0 To 4, 0 To 5) As Double
    Dim i As Long
    Dim k As Long
    Dim j As Long

    Dim yi As Double
    Dim yhat As Double
    Dim sse As Double
    Dim sst As Double
    Dim ymean As Double

    For i = 1 To n
        For k = 0 To 8
            sx(k) = sx(k) + (x(i) ^ k)
        Next k
        For k = 0 To 4
            sxy(k) = sxy(k) + y(i) * (x(i) ^ k)
        Next k
        ymean = ymean + y(i)
    Next i

    ymean = ymean / CDbl(n)

    For i = 0 To 4
        For j = 0 To 4
            aug(i, j) = sx(i + j)
        Next j
        aug(i, 5) = sxy(i)
    Next i

    If Not SolveLinear5x5(aug, coeff) Then
        MV_SetError "Background polynomial fit failed (singular matrix)"
        FitPolynomial4 = False
        Exit Function
    End If

    sse = 0#
    sst = 0#
    For i = 1 To n
        yi = y(i)
        yhat = EvalPoly4(coeff, x(i))
        sse = sse + (yi - yhat) * (yi - yhat)
        sst = sst + (yi - ymean) * (yi - ymean)
    Next i

    outRms = Sqr(sse / CDbl(n))
    If sst > 1E-18 Then
        outR2 = 1# - (sse / sst)
    Else
        outR2 = 0#
    End If

    FitPolynomial4 = True
End Function

Private Function SolveLinear5x5(ByRef aug() As Double, _
                                ByRef coeff() As Double) As Boolean
    Dim i As Long
    Dim j As Long
    Dim k As Long
    Dim maxRow As Long
    Dim maxAbs As Double
    Dim tmp As Double
    Dim pivot As Double
    Dim factor As Double

    For i = 0 To 4
        maxRow = i
        maxAbs = Abs(aug(i, i))
        For k = i + 1 To 4
            If Abs(aug(k, i)) > maxAbs Then
                maxAbs = Abs(aug(k, i))
                maxRow = k
            End If
        Next k

        If maxAbs < 1E-24 Then
            SolveLinear5x5 = False
            Exit Function
        End If

        If maxRow <> i Then
            For j = i To 5
                tmp = aug(i, j)
                aug(i, j) = aug(maxRow, j)
                aug(maxRow, j) = tmp
            Next j
        End If

        pivot = aug(i, i)
        For j = i To 5
            aug(i, j) = aug(i, j) / pivot
        Next j

        For k = 0 To 4
            If k <> i Then
                factor = aug(k, i)
                If factor <> 0# Then
                    For j = i To 5
                        aug(k, j) = aug(k, j) - factor * aug(i, j)
                    Next j
                End If
            End If
        Next k
    Next i

    For i = 0 To 4
        coeff(i) = aug(i, 5)
    Next i

    SolveLinear5x5 = True
End Function

' =========================================================
' Background zero-field estimation
' =========================================================

Private Function EstimateZeroFromPoly4(ByRef coeff() As Double, _
                                       ByVal startField As Double, _
                                       ByVal endField As Double, _
                                       ByRef outB0 As Double) As Boolean
    Dim leftField As Double
    Dim rightField As Double
    Dim i As Long
    Dim nGrid As Long
    Dim b As Double
    Dim stepB As Double
    Dim yPrev As Double
    Dim yCur As Double
    Dim yNext As Double
    Dim bestB As Double
    Dim bestAbsB As Double
    Dim foundLocal As Boolean

    leftField = startField
    rightField = endField
    If leftField > rightField Then
        leftField = endField
        rightField = startField
    End If

    If rightField = leftField Then
        outB0 = leftField
        EstimateZeroFromPoly4 = True
        Exit Function
    End If

    nGrid = 801
    stepB = (rightField - leftField) / CDbl(nGrid - 1)

    bestAbsB = 1E+99
    foundLocal = False

    yPrev = EvalPoly4(coeff, leftField)
    For i = 1 To nGrid - 2
        b = leftField + CDbl(i) * stepB
        yCur = EvalPoly4(coeff, b)
        yNext = EvalPoly4(coeff, b + stepB)

        If (yCur <= yPrev) And (yCur <= yNext) Then
            If Abs(b) < bestAbsB Then
                bestAbsB = Abs(b)
                bestB = b
                foundLocal = True
            End If
        End If

        yPrev = yCur
    Next i

    If Not foundLocal Then
        bestB = FindGlobalMinOnGrid(coeff, leftField, rightField, nGrid)
    End If

    outB0 = bestB
    EstimateZeroFromPoly4 = True
End Function

Private Function FindGlobalMinOnGrid(ByRef coeff() As Double, _
                                     ByVal leftField As Double, _
                                     ByVal rightField As Double, _
                                     ByVal nGrid As Long) As Double
    Dim i As Long
    Dim b As Double
    Dim stepB As Double
    Dim y As Double
    Dim bestY As Double
    Dim bestB As Double

    stepB = (rightField - leftField) / CDbl(nGrid - 1)
    bestB = leftField
    bestY = EvalPoly4(coeff, leftField)

    For i = 1 To nGrid - 1
        b = leftField + CDbl(i) * stepB
        y = EvalPoly4(coeff, b)
        If y < bestY Then
            bestY = y
            bestB = b
        End If
    Next i

    FindGlobalMinOnGrid = bestB
End Function

Private Function EvalPoly4(ByRef coeff() As Double, ByVal x As Double) As Double
    EvalPoly4 = coeff(0) + coeff(1) * x + coeff(2) * x * x + coeff(3) * x * x * x + coeff(4) * x * x * x * x
End Function

' =========================================================
' Background fit-plot export
' =========================================================

Private Sub WriteBackgroundFitPlot(ByVal bgDataPath As String, _
                                   ByRef x() As Double, _
                                   ByRef y() As Double, _
                                   ByVal n As Long, _
                                   ByRef coeff() As Double)
    On Error GoTo EH

    Dim outPath As String
    Dim outFile As Object
    Dim rowData(1 To 8) As Variant
    Dim i As Long
    Dim smoothPoints As Long
    Dim minX As Double
    Dim maxX As Double
    Dim xi As Double

    If n < 1 Then Exit Sub

    outPath = BackgroundFitPlotPath(bgDataPath)

    Set outFile = New MultiVuDataFile
    outFile.AddColumn "Field (Oe)", mvStartupAxisX
    outFile.AddColumn "Bg Measured R (Ohm)", mvStartupAxisY1
    outFile.AddColumn "Bg Fit R (Ohm)", mvStartupAxisY2
    outFile.AddColumn "Bg Fit Smooth R (Ohm)", mvStartupAxisY2
    outFile.CreateFileAndWriteHeader outPath, "Background fit plot", "; Background fit (raw and polynomial)"

    rowData(1) = "Field (Oe)"
    rowData(3) = "Bg Measured R (Ohm)"
    rowData(5) = "Bg Fit R (Ohm)"
    rowData(7) = "Bg Fit Smooth R  (Ohm)"

    For i = 1 To n
        rowData(2) = x(i)
        rowData(4) = y(i)
        rowData(6) = EvalPoly4(coeff, x(i))
        rowData(8) = ""
        Call outFile.WriteDataUsingArray(rowData, False)
    Next i

    minX = x(1)
    maxX = x(1)
    For i = 2 To n
        If x(i) < minX Then minX = x(i)
        If x(i) > maxX Then maxX = x(i)
    Next i

    If maxX < minX Then
        xi = minX
        minX = maxX
        maxX = xi
    End If

    smoothPoints = 201
    If maxX = minX Then
        rowData(2) = minX
        rowData(4) = ""
        rowData(6) = ""
        rowData(8) = EvalPoly4(coeff, minX)
        Call outFile.WriteDataUsingArray(rowData, False)
    Else
        For i = 0 To smoothPoints - 1
            xi = minX + (maxX - minX) * (CDbl(i) / CDbl(smoothPoints - 1))
            rowData(2) = xi
            rowData(4) = ""
            rowData(6) = ""
            rowData(8) = EvalPoly4(coeff, xi)
            Call outFile.WriteDataUsingArray(rowData, False)
        Next i
    End If

    MV_Log "[BG][PLOT] Fit plot saved: " & outPath
    Exit Sub

EH:
    MV_Log "[BG][WARN] Failed to write BG fit plot file: " & Err.Description
End Sub

Private Function BackgroundFitPlotPath(ByVal bgDataPath As String) As String
    Dim lastDot As Long

    lastDot = InStrRev(bgDataPath, ".")
    If lastDot > 0 Then
        BackgroundFitPlotPath = Left$(bgDataPath, lastDot - 1) & "_FitPlot.dat"
    Else
        BackgroundFitPlotPath = bgDataPath & "_FitPlot.dat"
    End If
End Function

' =========================================================
' Timing helpers
' =========================================================

Private Function TimerElapsedSeconds(ByVal tStart As Double, ByVal tEnd As Double) As Double
    If tEnd >= tStart Then
        TimerElapsedSeconds = tEnd - tStart
    Else
        TimerElapsedSeconds = (86400# - tStart) + tEnd
    End If
End Function

Private Function TimerElapsedMs(ByVal tStart As Double, ByVal tEnd As Double) As Double
    TimerElapsedMs = 1000# * TimerElapsedSeconds(tStart, tEnd)
End Function

' =========================================================
' String formatting helpers
' =========================================================

Private Function DoubleToCommandText(ByVal Value As Double) As String
    Dim s As String

    s = Trim$(CStr(Value))
    s = Replace$(s, ",", ".")
    DoubleToCommandText = s
End Function

Private Function NumericTokenNoRound(ByVal Value As Double) As String
    Dim s As String

    s = DoubleToCommandText(Value)
    s = Replace$(s, ".", "_")
    s = Replace$(s, "+", "")
    s = Replace$(s, "-", "m")
    If Len(s) = 0 Then s = "0"

    NumericTokenNoRound = s
End Function

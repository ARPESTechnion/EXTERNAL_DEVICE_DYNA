'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Instruments\MV_K2450_Hall.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"
'#Uses ".\MV_RunWrappers.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"

Option Explicit

Public Sub fn_IP_Loop_Helm_Loop_Bsweep( _
    ByVal Helm_Field_Start As Double, _
    ByVal Helm_Field_End As Double, _
    ByVal Helm_Field_Step As Double, _
    ByVal IV_Current_mA As Double, _
    ByVal IV_Frequency_Hz As Double, _
    ByVal IV_Averaging As Long, _
    ByVal IV_Gain_Code As String, _
    ByVal IV_Sweep_Code As String, _
    ByVal Wait_For_Stable_s As Long, _
    ByVal Helm_Field_Rate As Double, _
    ByVal Measure_Ch1 As Boolean, _
    ByVal Measure_Ch2 As Boolean, _
    ByVal Temp_Start As Double, _
    ByVal Temp_End As Double, _
    ByVal Temp_Step As Double, _
    ByVal IP_Field_Start As Double, _
    ByVal IP_Field_End As Double, _
    ByVal IP_Field_Step As Double, _
    ByVal K2600_resourceName As String, _
    ByVal K2450_resourceName As String, _
    ByVal Hallbar As String, _
    ByVal BaseFolder As String, _
    Optional ByVal Append_Output As Boolean = False)

    ' =========================================================
    ' Derived file path variables (set per condition inside the loop)
    ' =========================================================
    Dim ETO_DataFile As String
    Dim Helmholtz_LogFile As String
    Dim Merged_LogFile As String
    Dim BaseName As String
    Dim RunOutputStem As String

    ' =========================================================
    ' Derived variables
    ' =========================================================
    Dim N_Temps As Long
    Dim N_IP As Long
    Dim N_Steps As Long
    Dim IT As Long
    Dim IIP As Long
    Dim IB1 As Long
    Dim Measurement_Temperature As Double
    Dim In_Plane_Field As Double
    Dim B1 As Double
    Dim Helm_Field_Step_Actual As Double
    Dim Temp_Step_Actual As Double
    Dim IP_Field_Step_Actual As Double
    Dim SweepSuffix As String
    Dim RunSuffix As String
    Dim ETOIV_Params As String
    Dim tStepStart As Double
    Dim tAfterETO As Double
    Dim tAfterWait As Double
    Dim waitMs As Double
    Dim appendMs As Double
    Dim totalMs As Double
    Dim appendOk As Boolean
    Dim consecutiveAppendFail As Long
    Dim totalAppendFail As Long
    Dim catchOk As Boolean
    Dim catchCount As Long
    Dim Skip_IP_Field_Commands As Boolean
    Dim Is_Single_IP_Zero_Target As Boolean
    Dim Current_PPMS_Field_Oe As Double

    If Temp_Start = Temp_End Then
        Temp_Step_Actual = 0#
        N_Temps = 1
    Else
        If Temp_Step = 0# Then Exit Sub
        Temp_Step_Actual = Sgn(Temp_End - Temp_Start) * Abs(Temp_Step)
        N_Temps = CLng(Fix((Abs(Temp_End - Temp_Start) / Abs(Temp_Step)) + 0.5)) + 1
    End If

    If IP_Field_Start = IP_Field_End Then
        IP_Field_Step_Actual = 0#
        N_IP = 1
    Else
        If IP_Field_Step = 0# Then Exit Sub
        IP_Field_Step_Actual = Sgn(IP_Field_End - IP_Field_Start) * Abs(IP_Field_Step)
        N_IP = CLng(Fix((Abs(IP_Field_End - IP_Field_Start) / Abs(IP_Field_Step)) + 0.5)) + 1
    End If

    If Helm_Field_Start = Helm_Field_End Then
        Helm_Field_Step_Actual = 0#
        N_Steps = 1
    Else
        If Helm_Field_Step = 0# Then Exit Sub
        Helm_Field_Step_Actual = Sgn(Helm_Field_End - Helm_Field_Start) * Abs(Helm_Field_Step)
        N_Steps = CLng(Fix((Abs(Helm_Field_End - Helm_Field_Start) / Abs(Helm_Field_Step)) + 0.5)) + 1
    End If

    Is_Single_IP_Zero_Target = (N_IP = 1 And IP_Field_Start = 0# And IP_Field_End = 0#)

    SweepSuffix = NumericTokenNoRound(Helm_Field_Start) & "_" & _
                  NumericTokenNoRound(Abs(Helm_Field_Step)) & "_" & _
                  NumericTokenNoRound(Helm_Field_End) & "G"
    BaseName = "BSweep_" & SweepSuffix
    ETOIV_Params = DoubleToCommandText(IV_Current_mA) & " " & _
                   DoubleToCommandText(IV_Frequency_Hz) & " 0 " & _
                   CStr(IV_Averaging) & " 0 " & _
                   IV_Gain_Code & " " & IV_Sweep_Code

    ' =========================================================
    ' Instruments Init
    ' =========================================================
    ' K2600 is connected per run because MV_CloseSession() disconnects instruments.

    ' =========================================================
    ' Outer loops: temperature x in-plane field
    ' =========================================================
    For IT = 1 To N_Temps
    For IIP = 1 To N_IP

        Measurement_Temperature = Temp_Start + CDbl(IT - 1) * Temp_Step_Actual
        In_Plane_Field = IP_Field_Start + CDbl(IIP - 1) * IP_Field_Step_Actual
        If Is_Single_IP_Zero_Target Then In_Plane_Field = 0#

        Skip_IP_Field_Commands = False
        If Is_Single_IP_Zero_Target Then
            Current_PPMS_Field_Oe = DYNA_GetField_Oe()
            If Current_PPMS_Field_Oe > -9E98 Then
                Skip_IP_Field_Commands = (Abs(Current_PPMS_Field_Oe) < 2#)
            End If
        End If

        RunSuffix = "_T_" & NumericTokenNoRound(Measurement_Temperature) & "K" & _
                "_IP_" & NumericTokenNoRound(In_Plane_Field) & "G"

        RunOutputStem = ResolveAvailableOutputStem( _
                    BaseFolder & BaseName & RunSuffix, _
                    Append_Output, _
                    ".dat", _
                    "_HelmholtzLog.dat", _
                    "_Analyzed.dat")
        ETO_DataFile = RunOutputStem & ".dat"
        Helmholtz_LogFile = RunOutputStem & "_HelmholtzLog.dat"
        Merged_LogFile = RunOutputStem & "_Analyzed.dat"

        ' ---------------------------------------------------------
        ' Session Init for this condition
        ' ---------------------------------------------------------
        MV_InitSessionWithPostAnalysis("Helmholtz_Bsweep" & RunSuffix, Helmholtz_LogFile, Merged_LogFile) 'mvseq:Helmholtz_Bsweep.seq(1)>0007 Init Session

        ' ---------------------------------------------------------
        ' Reconnect K2600 at the beginning of each run
        ' ---------------------------------------------------------
        K2600_Connect(K2600_resourceName) 'mvseq:Helmholtz_Bsweep.seq(1)>0001 Connect To K2600
        Helm_ConfigSource(3, 1)           'mvseq:Helmholtz_Bsweep.seq(1)>0002 Config K2600
        'K2450_Connect(K2450_resourceName) 'mvseq:Helmholtz_Bsweep.seq(1)>0003 Connect To K2450
        'Hall_Configure(2, 2, 1, 5)        'mvseq:Helmholtz_Bsweep.seq(1)>0004 Config K2450
        'Hall_ApplyPreset(Hallbar)         'mvseq:Helmholtz_Bsweep.seq(1)>0005 Set Hall Bar
        'Hall_SetCalibration(MV_HallVPerG, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0006 Set Hall Bar Calibration

        ' ---------------------------------------------------------
        ' Set Initial Conditions
        ' ---------------------------------------------------------
        DynaCool.SetTemperature(2.8, 10, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0008 Set Temp
        If Not Skip_IP_Field_Commands Then
            DynaCool.SetField(In_Plane_Field, 50.0, 0, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0009 Set In-Plane Field
        End If
        DynaCool.WaitFor(1+2*1+4*1+8*0, 60, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0010 Wait For %t
        DynaCool.SetTemperature(Measurement_Temperature, 10, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0011 Set Temp
        Helm_SetField(Helm_Field_Start, 10) 'mvseq:Helmholtz_Bsweep.seq(1)>0013 Set Helmholtz Field
        Helm_WaitStable(1000, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Wait Helm Stable
        DynaCool.WaitFor(1+2*1+4*0+8*0, Wait_For_Stable_s, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0015 Wait For %t

        ' ---------------------------------------------------------
        ' Open ETO Data File
        ' ---------------------------------------------------------
        DynaCool.SequenceMeasure("ETODF '" & ETO_DataFile & "' 0 Untitled") 'mvseq:Helmholtz_Bsweep.seq(1)>0016 ETODF

        ' ---------------------------------------------------------
        ' Helmholtz B-Field Sweep Loop
        ' ---------------------------------------------------------
        consecutiveAppendFail = 0
        totalAppendFail = 0

        For IB1 = 1 To N_Steps 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Scan Helmholtz Field
            tStepStart = Timer
            B1 = Helm_Field_Start + CDbl(IB1 - 1) * Helm_Field_Step_Actual 'mvseq:Helmholtz_Bsweep.seq(1)>0017 Scan Helmholtz Field
            Helm_SetField(B1, Helm_Field_Rate) 'mvseq:Helmholtz_Bsweep.seq(1)>0017 Scan Helmholtz Field

            If B1 = 0  Then
            	Helm_WaitStable(Wait_For_Stable_s, 60) 'mvseq:Helmholtz_Bsweep.seq(1)>0017 Scan Helmholtz Field
	   		Else
	   			Helm_WaitStable(Wait_For_Stable_s, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0017 Scan Helmholtz Field
		    End If

            Helm_WaitStable(Wait_For_Stable_s, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0017 Scan Helmholtz Field
            Helm_MeasureAndLog() 'mvseq:Helmholtz_Bsweep.seq(1)>0018 Log Helmholtz State

            If Measure_Ch1 Then
                DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 0 " & ETOIV_Params) 'mvseq:Helmholtz_Bsweep.seq(1)>0019 ETOIV Ch1
            End If
            If Measure_Ch2 Then
                DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 1 " & ETOIV_Params) 'mvseq:Helmholtz_Bsweep.seq(1)>0020 ETOIV Ch2
            End If
            tAfterETO = Timer

            DynaCool.WaitFor(0, 1, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0021 Wait For %t
            tAfterWait = Timer

            appendOk = PostAnalysis_AppendAfterETO(ETO_DataFile, False, Measure_Ch1, Measure_Ch2, False, True, 9, 10, 12, 23, 29, 30, 32, 43) 'mvseq:Helmholtz_Bsweep.seq(1)>0022 Append Analysis
            If appendOk Then
                consecutiveAppendFail = 0
            Else
                consecutiveAppendFail = consecutiveAppendFail + 1
                totalAppendFail = totalAppendFail + 1
                MV_Log "[SEQ][WARN] Post-analysis append not ready at step " & CStr(IB1) & " (consecutive fails=" & CStr(consecutiveAppendFail) & ")"
                If consecutiveAppendFail >= 5 Then
                    MV_Log "[SEQ][WARN] Persistent ETO lag detected (" & CStr(consecutiveAppendFail) & " consecutive append fails)"
                End If
            End If

            waitMs = TimerElapsedMs(tAfterETO, tAfterWait)
            appendMs = TimerElapsedMs(tAfterWait, Timer)
            totalMs = TimerElapsedMs(tStepStart, Timer)
            MV_Log "[SEQ][TIMING] step=" & CStr(IB1) & " wait_ms=" & Format(waitMs, "0") & " append_ms=" & Format(appendMs, "0") & " total_ms=" & Format(totalMs, "0") & " append_ok=" & CStr(IIf(appendOk, 1, 0))
        Next IB1

        ' ---------------------------------------------------------
        ' Catch-up: recover steps that were not ready at sweep start
        ' ---------------------------------------------------------
        If totalAppendFail > 0 Then
            MV_Log "[SEQ] Catch-up pass: " & CStr(totalAppendFail) & " step(s) may be pending"
            DynaCool.WaitFor(0, 1, 0) ' allow last ETO blocks to flush
            catchCount = 0
            Do
                catchOk = PostAnalysis_AppendAfterETO(ETO_DataFile, False, Measure_Ch1, Measure_Ch2, False, True, 9, 10, 12, 23, 29, 30, 32, 43)
                If Not catchOk Then Exit Do
                catchCount = catchCount + 1
            Loop While catchCount < totalAppendFail
            If catchCount > 0 Then
                MV_Log "[SEQ] Catch-up recovered " & CStr(catchCount) & " step(s)"
            End If
            If catchCount < totalAppendFail Then
                MV_Log "[SEQ][WARN] " & CStr(totalAppendFail - catchCount) & " step(s) could not be recovered"
            End If
        End If

        ' ---------------------------------------------------------
        ' Ramp down between runs
        ' ---------------------------------------------------------
        Helm_SetField(0, 10) 'mvseq:Helmholtz_Bsweep.seq(1)>0024 Ramp Helmholtz Field To Zero
        Helm_WaitStable(10000, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0025 Wait Helm Stable
        DynaCool.WaitFor(1+2*1+4*0+8*0, 1, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0026 Wait For %t

        MV_CloseSession() 'mvseq:Helmholtz_Bsweep.seq(1)>0027 Close Session

    Next IIP
    Next IT

End Sub

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

Private Function CountEtoDataRows(ByVal filePath As String) As Long
    Dim fso As Object
    Dim file As Object
    Dim lineText As String
    Dim inData As Boolean
    Dim rowCount As Long

    On Error GoTo EH

    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(filePath) Then
        CountEtoDataRows = 0
        Exit Function
    End If

    Set file = fso.OpenTextFile(filePath, 1)
    inData = False
    rowCount = 0

    While Not file.AtEndOfStream
        lineText = file.ReadLine
        If Not inData Then
            If InStr(lineText, "[Data]") > 0 Then
                inData = True
                If Not file.AtEndOfStream Then lineText = file.ReadLine ' CSV header
                If Not file.AtEndOfStream Then lineText = file.ReadLine ' QD blank separator
            End If
        Else
            If Trim$(lineText) <> "" Then
                rowCount = rowCount + 1
            End If
        End If
    Wend

    file.Close
    CountEtoDataRows = rowCount
    Exit Function
EH:
    CountEtoDataRows = 0
End Function

Private Function WaitForEtoDataReady(ByVal filePath As String, ByVal minDataRows As Long, ByVal timeout_s As Double) As Boolean
    Dim t0 As Double
    Dim rowsNow As Long

    t0 = Timer
    Do
        rowsNow = CountEtoDataRows(filePath)
        If rowsNow >= minDataRows Then
            WaitForEtoDataReady = True
            Exit Function
        End If

        MV_WaitSeconds 0.2
        DoEvents
    Loop While MV_TimerElapsedSeconds(t0, Timer) < timeout_s

    WaitForEtoDataReady = False
End Function

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

Private Function ResolveAvailableOutputStem(ByVal baseStem As String, _
                                            ByVal appendExisting As Boolean, _
                                            ParamArray suffixes() As Variant) As String
    Dim candidateStem As String
    Dim suffixIndex As Long
    Dim candidateIndex As Long

    candidateStem = baseStem
    If appendExisting Then
        ResolveAvailableOutputStem = candidateStem
        Exit Function
    End If

    Do
        For suffixIndex = LBound(suffixes) To UBound(suffixes)
            If FileExists(CStr(candidateStem & CStr(suffixes(suffixIndex)))) Then Exit For
        Next suffixIndex

        If suffixIndex > UBound(suffixes) Then
            ResolveAvailableOutputStem = candidateStem
            Exit Function
        End If

        candidateIndex = candidateIndex + 1
        candidateStem = baseStem & "_" & Format$(candidateIndex, "000")
    Loop
End Function

Private Function FileExists(ByVal filePath As String) As Boolean
    FileExists = (Len(Dir$(filePath)) > 0)
End Function

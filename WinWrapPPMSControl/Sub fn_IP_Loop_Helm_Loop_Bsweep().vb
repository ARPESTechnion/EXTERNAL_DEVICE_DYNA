Sub fn_IP_Loop_Helm_Loop_Bsweep()
    ' =========================================================
    ' Measurement Configuration - edit these values
    ' =========================================================
    Dim Helm_Field_Start As Double ' Helmholtz sweep start (Oe)
    Dim Helm_Field_End As Double ' Helmholtz sweep end (Oe)
    Dim Helm_Field_Step As Double ' Helmholtz sweep step size (Oe)
    Dim IV_Current_mA As Double ' ETO IV peak current (mA)
    Dim IV_Frequency_Hz As Double ' ETO IV excitation frequency (Hz)
    ' Options: 0.3051758 | 1.017253 | 1.525879 | 3.051758
    ' 6.103516 | 12.20704 | 24.41407 | 48.82813 | 97.65625
    Dim IV_Averaging As Long ' ETO IV averaging points
    Dim IV_Gain_Code As String ' ETO IV gain (3 numbers, space-separated):
    ' "3 2 1"=44uV "3 2 0"=130uV "3 1 1"=440uV "3 1 0"=1.3mV
    ' "3 0 1"=4.4mV "3 0 0"=13mV "1 2 0"=40mV "1 1 1"=130mV
    ' "1 1 0"=0.4V "1 0 1"=1.3V "1 0 0"=4V
    Dim IV_Sweep_Code As String ' ETO IV sweep waveform (3 numbers, space-separated):
    ' "0 0 0" = 0->Max->Min->0 (full bipolar, default)
    ' "1 0 0" = 0->Min->Max->0
    ' "2 0 0" = 0->Max->0 (positive only)
    ' "3 0 0" = 0->Min->0 (negative only)
    Dim Wait_For_Stable_s As Long ' Helmholtz field stabilization timeout (s)
    Dim Helm_Field_Rate As Double ' Helmholtz field ramp rate in the sweep loop (Oe/s)
    Dim Measure_Ch1 As Boolean ' Enable ETO channel 1
    Dim Measure_Ch2 As Boolean ' Enable ETO channel 2
    Dim Temp_Start As Double ' Temperature sweep start (K)
    Dim Temp_End As Double ' Temperature sweep end (K)
    Dim Temp_Step As Double ' Temperature sweep step (K)
    Dim IP_Field_Start As Double ' In-plane field sweep start (Oe)
    Dim IP_Field_End As Double ' In-plane field sweep end (Oe)
    Dim IP_Field_Step As Double ' In-plane field sweep step (Oe)

    Helm_Field_Start = -200 ' Oe
    Helm_Field_End = 200 ' Oe
    Helm_Field_Step = 2 ' Oe
    IV_Current_mA = 0.0005 ' mA
    IV_Frequency_Hz = 12.20704 ' Hz
    IV_Averaging = 60
    IV_Gain_Code = "3 2 1" ' 44 uV range
    IV_Sweep_Code = "0 0 0" ' 0->Max->Min->0
    Wait_For_Stable_s = 300 ' s
    Helm_Field_Rate = 1 ' Oe/s
    Measure_Ch1 = False
    Measure_Ch2 = True
    Temp_Start = 2.65 ' K
    Temp_End = 2.65 ' K
    Temp_Step = 1 ' K
    IP_Field_Start = 0 ' Oe
    IP_Field_End = 2000 ' Oe
    IP_Field_Step = 500 ' Oe

    ' =========================================================
    ' Instrument & File Configuration
    ' =========================================================
    Dim K2600_resourceName As String
    Dim K2450_resourceName As String
    Dim Hallbar As String
    Dim ETO_DataFile As String
    Dim Helmholtz_LogFile As String
    Dim Merged_LogFile As String

    Dim BaseFolder As String
    Dim BaseName As String

    K2600_resourceName = "GPIB0::26::INSTR"
    K2450_resourceName = "GPIB0::18::INSTR"
    Hallbar = "wire2"

    BaseFolder = "C:\Users\user\Documents\Shared Data\Ilay Mangel\Clocks and Rings\4Hb\RIE Rings\TaS2005LW\TN\"

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
    Dim BlocksPerStep As Long
    Dim RequiredDataRows As Long

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

    SweepSuffix = Format(Helm_Field_Start, "0.###") & "_" & _
                  Format(Abs(Helm_Field_Step), "0.###") & "_" & _
                  Format(Helm_Field_End, "0.###") & "G"
    BaseName = "BSweep_" & SweepSuffix
    ETOIV_Params = Format(IV_Current_mA, "0.#######") & " " & _
                   Format(IV_Frequency_Hz, "0.#######") & " 0 " & _
                   CStr(IV_Averaging) & " 0 " & _
                   IV_Gain_Code & " " & IV_Sweep_Code

    BlocksPerStep = 0
    If Measure_Ch1 Then BlocksPerStep = BlocksPerStep + 1
    If Measure_Ch2 Then BlocksPerStep = BlocksPerStep + 1

    ' =========================================================
    ' Instruments Init (once)
    ' =========================================================
    K2600_Connect(K2600_resourceName) 'mvseq:Helmholtz_Bsweep.seq(1)>0001 Connect To K2600
    Helm_ConfigSource(3, 1)           'mvseq:Helmholtz_Bsweep.seq(1)>0002 Config K2600
    K2450_Connect(K2450_resourceName) 'mvseq:Helmholtz_Bsweep.seq(1)>0003 Connect To K2450
    Hall_Configure(2, 2, 1, 5)        'mvseq:Helmholtz_Bsweep.seq(1)>0004 Config K2450
    Hall_ApplyPreset(Hallbar)         'mvseq:Helmholtz_Bsweep.seq(1)>0005 Set Hall Bar
    Hall_SetCalibration(MV_HallVPerG, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0006 Set Hall Bar Calibration

    ' =========================================================
    ' Outer loops: temperature x in-plane field
    ' =========================================================
    For IT = 1 To N_Temps
    For IIP = 1 To N_IP

        Measurement_Temperature = Temp_Start + CDbl(IT - 1) * Temp_Step_Actual
        In_Plane_Field = IP_Field_Start + CDbl(IIP - 1) * IP_Field_Step_Actual
        RunSuffix = "_" & Format(Measurement_Temperature, "0.##") & "K" & _
                    "_IP_" & CStr(CLng(In_Plane_Field)) & "G"

        ETO_DataFile      = BaseFolder & BaseName & RunSuffix & ".dat"
        Helmholtz_LogFile = BaseFolder & BaseName & RunSuffix & "_HelmholtzLog.dat"
        Merged_LogFile    = BaseFolder & BaseName & RunSuffix & "_Analyzed.dat"

        ' ---------------------------------------------------------
        ' Session Init for this condition
        ' ---------------------------------------------------------
        MV_InitSessionWithPostAnalysis("Helmholtz_Bsweep" & RunSuffix, Helmholtz_LogFile, Merged_LogFile) 'mvseq:Helmholtz_Bsweep.seq(1)>0007 Init Session

        ' ---------------------------------------------------------
        ' Set Initial Conditions
        ' ---------------------------------------------------------
        DynaCool.SetTemperature(Measurement_Temperature, 10, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0008 Set Temp
        DynaCool.SetField(In_Plane_Field, 50.0, 0, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0009 Set In-Plane Field
        Helm_SetField(Helm_Field_Start, 10) 'mvseq:Helmholtz_Bsweep.seq(1)>0010 Set Helmholtz Field
        Helm_WaitStable(1000, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0011 Wait Helm Stable
        DynaCool.WaitFor(1+2*1+4*0+8*0, Wait_For_Stable_s, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0012 Wait For %t

        ' ---------------------------------------------------------
        ' Open ETO Data File
        ' ---------------------------------------------------------
        DynaCool.SequenceMeasure("ETODF '" & ETO_DataFile & "' 0 Untitled") 'mvseq:Helmholtz_Bsweep.seq(1)>0013 ETODF

        ' ---------------------------------------------------------
        ' Helmholtz B-Field Sweep Loop
        ' ---------------------------------------------------------
        For IB1 = 1 To N_Steps 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Scan Helmholtz Field
            B1 = Helm_Field_Start + CDbl(IB1 - 1) * Helm_Field_Step_Actual 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Scan Helmholtz Field
            Helm_SetField(B1, Helm_Field_Rate) 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Scan Helmholtz Field
            Helm_WaitStable(Wait_For_Stable_s, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0014 Scan Helmholtz Field
            Helm_MeasureAndLog() 'mvseq:Helmholtz_Bsweep.seq(1)>0015 Log Helmholtz State

            If Measure_Ch1 Then
                DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 0 " & ETOIV_Params) 'mvseq:Helmholtz_Bsweep.seq(1)>0016 ETOIV Ch1
            End If
            If Measure_Ch2 Then
                DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 1 " & ETOIV_Params) 'mvseq:Helmholtz_Bsweep.seq(1)>0017 ETOIV Ch2
            End If

            DynaCool.WaitFor(0, 1, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0018 Wait For %t
            RequiredDataRows = CLng(IB1) * BlocksPerStep * 1023
            If RequiredDataRows > 0 Then
                If Not WaitForEtoDataReady(ETO_DataFile, RequiredDataRows, 30#) Then
                    MV_Log "[SEQ][WARN] ETO data not ready for append at step " & CStr(IB1) & ": " & ETO_DataFile
                End If
            End If
            PostAnalysis_AppendAfterETO(ETO_DataFile, False, Measure_Ch1, Measure_Ch2, False, True, 9, 10, 12, 23, 29, 30, 32, 43) 'mvseq:Helmholtz_Bsweep.seq(1)>0019 Append Analysis
        Next IB1

        ' ---------------------------------------------------------
        ' Ramp down between runs
        ' ---------------------------------------------------------
        DynaCool.SetField(0.0, 50.0, 2, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0020 Ramp Dyna Field To Zero
        Helm_SetField(0, 10) 'mvseq:Helmholtz_Bsweep.seq(1)>0021 Ramp Helmholtz Field To Zero
        Helm_WaitStable(10000, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0022 Wait Helm Stable
        DynaCool.WaitFor(1+2*1+4*0+8*0, 1, 0) 'mvseq:Helmholtz_Bsweep.seq(1)>0023 Wait For %t

        MV_CloseSession() 'mvseq:Helmholtz_Bsweep.seq(1)>0024 Close Session

    Next IIP
    Next IT

End Sub

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
    Loop While (Timer - t0) < timeout_s

    WaitForEtoDataReady = False
End Function
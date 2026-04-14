Sub fn_IP_Loop_Helm_Loop_Bsweep()
    ' =========================================================
    ' Measurement Configuration - edit these values
    ' =========================================================
    Dim Measurement_Temperature As Double ' Target temperature (K)
    Dim Start_Field As Double ' Helmholtz sweep start (Oe)
    Dim End_Field As Double ' Helmholtz sweep end (Oe)
    Dim Field_Step As Double ' Helmholtz step size (Oe)
    Dim In_Plane_Field As Double ' DynaCool in-plane field (Oe), set by outer loop
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

    Measurement_Temperature = 2.65 ' K
    Start_Field = -200 ' Oe
    End_Field = 200 ' Oe
    Field_Step = 2 ' Oe
    IV_Current_mA = 0.0005 ' mA
    IV_Frequency_Hz = 12.20704 ' Hz
    IV_Averaging = 60
    IV_Gain_Code = "3 2 1" ' 44 uV range
    IV_Sweep_Code = "0 0 0" ' 0->Max->Min->0
    Wait_For_Stable_s = 300 ' s
    Helm_Field_Rate = 1 ' Oe/s
    Measure_Ch1 = False
    Measure_Ch2 = True

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
    Dim IPSuffix As String

    K2600_resourceName = "GPIB0::26::INSTR"
    K2450_resourceName = "GPIB0::18::INSTR"
    Hallbar = "wire2"

    BaseFolder = "C:\Users\user\Documents\Shared Data\Ilay Mangel\Clocks and Rings\4Hb\RIE Rings\TaS2005LW\TN\"
    BaseName = "BSweep_2_65K_-200_2_200G"

    ' =========================================================
    ' In-plane field outer loop configuration
    ' =========================================================
    Dim InPlaneFields(1 To 4) As Double
    Dim IIP As Long

    InPlaneFields(1) = 500
    InPlaneFields(2) = 1000
    InPlaneFields(3) = 1500
    InPlaneFields(4) = 2000

    ' =========================================================
    ' Derived variables
    ' =========================================================
    Dim N_Steps As Long
    Dim IB1 As Long
    Dim B1 As Double
    Dim ETOIV_Params As String

    N_Steps = CLng((End_Field - Start_Field) / Field_Step) + 1
    ETOIV_Params = Format(IV_Current_mA, "0.#######") & " " & _
    Format(IV_Frequency_Hz, "0.#######") & " 0 " & _
    CStr(IV_Averaging) & " 0 " & _
    IV_Gain_Code & " " & IV_Sweep_Code

    ' =========================================================
    ' Instruments Init (once)
    ' =========================================================
    K2600_Connect(K2600_resourceName) 'mvseq:Test_Helm_Loop.seq(1)>0001 Connect To K2600
    Helm_ConfigSource(3, 1) 'mvseq:Test_Helm_Loop.seq(1)>0002 Config K2600
    K2450_Connect(K2450_resourceName) 'mvseq:Test_Helm_Loop.seq(1)>0003 Connect To K2450
    Hall_Configure(2, 2, 1, 5) 'mvseq:Test_Helm_Loop.seq(1)>0004 Config K2450
    Hall_ApplyPreset(Hallbar) 'mvseq:Test_Helm_Loop.seq(1)>0005 Set Hall Bar
    Hall_SetCalibration(MV_HallVPerG, 0) 'mvseq:Test_Helm_Loop.seq(1)>0006 Set Hall Bar Calibration

    ' =========================================================
    ' Outer loop: run full Helm sweep for each in-plane field
    ' =========================================================
    For IIP = 1 To 4

    In_Plane_Field = InPlaneFields(IIP)
    IPSuffix       = "_IP_" & CStr(CLng(In_Plane_Field)) & "G"

    ETO_DataFile      = BaseFolder & BaseName & IPSuffix & ".dat"
    Helmholtz_LogFile = BaseFolder & BaseName & IPSuffix & "_HelmholtzLog.dat"
    Merged_LogFile    = BaseFolder & BaseName & IPSuffix & "_Analyzed.dat"

    ' ---------------------------------------------------------
    ' Session Init for this in-plane field
    ' ---------------------------------------------------------
    MV_InitSessionWithPostAnalysis("Test_Helm_Loop" & IPSuffix, Helmholtz_LogFile, Merged_LogFile)

    ' ---------------------------------------------------------
    ' Set Initial Conditions
    ' ---------------------------------------------------------
    DynaCool.SetTemperature(Measurement_Temperature, 10, 0)
    DynaCool.SetField(In_Plane_Field, 50.0, 0, 0)
    Helm_SetField(Start_Field, 10)
    Helm_WaitStable(1000, 0)
    DynaCool.WaitFor(1+2*1+4*0+8*0, Wait_For_Stable_s, 0)

    ' ---------------------------------------------------------
    ' Open ETO Data File
    ' ---------------------------------------------------------
    DynaCool.SequenceMeasure("ETODF '" & ETO_DataFile & "' 0 Untitled")

    ' ---------------------------------------------------------
    ' Helmholtz B-Field Sweep Loop
    ' ---------------------------------------------------------
    For IB1 = 1 To N_Steps
        B1 = Start_Field + (IB1 - 1) * Field_Step
        Helm_SetField(B1, Helm_Field_Rate)
        Helm_WaitStable(Wait_For_Stable_s, 0)
        Helm_MeasureAndLog()

        If Measure_Ch1 Then
            DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 0 " & ETOIV_Params)
        End If
        If Measure_Ch2 Then
            DynaCool.SequenceMeasure("ETOIV 'C:\QdDynacool\default_ETO.qmap' 0 1 " & ETOIV_Params)
        End If

        DynaCool.WaitFor(0, 1, 0)
        PostAnalysis_AppendAfterETO(ETO_DataFile, False, Measure_Ch1, Measure_Ch2, False, True, 9, 10, 12, 23, 29, 30, 32, 43)
    Next IB1

    ' ---------------------------------------------------------
    ' Ramp down between outer-loop runs
    ' ---------------------------------------------------------
        DynaCool.SetField(0.0, 10.0, 2, 0)
        Helm_SetField(0, 10)
        MV_CloseSession()

        Next IIP
End Sub
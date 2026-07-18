'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Instruments\MV_K2450_Hall.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Instruments\MV_K2450_LiveLog.bas"
'#Uses "..\Instruments\MV_K7001.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"
'#Uses "..\Analysis\MV_RTPostAnalysis.bas"
'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Runners\MV_HelmBSweepLoop.bas"
Option Explicit

Public Sub Macro_Run_Helmholtz_BSweep()
    ' =========================================================
    ' Measurement Configuration - edit these values
    ' =========================================================
    Dim Helm_Field_Start      As Double  ' Helmholtz sweep start (Oe)
    Dim Helm_Field_End        As Double  ' Helmholtz sweep end (Oe)
    Dim Helm_Field_Step       As Double  ' Helmholtz step size (Oe)
    Dim Helm_Field_Rate       As Double  ' Helmholtz field ramp rate in sweep loop (Oe/s)

    Dim IV_Current_mA         As Double  ' ETO IV peak current (mA)
    Dim IV_Frequency_Hz       As Double  ' ETO IV excitation frequency (Hz)
                                       '  Options: 0.3051758 | 1.017253 | 1.525879 | 3.051758
                                       '           6.103516  | 12.20704 | 24.41407 | 48.82813 | 97.65625
    Dim IV_Averaging          As Long    ' ETO IV averaging points
    Dim IV_Gain_Code          As String  ' ETO IV gain (3 numbers, space-separated):
                                       '  "3 2 1"=44uV   "3 2 0"=130uV  "3 1 1"=440uV  "3 1 0"=1.3mV
                                       '  "3 0 1"=4.4mV  "3 0 0"=13mV   "1 2 0"=40mV   "1 1 1"=130mV
                                       '  "1 1 0"=0.4V   "1 0 1"=1.3V   "1 0 0"=4V
    Dim IV_Sweep_Code         As String  ' ETO IV sweep waveform (3 numbers, space-separated):
                                       '  "0 0 0" = 0->Max->Min->0  (full bipolar, default)
                                       '  "1 0 0" = 0->Min->Max->0
                                       '  "2 0 0" = 0->Max->0       (positive only)
                                       '  "3 0 0" = 0->Min->0       (negative only)

    Dim Wait_For_Stable_s     As Long    ' Helmholtz field stabilization timeout (s)
    Dim Measure_Ch1           As Boolean ' Enable ETO channel 1
    Dim Measure_Ch2           As Boolean ' Enable ETO channel 2

    Dim Temp_Start            As Double  ' Temperature loop start (K)
    Dim Temp_End              As Double  ' Temperature loop end (K)
    Dim Temp_Step             As Double  ' Temperature step size (K); 0 if start=end

    Dim IP_Field_Start        As Double  ' In-plane field loop start (Oe)
    Dim IP_Field_End          As Double  ' In-plane field loop end (Oe)
    Dim IP_Field_Step         As Double  ' In-plane field step size (Oe); 0 if start=end

    Helm_Field_Start = -150#
    Helm_Field_End = 150#
    Helm_Field_Step = 3#
    Helm_Field_Rate = 10#

    IV_Current_mA = 0.0005
    IV_Frequency_Hz = 12.20704
    IV_Averaging = 60
    IV_Gain_Code = "3 2 1"
    IV_Sweep_Code = "0 0 0"

    Wait_For_Stable_s = 300
    Measure_Ch1 = True
    Measure_Ch2 = True

    Temp_Start = 2.7
    Temp_End = 2.7
    Temp_Step = 0#

    IP_Field_Start = 0#
    IP_Field_End = 0#
    IP_Field_Step = 0#

    ' =========================================================
    ' Instrument and file configuration - edit these values
    ' =========================================================
    Dim K2600_resourceName As String
    Dim K2450_resourceName As String
    Dim Hallbar As String
    Dim BaseFolder As String
    Dim Append_Output As Boolean

    K2600_resourceName = "GPIB0::26::INSTR"
    K2450_resourceName = "GPIB0::18::INSTR"
    Hallbar = "wire2"
    BaseFolder = "C:\QdDynacool\Data\ETO\"
    Append_Output = False

    ' =========================================================
    ' Do not edit below this line
    ' =========================================================

    Debug.Clear

    MV_Log "[MACRO][BSWEEP] Starting Helmholtz B-sweep loop"
    MV_Log "[MACRO][BSWEEP] Parameters loaded from Macro_Helmholtz_BSweep.bas"

    Call fn_IP_Loop_Helm_Loop_Bsweep( _
        Helm_Field_Start, _
        Helm_Field_End, _
        Helm_Field_Step, _
        IV_Current_mA, _
        IV_Frequency_Hz, _
        IV_Averaging, _
        IV_Gain_Code, _
        IV_Sweep_Code, _
        Wait_For_Stable_s, _
        Helm_Field_Rate, _
        Measure_Ch1, _
        Measure_Ch2, _
        Temp_Start, _
        Temp_End, _
        Temp_Step, _
        IP_Field_Start, _
        IP_Field_End, _
        IP_Field_Step, _
        K2600_resourceName, _
        K2450_resourceName, _
        Hallbar, _
        BaseFolder, _
        Append_Output)

    MV_Log "[MACRO][BSWEEP] Completed Helmholtz B-sweep loop"
End Sub

'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Instruments\MV_K2450_LiveLog.bas"
'#Uses "..\Analysis\MV_IV_PostAnalysis.bas"
'#Uses "..\Analysis\MV_RTPostAnalysis.bas"
'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_GpibIO.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Runners\MV_PPMSBSweep_HelmIPLoop.bas"
Option Explicit

Public Sub Macro_Run_PPMS_BSweep_HelmIP()
    ' =========================================================
    ' Main sweep configuration (PPMS out-of-plane)
    ' =========================================================
    Dim OOP_Field_Start As Double  ' PPMS sweep start (Oe)
    Dim OOP_Field_End As Double    ' PPMS sweep end (Oe)
    Dim OOP_Field_Step As Double   ' PPMS sweep step size (Oe)
    Dim OOP_Field_Rate As Double   ' PPMS sweep ramp rate (Oe/s)

    ' =========================================================
    ' In-plane bias configuration (Helmholtz)
    ' =========================================================
    Dim IP_Helm_Start As Double    ' Helmholtz in-plane loop start (Oe)
    Dim IP_Helm_End As Double      ' Helmholtz in-plane loop end (Oe)
    Dim IP_Helm_Step As Double     ' Helmholtz in-plane step size (Oe); 0 if start=end
    Dim IP_Helm_Rate As Double     ' Helmholtz ramp rate (Oe/s)

    ' =========================================================
    ' ETO IV configuration
    ' =========================================================
    Dim IV_Current_mA As Double     ' ETO IV peak current (mA)
    Dim IV_Frequency_Hz As Double   ' ETO IV excitation frequency (Hz)
                                     '  Options: 0.3051758 | 1.017253 | 1.525879 | 3.051758
                                     '           6.103516  | 12.20704 | 24.41407 | 48.82813 | 97.65625
    Dim IV_Averaging As Long        ' ETO IV averaging points
    Dim IV_Gain_Code As String      ' ETO IV gain (3 numbers, space-separated):
                                     '  "3 2 1"=44uV   "3 2 0"=130uV  "3 1 1"=440uV  "3 1 0"=1.3mV
                                     '  "3 0 1"=4.4mV  "3 0 0"=13mV   "1 2 0"=40mV   "1 1 1"=130mV
                                     '  "1 1 0"=0.4V   "1 0 1"=1.3V   "1 0 0"=4V
    Dim IV_Sweep_Code As String     ' ETO IV sweep waveform (3 numbers, space-separated):
                                     '  "0 0 0" = 0->Max->Min->0  (full bipolar, default)
                                     '  "1 0 0" = 0->Min->Max->0
                                     '  "2 0 0" = 0->Max->0       (positive only)
                                     '  "3 0 0" = 0->Min->0       (negative only)

    Dim Wait_For_Stable_s As Long     ' PPMS/background stabilization timeout (s)
    Dim IP_Field_Stable_Wait_s As Long ' Extra wait after each Helm IP set (s)

    ' Ch2 is always measured. Ch1 is optional Hall monitor.
    Dim Measure_Ch1_Hall As Boolean ' False=measure Ch2 only, True=measure Ch1 and Ch2

    ' =========================================================
    ' Temperature loop
    ' =========================================================
    Dim Temp_Start As Double        ' Temperature loop start (K)
    Dim Temp_End As Double          ' Temperature loop end (K)
    Dim Temp_Step As Double         ' Temperature loop step size (K); 0 if start=end

    ' =========================================================
    ' Background mini-sweep options
    ' =========================================================
    Dim Enable_Background_Pre As Boolean  ' True=run PRE background if no reusable POST
    Dim Enable_Background_Post As Boolean ' True=run POST background (reused for next temperature PRE)
    Dim Bg_Temperature_K As Double        ' Background measurement temperature (K)
    Dim Bg_Field_Start As Double          ' Background short-range sweep start (Oe)
    Dim Bg_Field_End As Double            ' Background short-range sweep end (Oe)
    Dim Bg_Field_Step As Double           ' Background sweep step size (Oe)
    Dim Bg_Field_Rate As Double           ' Background sweep ramp rate (Oe/s)
    Dim Bg_MinPointsForFit As Long        ' Minimum points for polynomial fit; must be >= 5

    ' =========================================================
    ' Instrument and file configuration
    ' =========================================================
    Dim K2600_resourceName As String      ' K2600 VISA resource
    Dim BaseFolder As String              ' Output folder for ETODF/Merged/Background files

    ' =========================================================
    ' Preset values (edit here for your run)
    ' =========================================================

    ' Main PPMS OOP sweep
    OOP_Field_Start = -150#
    OOP_Field_End = 150#
    OOP_Field_Step = 2#
    OOP_Field_Rate = 3#

    ' Helmholtz in-plane bias loop
    IP_Helm_Start = 0#
    IP_Helm_End = 0#
    IP_Helm_Step = 0#
    IP_Helm_Rate = 10#

    ' ETO IV setup
    IV_Current_mA = 0.0005
    IV_Frequency_Hz = 12.20704
    IV_Averaging = 60
    IV_Gain_Code = "3 2 1"
    IV_Sweep_Code = "0 0 0"

    ' Stabilization and channels
    Wait_For_Stable_s = 300
    IP_Field_Stable_Wait_s = 1800
    Measure_Ch1_Hall = False

    ' Temperature loop
    Temp_Start = 2.49
    Temp_End = 2.5
    Temp_Step = 0.01

    ' Background PRE/POST mini-sweeps
    Enable_Background_Pre = True
    Enable_Background_Post = True
    Bg_Temperature_K = 2.7
    Bg_Field_Start = -50#
    Bg_Field_End = 50#
    Bg_Field_Step = 2#
    Bg_Field_Rate = 3#
    Bg_MinPointsForFit = 9

    ' Instrument routing and output directory
    K2600_resourceName = MV_K2600_RESOURCE
    BaseFolder = "C:\QdDynacool\Data\ETO\"

    Debug.Clear

    MV_Log "[MACRO][PPMS-BSWEEP-HELM-IP] Starting"
    MV_Log "[MACRO][PPMS-BSWEEP-HELM-IP] Ch2 is forced ON; Ch1 Hall monitor is optional"

    ' Execute configured run
    Call fn_PPMS_BSweep_Helm_IP( _
        OOP_Field_Start, _
        OOP_Field_End, _
        OOP_Field_Step, _
        OOP_Field_Rate, _
        IP_Helm_Start, _
        IP_Helm_End, _
        IP_Helm_Step, _
        IP_Helm_Rate, _
        IV_Current_mA, _
        IV_Frequency_Hz, _
        IV_Averaging, _
        IV_Gain_Code, _
        IV_Sweep_Code, _
        Wait_For_Stable_s, _
        IP_Field_Stable_Wait_s, _
        Measure_Ch1_Hall, _
        Temp_Start, _
        Temp_End, _
        Temp_Step, _
        Enable_Background_Pre, _
        Enable_Background_Post, _
        Bg_Temperature_K, _
        Bg_Field_Start, _
        Bg_Field_End, _
        Bg_Field_Step, _
        Bg_Field_Rate, _
        Bg_MinPointsForFit, _
        K2600_resourceName, _
        BaseFolder) 'mvseq:Macro_PPMS_BSweep_HelmIP.seq(1)>0001 Run PPMS BSweep Helm IP

    MV_Log "[MACRO][PPMS-BSWEEP-HELM-IP] Completed"
End Sub

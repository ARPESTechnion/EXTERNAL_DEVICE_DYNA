'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Instruments\MV_K2450_Hall.bas"
'#Uses "..\Instruments\MV_K2450_General.bas"
'#Uses "..\Instruments\MV_K2450_LiveLog.bas"
'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_GpibIO.bas"

Option Explicit

' FTC (Fast Temperature Cycle) sweep configuration.
' Set these before calling Macro_Run_K2450_IV_Fast_TempCycle(),
' or edit the defaults inside the macro body.
Public K2450RW_FTC_TempList_K_Csv As String
Public K2450RW_FTC_MaxCurrentList_mA_Csv As String
Public K2450RW_FTC_PointsPerIV_List_Csv As String
Public K2450RW_FTC_HighTemp_K As Double
Public K2450RW_FTC_TempRampRate_Kmin As Double
Public K2450RW_FTC_TempSetMode As Integer
Public K2450RW_FTC_TempStableTimeout_s As Double
Public K2450RW_FTC_TempSettleDelay_s As Double
Public K2450RW_FTC_RepeatsPerTemp As Integer
Public K2450RW_FTC_SourceSpec As String
Public K2450RW_FTC_Start_mA As Double
Public K2450RW_FTC_MinStep_uA As Double
Public K2450RW_FTC_Nplc As Double
Public K2450RW_FTC_AvgCount As Integer
Public K2450RW_FTC_SweepSettle_s As Double
Public K2450RW_FTC_RampRate_mA_per_s As Double
Public K2450RW_FTC_Compliance_V As Double
Public K2450RW_FTC_Use4Wire As Boolean
Public K2450RW_FTC_AutoRange As Boolean
Public K2450RW_FTC_TbRefresh_s As Double
Public K2450RW_FTC_DirectionFirst As Integer
Public K2450RW_FTC_DirectionSecond As Integer
Public K2450RW_FTC_ResourceName As String
Public K2450RW_FTC_SampleChannelTag As String
Public K2450RW_FTC_BaseFolder As String
Public K2450RW_FTC_RunPrefix As String
Public K2450RW_FTC_DebugGPIB As Boolean

Public Sub Macro_Run_K2450_IV_Fast_TempCycle()
    ' =========================================================
    ' Per-temperature paired lists (same order and same length)
    ' =========================================================
    Dim TempList_K_Csv As String
    Dim MaxCurrentList_mA_Csv As String
    Dim PointsPerIV_List_Csv As String

    TempList_K_Csv = "2.67, 2.665, 2.66, 2.655, 2.65, 2.645, 2.64, 2.635, 2.63, 2.625"
    MaxCurrentList_mA_Csv = "0.065, 0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.1, 0.105, 0.11"
    PointsPerIV_List_Csv = "1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024"

    ' =========================================================
    ' Temperature-cycle settings
    ' HighTemp_K: return temperature between IV repetitions.
    ' TempRampRate_Kmin: temperature ramp speed in K/min.
    ' TempSetMode: MultiVu temperature mode (0 = fast settle mode used elsewhere in project).
    ' TempStableTimeout_s: wait time after temperature is stable.
    ' RepeatsPerTemp: number of IV sweeps at each temperature point.
    ' =========================================================
    Dim HighTemp_K As Double
    Dim TempRampRate_Kmin As Double
    Dim TempSetMode As Integer
    Dim TempStableTimeout_s As Double
    Dim RepeatsPerTemp As Integer

    HighTemp_K = 5#
    TempRampRate_Kmin = 10#
    TempSetMode = 0
    TempStableTimeout_s = 60#
    RepeatsPerTemp = 2

    ' =========================================================
    ' Shared K2450 fast-IV settings
    ' SourceSpec: "mA" or "A" for current sourcing, "V" for voltage sourcing.
    ' Start_mA/MinStep_uA: start value and minimum step used to hit target points.
    ' Nplc/AvgCount/SweepSettle_s: K2450 measurement timing/averaging settings.
    ' RampRate_mA_per_s: optional ramp rate to start point (0 disables ramping).
    ' Compliance_V: voltage compliance limit during current-source sweep.
    ' Use4Wire/AutoRange: measurement wiring and range behavior.
    ' TbRefresh_s: live table refresh period during fast sweep logging.
    ' Direction modes used by this fast temp-cycle macro:
    '   0 = MAXFIRST: start -> +Imax -> -Imax -> start
    '   1 = MINFIRST: start -> -Imax -> +Imax -> start
    ' DirectionFirst/DirectionSecond alternate by repeat index:
    '   odd repeats use DirectionFirst, even repeats use DirectionSecond.
    ' =========================================================
    Dim SourceSpec As String
    Dim Start_mA As Double
    Dim MinStep_uA As Double
    Dim Nplc As Double
    Dim AvgCount As Integer
    Dim SweepSettle_s As Double
    Dim RampRate_mA_per_s As Double
    Dim Compliance_V As Double
    Dim Use4Wire As Boolean
    Dim AutoRange As Boolean
    Dim TbRefresh_s As Double
    Dim DirectionFirst As Integer
    Dim DirectionSecond As Integer

    SourceSpec = "mA"
    Start_mA = 0#
    MinStep_uA = 0.01
    Nplc = 1#
    AvgCount = 1
    SweepSettle_s = 0.01#
    RampRate_mA_per_s = 0#
    Compliance_V = 20#
    Use4Wire = True
    AutoRange = True
    TbRefresh_s = 1#
    DirectionFirst = 1
    DirectionSecond = 0

    ' =========================================================
    ' File and instrument settings
    ' =========================================================
    Dim ResourceName As String
    Dim SampleChannelTag As String
    Dim BaseFolder As String
    Dim RunPrefix As String
    Dim DebugGPIB As Boolean

    ResourceName = "GPIB0::18::INSTR"
    SampleChannelTag = "Ch2"
    BaseFolder = "C:\QdDynacool\Data\ETO\"
    RunPrefix = "K2450_fast_tempcycle"
    DebugGPIB = False

    Debug.Clear
    K2450RW_FTC_TempList_K_Csv = TempList_K_Csv
    K2450RW_FTC_MaxCurrentList_mA_Csv = MaxCurrentList_mA_Csv
    K2450RW_FTC_PointsPerIV_List_Csv = PointsPerIV_List_Csv
    K2450RW_FTC_HighTemp_K = HighTemp_K
    K2450RW_FTC_TempRampRate_Kmin = TempRampRate_Kmin
    K2450RW_FTC_TempSetMode = TempSetMode
    K2450RW_FTC_TempStableTimeout_s = TempStableTimeout_s
    K2450RW_FTC_TempSettleDelay_s = 0#
    K2450RW_FTC_RepeatsPerTemp = RepeatsPerTemp
    K2450RW_FTC_SourceSpec = SourceSpec
    K2450RW_FTC_Start_mA = Start_mA
    K2450RW_FTC_MinStep_uA = MinStep_uA
    K2450RW_FTC_Nplc = Nplc
    K2450RW_FTC_AvgCount = AvgCount
    K2450RW_FTC_SweepSettle_s = SweepSettle_s
    K2450RW_FTC_RampRate_mA_per_s = RampRate_mA_per_s
    K2450RW_FTC_Compliance_V = Compliance_V
    K2450RW_FTC_Use4Wire = Use4Wire
    K2450RW_FTC_AutoRange = AutoRange
    K2450RW_FTC_TbRefresh_s = TbRefresh_s
    K2450RW_FTC_DirectionFirst = DirectionFirst
    K2450RW_FTC_DirectionSecond = DirectionSecond
    K2450RW_FTC_ResourceName = ResourceName
    K2450RW_FTC_SampleChannelTag = SampleChannelTag
    K2450RW_FTC_BaseFolder = BaseFolder
    K2450RW_FTC_RunPrefix = RunPrefix
    K2450RW_FTC_DebugGPIB = DebugGPIB

    Call FTC_RunConfigured
End Sub

Sub Main()
    Call Macro_Run_K2450_IV_Fast_TempCycle
End Sub

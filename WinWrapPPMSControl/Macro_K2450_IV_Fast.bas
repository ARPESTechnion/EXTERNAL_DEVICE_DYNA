Option Explicit

Public Sub Macro_Run_K2450_IV_Fast()
    ' =========================================================
    ' Measurement Configuration - edit these values
    ' =========================================================
    Dim IvDirection As Integer   ' Sweep direction mode:
                              '  K2450_IV_DIR_START_MAX_MIN_START (0->Max->Min->0)
                              '  K2450_IV_DIR_START_MIN_MAX_START (0->Min->Max->0)
                              '  K2450_IV_DIR_START_MAX_START     (0->Max->0)
                              '  K2450_IV_DIR_START_MIN_START     (0->Min->0)
    Dim Start_A As Double      ' Sweep start value (A)
    Dim Max_A As Double        ' Sweep max value (A)
    Dim Min_A As Double        ' Sweep min value (A)
    Dim Step_A As Double       ' Sweep step size (A)
    Dim Settle_s As Double     ' Delay before each point (s)
    Dim Nplc As Double         ' Integration time in PLC
    Dim AvgCount As Integer    ' Average count per point
    Dim RampRatePerS As Double ' Ramp rate to start value (A/s), 0 for immediate
    Dim Compliance_V As Double ' Compliance limit (V)
    Dim Use4Wire As Boolean    ' True = 4-wire sense
    Dim AutoRange As Boolean   ' True = auto-range

    IvDirection = K2450_IV_DIR_START_MAX_MIN_START
    Start_A = 0#
    Max_A = 0.001
    Min_A = -0.001
    Step_A = 0.000004
    Settle_s = 0#
    Nplc = 1#
    AvgCount = 1
    RampRatePerS = 0#
    Compliance_V = 20#
    Use4Wire = True
    AutoRange = True

    ' =========================================================
    ' Run labeling and file configuration - edit these values
    ' =========================================================
    Dim SourceSpec As String        ' "A" for current-source sweep
    Dim SampleChannelTag As String  ' Channel tag written to output log
    Dim ResourceName As String      ' K2450 VISA resource
    Dim DataPath As String          ' Output .dat path
    Dim RunTitle As String          ' Title/comment for metadata
    Dim RunComment As String        ' Additional comment text
    Dim TbRefresh_s As Double       ' Live UI/log refresh period (s)
    Dim DebugGPIB As Boolean        ' True prints low-level GPIB traces

    SourceSpec = "A"
    SampleChannelTag = "Ch2"
    ResourceName = MV_K2450_RESOURCE
    DataPath = "C:\QdDynacool\Data\ETO\Test_IV_fast.dat"
    RunTitle = "K2450 IV sweep fast CH2"
    RunComment = "fast sweep"
    TbRefresh_s = 1#
    DebugGPIB = False

    ' =========================================================
    ' Do not edit below this line
    ' =========================================================
    Dim ok As Boolean
    Dim runStartDate As Date
    Dim runStartTimer As Double
    Dim elapsed_s As Double

    Debug.Clear
    runStartDate = Date
    runStartTimer = Timer

    Call MV_SetDebugMode(DebugGPIB)

    ok = Run_K2450_IV_SweepFast(DataPath, _
                                IvDirection, _
                                Start_A, _
                                Max_A, _
                                Min_A, _
                                Step_A, _
                                SourceSpec, _
                                Settle_s, _
                                Nplc, _
                                AvgCount, _
                                RampRatePerS, _
                                RunTitle, _
                                Compliance_V, _
                                SampleChannelTag, _
                                Use4Wire, _
                                AutoRange, _
                                ResourceName, _
                                RunComment, _
                                TbRefresh_s)

    elapsed_s = (CDbl(Date - runStartDate) * 86400#) + (Timer - runStartTimer)
    If elapsed_s < 0# Then elapsed_s = 0#
    MV_Log "[MACRO][K2450-FAST] elapsed_s=" & Format$(elapsed_s, "0.000")

    If Not ok Then
        MV_Log "[MACRO][K2450-FAST] FAIL: " & MV_LastError
        Call MV_SetDebugMode(False)
        Exit Sub
    End If

    MV_Log "[MACRO][K2450-FAST] OK: " & DataPath
    Call MV_SetDebugMode(False)
End Sub

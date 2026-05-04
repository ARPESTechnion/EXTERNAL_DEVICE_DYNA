Option Explicit

' =============================
' Global constants and settings
' =============================
Public Const MV_MAPPING_VERSION As String = "v1"

' Helmholtz calibration and safety
Public Const MV_HELM_G_PER_A_TOTAL As Double = 341.71
Public Const MV_HELM_MAX_TOTAL_CURRENT_A As Double = 3#
Public Const MV_HELM_DEFAULT_RAMP_RATE_mA_PER_S As Double = 100#
' v3 limit is 100 mA/s; convert to G/s through total Helmholtz gain.
Public Const MV_HELM_MAX_RATE_G_PER_S As Double = MV_HELM_DEFAULT_RAMP_RATE_mA_PER_S * 0.001 * MV_HELM_G_PER_A_TOTAL
Public Const MV_HELM_MIN_COMPLIANCE_V As Double = 0#
Public Const MV_HELM_MAX_COMPLIANCE_V As Double = 20#
Public Const MV_HELM_MIN_NPLC As Double = 0.01
Public Const MV_HELM_MAX_NPLC As Double = 20#

' Defaults
Public Const MV_DEFAULT_HELM_COMPLIANCE_V As Double = 3#
Public Const MV_DEFAULT_HELM_NPLC As Double = 1#
Public Const MV_DEFAULT_HALL_CURRENT_mA As Double = 2#
Public Const MV_DEFAULT_HALL_NPLC As Double = 5#
Public Const MV_DEFAULT_HALL_COMPLIANCE_V As Double = 2#
Public Const MV_DEFAULT_HALL_FILTER_COUNT As Integer = 10
Public Const MV_DEFAULT_HALL_OFFSET_V As Double = 0#
Public Const MV_DEFAULT_STABLE_COUNT As Integer = 2
Public Const MV_DEFAULT_CURRENT_TOL_A As Double = 0.001
Public Const MV_DEFAULT_POLL_S As Double = 0.25

' Hall limits

Public Const MV_HALL_MIN_CURRENT_mA As Double = 0#
Public Const MV_HALL_MAX_CURRENT_mA As Double = 105#
Public Const MV_HALL_MIN_NPLC As Double = 0.01
Public Const MV_HALL_MAX_NPLC As Double = 20#
Public Const MV_HALL_MIN_COMPLIANCE_V As Double = 0#
Public Const MV_HALL_MAX_COMPLIANCE_V As Double = 210#
Public Const MV_HALL_MIN_FILTER_COUNT As Integer = 1
Public Const MV_HALL_MAX_FILTER_COUNT As Integer = 100
Public Const MV_HALL_MIN_OFFSET_V As Double = -5#
Public Const MV_HALL_MAX_OFFSET_V As Double = 5#
Public Const MV_HALL_MIN_ABS_V_PER_G As Double = 0.0000001

' Hall presets (V/G) from v3 hall_tab.py
Public Const MV_HALL_V_PER_G_WIRE_1 As Double = 0.000021508
Public Const MV_HALL_V_PER_G_WIRE_2 As Double = 0.00002154
Public Const MV_HALL_V_PER_G_BOND_1 As Double = -0.000019057
Public Const MV_HALL_V_PER_G_BOND_2 As Double = -0.000019647

' VISA resource defaults
'Public Const MV_K2600_RESOURCE As String = "USB0::0x05E6::0x2614::4083836::INSTR"
Public Const MV_K2600_RESOURCE As String = "GPIB0::26::INSTR"
Public Const MV_K2450_RESOURCE As String = "GPIB0::18::INSTR"
Public Const MV_K7001_RESOURCE As String = "GPIB0::7::INSTR"
Public Const MV_GPIB_RETRY_COUNT As Integer = 3
Public Const MV_GPIB_TERM_CHAR As Integer = 10
Public Const MV_GPIB_EOI As Boolean = True
Public Const MV_GPIB_TIMEOUT_S As Double = 5#

' Built-in MultiVu.GPIB device keys (empty means disconnected).
Public MV_K2600_Device As String
Public MV_K2450_Device As String
Public MV_K7001_Device As String
Public MV_GPIBDebug As Boolean

' Session-level paths/state
Public MV_RunName As String
Public MV_HelmLogPath As String
Public MV_LastError As String
Public MV_SessionStartTimer As Double
Public MV_SessionStartDate As Date

' Runtime parameters (editable from scripts)
Public MV_HelmCompliance_V As Double
Public MV_HelmNPLC As Double
Public MV_HallCurrent_mA As Double
Public MV_HallCompliance_V As Double
Public MV_HallNPLC As Double
Public MV_HallAvgFilter As Integer
Public MV_HallVPerG As Double
Public MV_HallVOffset As Double
Public MV_PostAnalysisStepIndex As Long

' Mapping slots (frozen v1)
Public Const MV_CH_TARGET_FIELD As Integer = 1
Public Const MV_CH_TOTAL_CURRENT As Integer = 2
Public Const MV_CH_COMPLIANCE As Integer = 3
Public Const MV_CH_HALL_CURRENT As Integer = 4
Public Const MV_CH_HALL_COMPLIANCE As Integer = 5
Public Const MV_CH_HALL_VOLTAGE As Integer = 6
Public Const MV_CH_HALL_FIELD As Integer = 7
Public Const MV_CH_HALL_NPLC As Integer = 8
Public Const MV_CH_HALL_FILTER As Integer = 9
Public Const MV_CH_CURR_A As Integer = 10
Public Const MV_CH_CURR_B As Integer = 11
Public Const MV_CH_EXT_STATUS As Integer = 12

Public Sub MV_ResetDefaults()
    MV_HelmCompliance_V = MV_DEFAULT_HELM_COMPLIANCE_V
    MV_HelmNPLC = MV_DEFAULT_HELM_NPLC

    MV_HallCurrent_mA = MV_DEFAULT_HALL_CURRENT_mA
    MV_HallCompliance_V = MV_DEFAULT_HALL_COMPLIANCE_V
    MV_HallNPLC = MV_DEFAULT_HALL_NPLC
    MV_HallAvgFilter = MV_DEFAULT_HALL_FILTER_COUNT
    MV_HallVPerG = MV_HALL_V_PER_G_WIRE_1
    MV_HallVOffset = MV_DEFAULT_HALL_OFFSET_V
    MV_PostAnalysisStepIndex = 0

    MV_LastError = ""
End Sub

Public Sub MV_StartSessionClock()
    MV_SessionStartDate = Date
    MV_SessionStartTimer = Timer
End Sub

Public Function MV_GetSessionElapsedSeconds() As Double
    Dim elapsed As Double
    elapsed = (CDbl(Date - MV_SessionStartDate) * 86400#) + (Timer - MV_SessionStartTimer)
    If elapsed < 0# Then
        ' Defensive clamp for rare system clock adjustments.
        elapsed = 0#
    End If
    MV_GetSessionElapsedSeconds = elapsed
End Function

Public Function Hall_ApplyPreset(ByVal presetName As String) As Boolean
    Dim key As String
    key = LCase$(Trim$(presetName))

    Select Case key
        Case "wire hall bar 1", "wire1", "wire_1"
            MV_HallVPerG = MV_HALL_V_PER_G_WIRE_1
        Case "wire hall bar 2", "wire2", "wire_2"
            MV_HallVPerG = MV_HALL_V_PER_G_WIRE_2
        Case "bond hall bar 1", "bond1", "bond_1"
            MV_HallVPerG = MV_HALL_V_PER_G_BOND_1
        Case "bond hall bar 2", "bond2", "bond_2"
            MV_HallVPerG = MV_HALL_V_PER_G_BOND_2
        Case Else
            MV_SetError "Unknown Hall preset: " & presetName
            Hall_ApplyPreset = False
            Exit Function
    End Select

    Hall_ApplyPreset = True
End Function

Public Sub MV_SetError(ByVal msg As String)
    MV_LastError = msg
    MV_Log "[MV][ERROR] " & msg
End Sub

Public Sub MV_ClearError()
    MV_LastError = ""
End Sub

Public Sub MV_Log(ByVal msg As String)
    Debug.Print msg
End Sub

Public Function MV_IsFinite(ByVal x As Double) As Boolean
    MV_IsFinite = (Abs(x) < 1E90)
End Function

Public Sub MV_WaitSeconds(ByVal seconds As Double)
    Dim t0 As Double
    t0 = Timer
    Do While (Timer - t0) < seconds
        DoEvents
    Loop
End Sub
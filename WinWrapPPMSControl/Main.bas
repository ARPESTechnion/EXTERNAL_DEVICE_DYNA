 
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_HelmholtzLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2600_Helmholtz.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_Hall.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_General.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K2450_LiveLog.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_K7001.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_IV_PostAnalysis.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_RTPostAnalysis.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_RunWrappers.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_GpibIO.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Sub fn_IP_Loop_Helm_Loop_Bsweep().vb"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_K2450_IV_Slow.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_K2450_IV_Fast.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_K2450_IV_Fast_TempCycle.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_Helmholtz_BSweep.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_K2600_OutputOff_Check.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\Macro_Hall_ETO_Switch_TempField.bas"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_TestFunctions_Legacy.bas"  ' Optional: enable legacy tests/utilities

Option Explicit

Private Sub PrintStartupDefaults()
    Dim maxFieldG As Double
    Dim maxCurrentPerChA As Double
    maxFieldG = MV_HELM_G_PER_A_TOTAL * MV_HELM_MAX_TOTAL_CURRENT_A
    maxCurrentPerChA = MV_HELM_MAX_TOTAL_CURRENT_A / 2#

    MV_Log "========== WinWrapPPMSControl Defaults =========="
    MV_Log "mapping_version = " & MV_MAPPING_VERSION
    MV_Log ""
    MV_Log "Helmholtz"
    MV_Log "  G_per_A_total = " & CStr(MV_HELM_G_PER_A_TOTAL)
    MV_Log "  max_current_per_ch_A = " & CStr(maxCurrentPerChA)
    MV_Log "  max_total_current_A = " & CStr(MV_HELM_MAX_TOTAL_CURRENT_A)
    MV_Log "  max_field_G = " & CStr(maxFieldG)
    MV_Log "  max_rate_G_per_s = " & CStr(MV_HELM_MAX_RATE_G_PER_S)
    MV_Log "  default_compliance_V = " & CStr(MV_HelmCompliance_V)
    MV_Log "  default_nplc = " & CStr(MV_HelmNPLC)
    MV_Log ""
    MV_Log "Hall (default preset: Wire Hall Bar 1)"
    MV_Log "  hall_current_mA = " & CStr(MV_HallCurrent_mA)
    MV_Log "  hall_compliance_V = " & CStr(MV_HallCompliance_V)
    MV_Log "  hall_nplc = " & CStr(MV_HallNPLC)
    MV_Log "  hall_filter_count = " & CStr(MV_HallAvgFilter)
    MV_Log "  hall_v_per_g = " & CStr(MV_HallVPerG)
    MV_Log "  hall_offset_V = " & CStr(MV_HallVOffset)
    If Abs(MV_HallVPerG) > MV_HALL_MIN_ABS_V_PER_G Then
        MV_Log "  hall_g_per_v = " & CStr(1# / MV_HallVPerG)
    End If
    MV_Log "=================================================="
End Sub

Private Sub PrintFunctionCatalog()
    MV_Log "========== WinWrapPPMSControl Public API =========="
    MV_Log "Session"
    MV_Log "  MV_InitSession(runName, helmholtzLogPath)"
    MV_Log "  MV_InitSessionWithPostAnalysis(runName, helmholtzLogPath, mergedPostAnalysisPath)"
    MV_Log "  MV_CloseSession()"
    MV_Log ""
    MV_Log "Helmholtz (K2600)"
    MV_Log "  K2600_Connect([resource]) / K2600_Disconnect()"
    MV_Log "  Helm_ConfigSource(compliance_V, nplc)"
    MV_Log "  Helm_SetField(helmholtzField_Oe, rate_G_per_s)"
    MV_Log "  Helm_ValidateHelmholtzField(helmholtzField_Oe, rate_G_per_s)"
    MV_Log "  Helm_WaitStable(timeout_s, [delay_s])"
    MV_Log "  Helm_MeasureResistances_Ohm(nplc, resistanceA_Ohm, resistanceB_Ohm)"
    MV_Log "  Helm_MeasureAndLog()"
    MV_Log ""
    MV_Log "Hall (K2450)"
    MV_Log "  K2450_Connect([resource]) / K2450_Disconnect()"
    MV_Log "  Hall_ApplyPreset(name), Hall_SetCalibration(vPerG, vOffset_V)"
    MV_Log "  Hall_Configure(current_mA, compliance_V, nplc, avgFilter)"
    MV_Log "  Hall_MeasureVoltage_V(), Hall_ComputeField_Oe(voltage_V)"
    MV_Log "  Hall_MeasureAndLog(), Hall_CalibrateOffset_V()"
    MV_Log "  K2450_ConfigCurrentSource(source_A, compliance_V, nplc, avgCount, [use4Wire], [autoRange])"
    MV_Log "  K2450_ConfigVoltageSource(source_V, compliance_A, nplc, avgCount, [use4Wire], [autoRange])"
    MV_Log "  K2450_MeasureVoltage_V([Ch], [settle_s]), K2450_MeasureCurrent_A([Ch], [settle_s]), K2450_MeasureResistance_Ohm([Ch], [settle_s])"
    MV_Log "  K2450_IV_Run(Ch, sourceMode, startVal, maxVal, minVal, stepVal, directionMode, settle_s, [rampToStart], [rampRatePerS], [comment])"
    MV_Log "  Run_K2450_IV_Sweep(datPath, directionMode, startVal, maxVal, minVal, stepVal, sourceSpec, settle_s, nplc, avgCount, rampRatePerS, ...)"
    MV_Log "  Run_K2450_IV_SweepFast(datPath, directionMode, startVal, maxVal, minVal, stepVal, sourceSpec, settle_s, nplc, avgCount, rampRatePerS, ...)"
    MV_Log "  K2450_LogInit(datPath, runTitle), K2450_LogPoint([Ch], [comment]), K2450_LogClose()"
    MV_Log ""
    MV_Log "Switch Matrix (K7001 + 7012-S 4x10)"
    MV_Log "  K7001_Connect([resource]) / K7001_Disconnect()"
    MV_Log "  K7001_OpenAll(), K7001_CloseChannel(name)"
    MV_Log "  K7001_DefineChannel(name, iPlusOut, vPlusOut, vMinusOut, iMinusOut)"
    MV_Log "  K7001_LoadDefaultMappings(), K7001_ClearMappings(), K7001_PrintMappings()"
    MV_Log ""
    MV_Log "DynaCool + Data"
    MV_Log "  DYNA_GetTemperature_K(), DYNA_GetField_Oe()"
    MV_Log "  DYNA_SetField(field_Oe, rate_Oe_s), DYNA_SetFieldAndWait(field_Oe, rate_Oe_s, timeout_s)"
    MV_Log "  DYNA_SetTempAndWait(targetK, rateKmin, mode, timeout_s), DYNA_WaitForTempFieldStable(timeout_s)"
    MV_Log "  Data_AddComment(text)"
    MV_Log ""
    MV_Log "GPIB"
    MV_Log "  MV_SetDebugMode(True/False)  -- toggles [GPIB][W/Q/R] trace output"
    MV_Log ""
    MV_Log "Run wrappers"
    MV_Log "  Full_MeasureAndLog([tbm_s])"
    MV_Log "  Run_K2450_IV_Live(datPath, runTitle, Ch, sourceMode, startVal, maxVal, minVal, stepVal, directionMode, settle_s, ...)"
    MV_Log "  Run_IVSweepFastTest()"
    MV_Log "  Run_K2600_ZeroOutputCheck()"
    MV_Log "  Run_K2450_IV_SweepFast(datPath, directionMode, startVal, maxVal, minVal, stepVal, sourceSpec, settle_s, nplc, avgCount, rampRatePerS, ...)"
    MV_Log ""
    MV_Log "Post analysis"
    MV_Log "  Merged_InitPostAnalysisLog(filePath), Merged_ClosePostAnalysisLog()"
    MV_Log "  PostAnalysis_AppendMergedRow(etoDataPath, stepIndex, hallMeasured, measureCh1, measureCh2, ...)"
    MV_Log "  PostAnalysis_AppendAfterETO(etoDataPath, hallMeasured, measureCh1, measureCh2, ...)"
    MV_Log "  PostAnalysis_ReplayOldETOScan(etoDataPath, loopCount, helmStart_Oe, helmStep_Oe, ..., dualBlockOrderCh1First)"
    MV_Log "===================================================="
End Sub

' ---------------------------------------------------------------------------
' Main: default entry point when MultiVu runs the script.
' Use this file as the run menu and quick-start guide.
' ---------------------------------------------------------------------------
Sub Main()
    Debug.Clear

    Call PrintStartupDefaults()
    Call PrintFunctionCatalog()

    MV_Log "[MAIN] ===== WinWrapPPMSControl Run Menu ====="
    MV_Log "[MAIN]   Macro_Run_K2450_IV_Slow"
    MV_Log "[MAIN]     File: Macro_K2450_IV_Slow.bas"
    MV_Log "[MAIN]     Edit: start/max/min/step, NPLC, avg, compliance, output path"
    MV_Log "[MAIN]   Macro_Run_K2450_IV_Fast"
    MV_Log "[MAIN]     File: Macro_K2450_IV_Fast.bas"
    MV_Log "[MAIN]     Edit: start/max/min/step, NPLC, avg, tb refresh, output path"
    MV_Log "[MAIN]   Macro_Run_K2450_IV_Fast_TempCycle"
    MV_Log "[MAIN]     File: Macro_K2450_IV_Fast_TempCycle.bas"
    MV_Log "[MAIN]     Edit: temp list, settle delay, high temp, max-current list"
    MV_Log "[MAIN]   Macro_Run_Helmholtz_BSweep"
    MV_Log "[MAIN]     File: Macro_Helmholtz_BSweep.bas"
    MV_Log "[MAIN]     Edit: B sweep range/rate, temp loop, in-plane field loop, ETO IV params"
    MV_Log "[MAIN]   Macro_Run_K2600_OutputOff_Check"
    MV_Log "[MAIN]     File: Macro_K2600_OutputOff_Check.bas"
    MV_Log "[MAIN]     Edit: resource name and zero-current tolerance"
    MV_Log "[MAIN]   Macro_Run_Hall_ETO_Switch_TempField"
    MV_Log "[MAIN]     File: Macro_Hall_ETO_Switch_TempField.bas"
    MV_Log "[MAIN]     Edit: Temp/Field loops, ETOR params, switch mappings, output path"
    MV_Log "[MAIN] ========================================"

    ' -----------------------------------------------------------------------
    ' ONE-CLICK RUN OPTION
    ' Uncomment exactly one Call below to make it the default Main action.
    ' Keep all others commented.
    ' -----------------------------------------------------------------------
    ' Call Macro_Run_K2450_IV_Slow()
    ' Call Macro_Run_K2450_IV_Fast()
    ' Call Macro_Run_K2450_IV_Fast_TempCycle()
    ' Call Macro_Run_Helmholtz_BSweep()
    ' Call Macro_Run_K2600_OutputOff_Check()
    ' Call Macro_Run_Hall_ETO_Switch_TempField()
End Sub

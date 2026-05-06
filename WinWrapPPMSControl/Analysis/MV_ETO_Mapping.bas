'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"

Option Explicit

Private Function MV_JoinKV(ByVal k As String, ByVal v As String) As String
    MV_JoinKV = k & "=" & v
End Function

Private Function MV_BuildMappingComment(ByVal helmholtzField_Oe As Double, _
                                        ByVal totalCurrent_A As Double, _
                                        ByVal compliance_V As Double, _
                                        ByVal hallCurrent_mA As Double, _
                                        ByVal hallCompliance_V As Double, _
                                        ByVal hallVoltage_V As Double, _
                                        ByVal hallField_Oe As Double, _
                                        ByVal hallNPLC As Double, _
                                        ByVal hallAvgFilter As Integer) As String
    Dim s As String

    s = "EXTMAP," & MV_JoinKV("mapping_version", MV_MAPPING_VERSION)
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_TARGET_FIELD), CStr(helmholtzField_Oe))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_TOTAL_CURRENT), CStr(totalCurrent_A))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_COMPLIANCE), CStr(compliance_V))

    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_CURRENT), CStr(hallCurrent_mA))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_COMPLIANCE), CStr(hallCompliance_V))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_VOLTAGE), CStr(hallVoltage_V))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_FIELD), CStr(hallField_Oe))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_NPLC), CStr(hallNPLC))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_HALL_FILTER), CStr(hallAvgFilter))

    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_CURR_A), CStr(MV_LastCurrentA_A))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_CURR_B), CStr(MV_LastCurrentB_A))
    s = s & "," & MV_JoinKV("ch" & CStr(MV_CH_EXT_STATUS), "0")

    s = s & "," & MV_JoinKV("hall_v_per_g", CStr(MV_HallVPerG))
    s = s & "," & MV_JoinKV("hall_v_offset", CStr(MV_HallVOffset))

    MV_BuildMappingComment = s
End Function

Public Function Data_AddComment(ByVal commentText As String) As Boolean
    On Error GoTo EH
    DynaCool.SequenceMeasure "ETOLC '" & commentText & "'"
    Data_AddComment = True
    Exit Function
EH:
    MV_SetError "Failed to append ETOLC comment: " & Err.Description
    Data_AddComment = False
End Function

Public Function Data_WriteETOExtendedRow(ByVal helmholtzField_Oe As Double, _
                                         ByVal appliedCurrent_A As Double, _
                                         ByVal compliance_V As Double, _
                                         ByVal hallCurrent_mA As Double, _
                                         ByVal hallCompliance_V As Double, _
                                         ByVal hallVoltage_V As Double, _
                                         ByVal hallField_Oe As Double, _
                                         ByVal hallNPLC As Double, _
                                         ByVal hallAvgFilter As Integer) As Boolean
    Dim payload As String

    payload = MV_BuildMappingComment(helmholtzField_Oe, _
                                     appliedCurrent_A, _
                                     compliance_V, _
                                     hallCurrent_mA, _
                                     hallCompliance_V, _
                                     hallVoltage_V, _
                                     hallField_Oe, _
                                     hallNPLC, _
                                     hallAvgFilter)

    Data_WriteETOExtendedRow = Data_AddComment(payload)
End Function

Public Function SelfTest_ETOChannelMappingV1() As Boolean
    Dim ok As Boolean
    ok = Data_AddComment("EXTMAP,selftest=1,mapping_version=" & MV_MAPPING_VERSION)
    SelfTest_ETOChannelMappingV1 = ok
End Function

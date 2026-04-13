'#Uses "..\Utility\Macros__QD_Library_Oct_2015\MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"

Option Explicit

Private MV_HelmDataFile As Object

Private Const COL_TEMP_K As String = "Temperature (K)"
Private Const COL_FIELD_OE As String = "Field (Oe)"
Private Const COL_TARGET_FIELD_OE As String = "Target Field (Oe)"
Private Const COL_TOTAL_CURRENT_A As String = "Helmholtz Current Total (A)"
Private Const COL_CURRENT_A_A As String = "Applied Current ChA (A)"
Private Const COL_CURRENT_B_A As String = "Applied Current ChB (A)"
Private Const COL_HELM_COMPLIANCE_V As String = "Helmholtz Compliance (V)"
Private Const COL_HELM_NPLC As String = "Helmholtz NPLC"
Private Const COL_RES_A_OHM As String = "Resistance ChA (Ohms)"
Private Const COL_RES_B_OHM As String = "Resistance ChB (Ohms)"
Private Const COL_HALL_CURRENT_mA As String = "Hall Current (mA)"
Private Const COL_HALL_COMPLIANCE_V As String = "Hall Compliance (V)"
Private Const COL_HALL_NPLC As String = "Hall NPLC"
Private Const COL_HALL_VOLTAGE_V As String = "Hall Voltage (V)"
Private Const COL_HALL_FIELD_OE As String = "Hall Field (Oe)"

Private Sub Log_SetNumericOrBlank(ByRef rowData() As Variant, ByVal idxLabel As Integer, ByVal idxValue As Integer, ByVal colName As String, ByVal value As Double)
    rowData(idxLabel) = colName
    If MV_IsFinite(value) Then
        rowData(idxValue) = value
    Else
        rowData(idxValue) = ""
    End If
End Sub

Private Function MV_EndsWithIgnoreCase(ByVal txt As String, ByVal suffix As String) As Boolean
    Dim lt As String
    Dim ls As String
    lt = LCase$(txt)
    ls = LCase$(suffix)
    If Len(lt) < Len(ls) Then
        MV_EndsWithIgnoreCase = False
    Else
        MV_EndsWithIgnoreCase = (Right$(lt, Len(ls)) = ls)
    End If
End Function

Public Function MV_InitHelmholtzLog(ByVal filePath As String) As Boolean
    On Error GoTo EH

    MV_HelmLogPath = filePath
    If Not MV_EndsWithIgnoreCase(MV_HelmLogPath, ".dat") Then
        MV_HelmLogPath = MV_HelmLogPath & ".dat"
    End If

    Set MV_HelmDataFile = New MultiVuDataFile
    MV_HelmDataFile.AddColumn COL_TEMP_K
    MV_HelmDataFile.AddColumn COL_FIELD_OE
    MV_HelmDataFile.AddColumn COL_TARGET_FIELD_OE, mvStartupAxisY1
    MV_HelmDataFile.AddColumn COL_TOTAL_CURRENT_A, mvStartupAxisY2
    MV_HelmDataFile.AddColumn COL_CURRENT_A_A
    MV_HelmDataFile.AddColumn COL_CURRENT_B_A
    MV_HelmDataFile.AddColumn COL_HELM_COMPLIANCE_V
    MV_HelmDataFile.AddColumn COL_HELM_NPLC
    MV_HelmDataFile.AddColumn COL_RES_A_OHM, mvStartupAxisY3
    MV_HelmDataFile.AddColumn COL_RES_B_OHM, mvStartupAxisY3
    MV_HelmDataFile.AddColumn COL_HALL_CURRENT_mA
    MV_HelmDataFile.AddColumn COL_HALL_COMPLIANCE_V
    MV_HelmDataFile.AddColumn COL_HALL_NPLC
    MV_HelmDataFile.AddColumn COL_HALL_VOLTAGE_V
    MV_HelmDataFile.AddColumn COL_HALL_FIELD_OE

    MV_HelmDataFile.CreateFileAndWriteHeader MV_HelmLogPath, "WinWrapPPMSControl Helmholtz live log", "; WinWrapPPMSControl Helmholtz live log"

    MV_InitHelmholtzLog = True
    Exit Function
EH:
    MV_SetError "Init Helmholtz log failed: " & Err.Description
    MV_InitHelmholtzLog = False
End Function

Public Function Log_WriteHelmholtzRow(ByVal time_s As Double, _
                                      ByVal temp_K As Double, _
                                      ByVal field_Oe As Double, _
                                      ByVal targetField_Oe As Double, _
                                      ByVal currentA_A As Double, _
                                      ByVal currentB_A As Double, _
                                      ByVal helmCompliance_V As Double, _
                                      ByVal helmNplc As Double, _
                                      ByVal resistanceA_Ohm As Double, _
                                      ByVal resistanceB_Ohm As Double, _
                                      ByVal hallCurrent_mA As Double, _
                                      ByVal hallCompliance_V As Double, _
                                      ByVal hallNplc As Double, _
                                      Optional ByVal hallVoltage_V As Double = -9.9E99, _
                                      Optional ByVal hallField_Oe As Double = -9.9E99) As Boolean
    On Error GoTo EH
    Dim rowData(1 To 32) As Variant

    If MV_HelmDataFile Is Nothing Then
        MV_SetError "Helmholtz log writer not initialized"
        Log_WriteHelmholtzRow = False
        Exit Function
    End If

    rowData(1) = MV_HelmDataFile.GetTimeCol()
    rowData(2) = time_s
    rowData(3) = COL_TEMP_K
    rowData(4) = temp_K
    rowData(5) = COL_FIELD_OE
    rowData(6) = field_Oe
    rowData(7) = COL_TARGET_FIELD_OE
    rowData(8) = targetField_Oe
    rowData(9) = COL_TOTAL_CURRENT_A
    rowData(10) = currentA_A + currentB_A
    rowData(11) = COL_CURRENT_A_A
    rowData(12) = currentA_A
    rowData(13) = COL_CURRENT_B_A
    rowData(14) = currentB_A
    rowData(15) = COL_HELM_COMPLIANCE_V
    rowData(16) = helmCompliance_V
    rowData(17) = COL_HELM_NPLC
    rowData(18) = helmNplc
    rowData(19) = COL_RES_A_OHM
    rowData(20) = resistanceA_Ohm
    rowData(21) = COL_RES_B_OHM
    rowData(22) = resistanceB_Ohm
    rowData(23) = COL_HALL_CURRENT_mA
    rowData(24) = hallCurrent_mA
    rowData(25) = COL_HALL_COMPLIANCE_V
    rowData(26) = hallCompliance_V
    rowData(27) = COL_HALL_NPLC
    rowData(28) = hallNplc
    Call Log_SetNumericOrBlank(rowData, 29, 30, COL_HALL_VOLTAGE_V, hallVoltage_V)
    Call Log_SetNumericOrBlank(rowData, 31, 32, COL_HALL_FIELD_OE, hallField_Oe)
    Call MV_HelmDataFile.WriteDataUsingArray(rowData, False)

    Log_WriteHelmholtzRow = True
    Exit Function
EH:
    MV_SetError "Write Helmholtz log row failed: " & Err.Description
    Log_WriteHelmholtzRow = False
End Function
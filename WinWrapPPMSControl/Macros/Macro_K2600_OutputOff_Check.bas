'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses "..\Instruments\MV_K2600_Helmholtz.bas"
'#Uses "..\Runners\MV_RunWrappers.bas"
'#Uses "..\Core\MV_GpibIO.bas"

Option Explicit

Public Sub Macro_Run_K2600_OutputOff_Check()
    ' =========================================================
    ' Check configuration - edit these values
    ' =========================================================
    Dim K2600_resourceName As String     ' VISA resource
    Dim CurrentTolerance_A As Double     ' Max allowed |source current setpoint| when OFF

    K2600_resourceName = MV_K2600_RESOURCE
    CurrentTolerance_A = 0.000001

    ' =========================================================
    ' Do not edit below this line
    ' =========================================================
    Dim outputA As String
    Dim outputB As String
    Dim currentA As String
    Dim currentB As String
    Dim currentA_A As Double
    Dim currentB_A As Double
    Dim ok As Boolean
    Dim connectedHere As Boolean

    Debug.Clear
    connectedHere = False

    MV_Log "[MACRO][K2600-OFF] Starting output-off check"

    If MV_K2600_Device = "" Then
        MV_Log "[MACRO][K2600-OFF] Connecting to " & K2600_resourceName
        If Not K2600_Connect(K2600_resourceName) Then
            MV_Log "[MACRO][K2600-OFF] FAIL connect: " & MV_LastError
            Exit Sub
        End If
        connectedHere = True
        MV_Log "[MACRO][K2600-OFF] Connected"
    Else
        MV_Log "[MACRO][K2600-OFF] Using existing connection: " & MV_K2600_Device
    End If

    Call K2600_OutputOff()
    MV_Log "[MACRO][K2600-OFF] Sent OUTPUT_OFF and zero-current commands"

    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.output)", outputA) Then
        MV_Log "[MACRO][K2600-OFF] FAIL read SMUA output state: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.output)", outputB) Then
        MV_Log "[MACRO][K2600-OFF] FAIL read SMUB output state: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smua.source.leveli)", currentA) Then
        MV_Log "[MACRO][K2600-OFF] FAIL read SMUA current level: " & MV_LastError
        GoTo Cleanup
    End If
    If Not MV_GPIB_Query(MV_K2600_Device, "print(smub.source.leveli)", currentB) Then
        MV_Log "[MACRO][K2600-OFF] FAIL read SMUB current level: " & MV_LastError
        GoTo Cleanup
    End If

    currentA_A = CDbl(Val(currentA))
    currentB_A = CDbl(Val(currentB))

    MV_Log "[MACRO][K2600-OFF] SMUA output=" & Trim$(outputA) & ", leveli=" & CStr(currentA_A) & " A"
    MV_Log "[MACRO][K2600-OFF] SMUB output=" & Trim$(outputB) & ", leveli=" & CStr(currentB_A) & " A"

    ok = (Val(outputA) = 0) And _
         (Val(outputB) = 0) And _
         (Abs(currentA_A) <= CurrentTolerance_A) And _
         (Abs(currentB_A) <= CurrentTolerance_A)

    If ok Then
        MV_Log "[MACRO][K2600-OFF] PASS outputs are OFF and setpoints are zero"
    Else
        MV_Log "[MACRO][K2600-OFF] FAIL non-zero or enabled output readback"
    End If

Cleanup:
    If MV_K2600_Device <> "" Then
        Call K2600_Disconnect()
        If connectedHere Then
            MV_Log "[MACRO][K2600-OFF] Disconnected"
        Else
            MV_Log "[MACRO][K2600-OFF] Disconnected existing session after safety shutdown"
        End If
    End If
End Sub

'#Uses "..\Core\MV_Constants.bas"
'#Uses "..\Core\MV_DynaHelpers.bas"
'#Uses "..\Analysis\MV_HelmholtzLog.bas"
'#Uses ".\MV_K2600_Helmholtz.bas"
'#Uses "..\Core\MV_GpibIO.bas"


Option Explicit

Private Const K7001_CARD_SLOT As Integer = 1
Private Const K7001_ROW_IPLUS As Integer = 1
Private Const K7001_ROW_VPLUS As Integer = 2
Private Const K7001_ROW_VMINUS As Integer = 3
Private Const K7001_ROW_IMINUS As Integer = 4
Private Const K7001_MIN_OUTPUT As Integer = 1
Private Const K7001_MAX_OUTPUT As Integer = 10

Private Type K7001_MapEntry
    NameKey As String
    NameLabel As String
    OutIPlus As Integer
    OutVPlus As Integer
    OutVMinus As Integer
    OutIMinus As Integer
End Type

Private MV_K7001_Maps() As K7001_MapEntry
Private MV_K7001_MapCount As Long
Private MV_K7001_DefaultsLoaded As Boolean

Private Function K7001_NormalizeName(ByVal logicalName As String) As String
    K7001_NormalizeName = LCase$(Trim$(logicalName))
End Function

Private Function K7001_RowName(ByVal rowNumber As Integer) As String
    Select Case rowNumber
        Case K7001_ROW_IPLUS
            K7001_RowName = "I+"
        Case K7001_ROW_VPLUS
            K7001_RowName = "V+"
        Case K7001_ROW_VMINUS
            K7001_RowName = "V-"
        Case K7001_ROW_IMINUS
            K7001_RowName = "I-"
        Case Else
            K7001_RowName = "Row" & CStr(rowNumber)
    End Select
End Function

Private Function K7001_ValidateOutput(ByVal outputNumber As Integer, ByVal rowNumber As Integer) As Boolean
    If outputNumber < K7001_MIN_OUTPUT Or outputNumber > K7001_MAX_OUTPUT Then
        K7001_ValidateOutput = False
        Exit Function
    End If
    K7001_ValidateOutput = True
End Function

Private Function K7001_Crosspoint(ByVal rowNumber As Integer, ByVal outputNumber As Integer) As String
    K7001_Crosspoint = CStr(K7001_CARD_SLOT) & "!" & CStr(rowNumber) & "!" & Right$("0" & CStr(outputNumber), 2)
End Function

Private Sub K7001_EnsureMapArray()
    If MV_K7001_MapCount <= 0 Then
        ReDim MV_K7001_Maps(0 To 0)
    End If
End Sub

Private Function K7001_FindIndex(ByVal nameKey As String) As Long
    Dim i As Long

    For i = 0 To MV_K7001_MapCount - 1
        If MV_K7001_Maps(i).NameKey = nameKey Then
            K7001_FindIndex = i
            Exit Function
        End If
    Next i

    K7001_FindIndex = -1
End Function

Private Sub K7001_EnsureDefaultsLoaded()
    If MV_K7001_DefaultsLoaded Then Exit Sub
    Call K7001_LoadDefaultMappings()
End Sub

Private Sub K7001_AddDefaultColumnMap(ByVal logicalName As String, ByVal outputNumber As Integer)
    Call K7001_DefineChannel(logicalName, outputNumber, outputNumber, outputNumber, outputNumber)
End Sub

Public Sub K7001_ClearMappings()
    MV_K7001_MapCount = 0
    Erase MV_K7001_Maps
    MV_K7001_DefaultsLoaded = False
    MV_Log "[K7001] cleared all logical channel mappings"
End Sub

Public Sub K7001_LoadDefaultMappings()
    Dim i As Integer

    MV_K7001_MapCount = 0
    Erase MV_K7001_Maps

    For i = 1 To 10
        Call K7001_AddDefaultColumnMap(Chr$(Asc("a") + i - 1), i)
    Next i

    MV_K7001_DefaultsLoaded = True
    MV_Log "[K7001] loaded default mappings a..j -> outputs 1..10"
End Sub

Public Function K7001_DefineChannel(ByVal logicalName As String, _
                                    ByVal outIPlus As Integer, _
                                    ByVal outVPlus As Integer, _
                                    ByVal outVMinus As Integer, _
                                    ByVal outIMinus As Integer) As Boolean
    Dim nameKey As String
    Dim nameLabel As String
    Dim idx As Long
    Dim oldTuple As String
    Dim newTuple As String

    nameLabel = Trim$(logicalName)
    nameKey = K7001_NormalizeName(nameLabel)

    If nameKey = "" Then
        MV_Log "[K7001][ERROR] logical name cannot be empty"
        K7001_DefineChannel = False
        Exit Function
    End If

    If Not K7001_ValidateOutput(outIPlus, K7001_ROW_IPLUS) Then
        K7001_DefineChannel = False
        Exit Function
    End If
    If Not K7001_ValidateOutput(outVPlus, K7001_ROW_VPLUS) Then
        K7001_DefineChannel = False
        Exit Function
    End If
    If Not K7001_ValidateOutput(outVMinus, K7001_ROW_VMINUS) Then
        K7001_DefineChannel = False
        Exit Function
    End If
    If Not K7001_ValidateOutput(outIMinus, K7001_ROW_IMINUS) Then
        K7001_DefineChannel = False
        Exit Function
    End If

    idx = K7001_FindIndex(nameKey)
    newTuple = "(" & CStr(outIPlus) & "," & CStr(outVPlus) & "," & CStr(outVMinus) & "," & CStr(outIMinus) & ")"

    If idx >= 0 Then
        oldTuple = "(" & CStr(MV_K7001_Maps(idx).OutIPlus) & "," & CStr(MV_K7001_Maps(idx).OutVPlus) & "," & CStr(MV_K7001_Maps(idx).OutVMinus) & "," & CStr(MV_K7001_Maps(idx).OutIMinus) & ")"
        MV_Log "[K7001][WARN] overwrite mapping name='" & nameKey & "' old=" & oldTuple & " new=" & newTuple
    Else
        Call K7001_EnsureMapArray()
        idx = MV_K7001_MapCount
        If MV_K7001_MapCount = 0 Then
            ReDim MV_K7001_Maps(0 To 0)
        Else
            ReDim Preserve MV_K7001_Maps(0 To MV_K7001_MapCount)
        End If
        MV_K7001_MapCount = MV_K7001_MapCount + 1
    End If

    MV_K7001_Maps(idx).NameKey = nameKey
    If nameLabel = "" Then
        MV_K7001_Maps(idx).NameLabel = nameKey
    Else
        MV_K7001_Maps(idx).NameLabel = nameLabel
    End If
    MV_K7001_Maps(idx).OutIPlus = outIPlus
    MV_K7001_Maps(idx).OutVPlus = outVPlus
    MV_K7001_Maps(idx).OutVMinus = outVMinus
    MV_K7001_Maps(idx).OutIMinus = outIMinus

    K7001_DefineChannel = True
End Function

Public Sub K7001_PrintMappings()
    Dim i As Long
    Dim j As Long
    Dim idx() As Long
    Dim tmp As Long

    Call K7001_EnsureDefaultsLoaded()

    If MV_K7001_MapCount <= 0 Then
        MV_Log "[K7001] no logical channel mappings defined"
        Exit Sub
    End If

    ReDim idx(0 To MV_K7001_MapCount - 1)
    For i = 0 To MV_K7001_MapCount - 1
        idx(i) = i
    Next i

    For i = 0 To MV_K7001_MapCount - 2
        For j = i + 1 To MV_K7001_MapCount - 1
            If MV_K7001_Maps(idx(j)).NameKey < MV_K7001_Maps(idx(i)).NameKey Then
                tmp = idx(i)
                idx(i) = idx(j)
                idx(j) = tmp
            End If
        Next j
    Next i

    MV_Log "[K7001] active mappings (name -> I+,V+,V-,I-)"
    For i = 0 To MV_K7001_MapCount - 1
        j = idx(i)
        MV_Log "[K7001]   " & MV_K7001_Maps(j).NameKey & " -> " & _
               CStr(MV_K7001_Maps(j).OutIPlus) & "," & _
               CStr(MV_K7001_Maps(j).OutVPlus) & "," & _
               CStr(MV_K7001_Maps(j).OutVMinus) & "," & _
               CStr(MV_K7001_Maps(j).OutIMinus)
    Next i
End Sub

Public Function K7001_Connect(Optional ByVal resource As String = "") As Boolean
    Dim idn As String

    If resource = "" Then resource = MV_K7001_RESOURCE

    If Not MV_GPIB_Connect(resource, MV_K7001_Device) Then
        K7001_Connect = False
        Exit Function
    End If

    If MV_GPIB_Query(MV_K7001_Device, "*IDN?", idn) Then
        MV_Log "[K7001] connected: resource=" & resource & "; idn=" & idn
    Else
        MV_Log "[K7001][WARN] connected but IDN query failed: resource=" & resource
    End If

    Call K7001_EnsureDefaultsLoaded()
    K7001_Connect = True
End Function

Public Function K7001_Disconnect() As Boolean
    On Error Resume Next
    Call MV_GPIB_Disconnect(MV_K7001_Device)
    On Error GoTo 0
    MV_Log "[K7001] disconnected"
    K7001_Disconnect = True
End Function

Public Function K7001_OpenAll() As Boolean
    If MV_K7001_Device = "" Then
        MV_Log "[K7001][ERROR] not connected"
        K7001_OpenAll = False
        Exit Function
    End If

    If Not MV_GPIB_Write(MV_K7001_Device, ":ROUTE:OPEN ALL") Then
        K7001_OpenAll = False
        Exit Function
    End If

    MV_Log "[K7001] open all channels"
    K7001_OpenAll = True
End Function

Public Function K7001_CloseChannel(ByVal logicalName As String) As Boolean
    Dim nameKey As String
    Dim idx As Long
    Dim cmd As String
    Dim p1 As String
    Dim p2 As String
    Dim p3 As String
    Dim p4 As String

    If MV_K7001_Device = "" Then
        MV_Log "[K7001][ERROR] not connected"
        K7001_CloseChannel = False
        Exit Function
    End If

    Call K7001_EnsureDefaultsLoaded()

    nameKey = K7001_NormalizeName(logicalName)
    idx = K7001_FindIndex(nameKey)
    If idx < 0 Then
        MV_Log "[K7001][ERROR] unknown logical channel name: " & logicalName
        K7001_CloseChannel = False
        Exit Function
    End If

    If Not K7001_OpenAll() Then
        K7001_CloseChannel = False
        Exit Function
    End If

    p1 = K7001_Crosspoint(K7001_ROW_IPLUS, MV_K7001_Maps(idx).OutIPlus)
    p2 = K7001_Crosspoint(K7001_ROW_VPLUS, MV_K7001_Maps(idx).OutVPlus)
    p3 = K7001_Crosspoint(K7001_ROW_VMINUS, MV_K7001_Maps(idx).OutVMinus)
    p4 = K7001_Crosspoint(K7001_ROW_IMINUS, MV_K7001_Maps(idx).OutIMinus)

    cmd = "ROUTE:CLOSE (@" & p1 & "," & p2 & "," & p3 & "," & p4 & ")"

    If Not MV_GPIB_Write(MV_K7001_Device, cmd) Then
        K7001_CloseChannel = False
        Exit Function
    End If

    MV_Log "[K7001] close name='" & nameKey & "' outputs=(" & _
           CStr(MV_K7001_Maps(idx).OutIPlus) & "," & _
           CStr(MV_K7001_Maps(idx).OutVPlus) & "," & _
           CStr(MV_K7001_Maps(idx).OutVMinus) & "," & _
           CStr(MV_K7001_Maps(idx).OutIMinus) & ")"

    K7001_CloseChannel = True
End Function

'#Uses "C:\Users\Ilay\OneDrive - Technion\Desktop\MC_Projects\Extarnal_Device_Dyna\WinWrapPPMSControl\MV_Constants.bas"

Option Explicit

' =========================================================================
' VISA32.DLL NATIVE FUNCTION DECLARATIONS
' =========================================================================
Declare Function viOpenDefaultRM Lib "visa32.dll" (ByRef sesn As Long) As Long
Declare Function viOpen Lib "visa32.dll" (ByVal sesn As Long, ByVal rsrcName As String, ByVal accessMode As Long, ByVal timeout As Long, ByRef vi As Long) As Long
Declare Function viWrite Lib "visa32.dll" (ByVal vi As Long, ByVal buffer As String, ByVal count As Long, ByRef retCount As Long) As Long
Declare Function viRead Lib "visa32.dll" (ByVal vi As Long, ByVal buffer As String, ByVal count As Long, ByRef retCount As Long) As Long
Declare Function viSetAttribute Lib "visa32.dll" (ByVal vi As Long, ByVal attrName As Long, ByVal attrValue As Long) As Long
Declare Function viClose Lib "visa32.dll" (ByVal vi As Long) As Long
Declare Function viClear Lib "visa32.dll" (ByVal vi As Long) As Long

' =========================================================================
' VISA32 CONSTANTS
' =========================================================================
Const VI_ATTR_TERMCHAR_EN As Long = &H3FFF0038
Const VI_ATTR_TERMCHAR As Long = &H3FFF0018
Const VI_ATTR_TMO_VALUE As Long = &H3FFF001A
Const VI_SUCCESS As Long = 0
Const VI_ERROR_TMO As Long = -1073807339

Private Const MV_GPIB_READ_CHUNK_SIZE As Long = 256
Private Const MV_GPIB_MAX_QUERY_CHUNKS As Long = 512
Private Const MV_GPIB_DRAIN_TIMEOUT_MS As Long = 5
Private Const MV_GPIB_DRAIN_MAX_READS As Long = 32
Private Const MV_GPIB_ENABLE_PREQUERY_DRAIN As Boolean = False

Private Function VISA_StatusIsSuccess(ByVal status As Long) As Boolean
    ' VISA returns 0 for success and positive values for success-with-info/warnings.
    VISA_StatusIsSuccess = (status >= 0)
End Function

Private Function MV_GPIB_ReadLineFromHandle(ByVal viHandle As Long, ByRef outText As String, ByRef outErr As String) As Boolean
    Dim status As Long
    Dim retCount As Long
    Dim readBuf As String * 256
    Dim chunkText As String
    Dim i As Long

    outText = ""
    outErr = ""

    For i = 1 To MV_GPIB_MAX_QUERY_CHUNKS
        readBuf = String(MV_GPIB_READ_CHUNK_SIZE, vbNullChar)

        On Error Resume Next
        status = viRead(viHandle, readBuf, MV_GPIB_READ_CHUNK_SIZE, retCount)
        On Error GoTo 0

        If Not VISA_StatusIsSuccess(status) Then
            If status = VI_ERROR_TMO Then
                If Trim$(outText) <> "" Then
                    outText = Trim$(outText)
                    MV_GPIB_ReadLineFromHandle = True
                Else
                    outErr = "viRead returned " & CStr(status)
                    MV_GPIB_ReadLineFromHandle = False
                End If
            Else
                outErr = "viRead returned " & CStr(status)
                MV_GPIB_ReadLineFromHandle = False
            End If
            Exit Function
        End If

        If retCount <= 0 Then
            If Trim$(outText) <> "" Then
                outText = Trim$(outText)
                MV_GPIB_ReadLineFromHandle = True
            Else
                outErr = "viRead returned empty response"
                MV_GPIB_ReadLineFromHandle = False
            End If
            Exit Function
        End If

        chunkText = Left$(readBuf, retCount)
        outText = outText & chunkText

        If InStr(1, chunkText, vbLf) > 0 Or InStr(1, chunkText, vbCr) > 0 Then
            outText = Trim$(outText)
            If outText <> "" Then
                MV_GPIB_ReadLineFromHandle = True
            Else
                outErr = "viRead returned empty response"
                MV_GPIB_ReadLineFromHandle = False
            End If
            Exit Function
        End If

        ' Do not treat short reads as end-of-message.  Some VISA backends return
        ' varying chunk sizes before the final terminator/EOI.
    Next

    outErr = "response exceeds " & CStr(MV_GPIB_READ_CHUNK_SIZE * MV_GPIB_MAX_QUERY_CHUNKS) & " bytes"
    MV_GPIB_ReadLineFromHandle = False
End Function

Public Function MV_GPIB_QueryWithTimeout(ByVal deviceKey As String, ByVal cmd As String, ByRef outText As String, ByVal timeout_s As Double, Optional ByVal quietFail As Boolean = False) As Boolean
    Dim attempt As Integer
    Dim lastErr As String
    Dim address As Integer
    Dim viHandle As Long
    Dim status As Long
    Dim retCount As Long
    Dim fullCmd As String
    Dim readErr As String
    Dim writeOk As Boolean
    Dim timeout_ms As Long
    Dim default_timeout_ms As Long

    outText = ""
    If timeout_s <= 0# Then
        MV_GPIB_QueryWithTimeout = MV_GPIB_Query(deviceKey, cmd, outText)
        Exit Function
    End If

    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB query failed: device is not connected"
        MV_GPIB_QueryWithTimeout = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB query failed: invalid device address: " & deviceKey
        MV_GPIB_QueryWithTimeout = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB query failed: device handle not found for address " & CStr(address)
        MV_GPIB_QueryWithTimeout = False
        Exit Function
    End If

    If MV_GPIBDebug Then MV_Log "[GPIB][Q] " & cmd

    fullCmd = cmd & vbLf
    timeout_ms = CLng(timeout_s * 1000#)
    default_timeout_ms = CLng(MV_GPIB_TIMEOUT_S * 1000#)
    Call MV_GPIB_SetTimeoutMs(viHandle, timeout_ms)

    writeOk = False
    For attempt = 1 To MV_GPIB_RETRY_COUNT
        On Error Resume Next
        status = viWrite(viHandle, fullCmd, Len(fullCmd), retCount)
        On Error GoTo 0
        If VISA_StatusIsSuccess(status) Then
            writeOk = True
            Exit For
        End If
        lastErr = "viWrite returned " & CStr(status)
        If MV_GPIBDebug Then MV_Log "[GPIB][Q][write retry " & CStr(attempt) & "] " & lastErr
        MV_WaitSeconds 0.01
        DoEvents
    Next

    If Not writeOk Then
        Call MV_GPIB_SetTimeoutMs(viHandle, default_timeout_ms)
        If Not quietFail Then MV_SetError "GPIB query write failed: " & cmd & " :: " & lastErr
        MV_GPIB_QueryWithTimeout = False
        Exit Function
    End If

    For attempt = 1 To MV_GPIB_RETRY_COUNT
        MV_WaitSeconds 0.01
        If MV_GPIB_ReadLineFromHandle(viHandle, outText, readErr) Then
            If MV_GPIBDebug Then MV_Log "[GPIB][R] " & outText
            Call MV_GPIB_SetTimeoutMs(viHandle, default_timeout_ms)
            MV_GPIB_QueryWithTimeout = True
            Exit Function
        End If
        lastErr = readErr
        If MV_GPIBDebug Then MV_Log "[GPIB][Q][read retry " & CStr(attempt) & "] " & lastErr
        outText = ""
        DoEvents
    Next

    Call MV_GPIB_SetTimeoutMs(viHandle, default_timeout_ms)
    If Not quietFail Then MV_SetError "GPIB query failed after retries: " & cmd & " :: " & lastErr
    MV_GPIB_QueryWithTimeout = False
End Function

Private Sub MV_GPIB_SetTimeoutMs(ByVal viHandle As Long, ByVal timeoutMs As Long)
    On Error Resume Next
    Call viSetAttribute(viHandle, VI_ATTR_TMO_VALUE, timeoutMs)
    On Error GoTo 0
End Sub

Private Function MV_GPIB_DrainPendingRead(ByVal viHandle As Long) As Boolean
    Dim status As Long
    Dim retCount As Long
    Dim readBuf As String * 256
    Dim i As Long
    Dim drainedBytes As Long

    MV_GPIB_DrainPendingRead = False
    drainedBytes = 0

    Call MV_GPIB_SetTimeoutMs(viHandle, MV_GPIB_DRAIN_TIMEOUT_MS)

    For i = 1 To MV_GPIB_DRAIN_MAX_READS
        readBuf = String(MV_GPIB_READ_CHUNK_SIZE, vbNullChar)

        On Error Resume Next
        status = viRead(viHandle, readBuf, MV_GPIB_READ_CHUNK_SIZE, retCount)
        On Error GoTo 0

        If status = VI_ERROR_TMO Then
            MV_GPIB_DrainPendingRead = True
            Exit For
        End If

        If Not VISA_StatusIsSuccess(status) Then
            MV_GPIB_DrainPendingRead = False
            Exit For
        End If

        If retCount <= 0 Then
            MV_GPIB_DrainPendingRead = True
            Exit For
        End If

        drainedBytes = drainedBytes + retCount
    Next

    If MV_GPIBDebug And drainedBytes > 0 Then
        MV_Log "[GPIB][Q] drained stale bytes=" & CStr(drainedBytes)
    End If

    Call MV_GPIB_SetTimeoutMs(viHandle, CLng(MV_GPIB_TIMEOUT_S * 1000#))
End Function

' =========================================================================
' PRIVATE SESSION MANAGEMENT
' =========================================================================
Private rmSession As Long                ' Global VISA Resource Manager handle
Private VISA_Initialized As Boolean      ' Flag: RM successfully opened
Private K2600_VIHandle As Long           ' VI handle for K2600 device
Private K2450_VIHandle As Long           ' VI handle for K2450 device

' =========================================================================
' HELPER: INITIALIZE VISTA RESOURCE MANAGER (called once at startup)
' =========================================================================
Private Function VISA_InitResourceManager() As Boolean
    Dim status As Long
    
    If VISA_Initialized Then
        VISA_InitResourceManager = True
        Exit Function
    End If
    
    On Error Resume Next
    status = viOpenDefaultRM(rmSession)
    On Error GoTo 0
    
    If status = VI_SUCCESS Then
        VISA_Initialized = True
        If MV_GPIBDebug Then MV_Log "[VISA] Resource Manager opened"
        VISA_InitResourceManager = True
    Else
        MV_SetError "VISA Resource Manager failed to open: " & CStr(status)
        VISA_Initialized = False
        VISA_InitResourceManager = False
    End If
End Function

' =========================================================================
' HELPER: PARSE GPIB ADDRESS FROM RESOURCE STRING
' =========================================================================
Private Function MV_GPIB_ParseAddress(ByVal resourceOrAddress As String, ByRef address As Integer) As Boolean
    Dim token As String
    Dim p1 As Long
    Dim p2 As Long

    token = Trim$(resourceOrAddress)
    If token = "" Then
        MV_GPIB_ParseAddress = False
        Exit Function
    End If

    ' Accept plain numeric addresses like "26".
    If IsNumeric(token) Then
        address = CInt(token)
        MV_GPIB_ParseAddress = True
        Exit Function
    End If

    ' Accept VISA-like resources: GPIB0::26::INSTR
    p1 = InStr(1, token, "::")
    If p1 > 0 Then
        p2 = InStr(p1 + 2, token, "::")
        If p2 > p1 Then
            token = Mid$(token, p1 + 2, p2 - (p1 + 2))
            If IsNumeric(token) Then
                address = CInt(token)
                MV_GPIB_ParseAddress = True
                Exit Function
            End If
        End If
    End If

    MV_GPIB_ParseAddress = False
End Function

' =========================================================================
' HELPER: GET VI HANDLE FOR A GIVEN DEVICE ADDRESS
' =========================================================================
Private Function GetVIHandle(ByVal address As Integer) As Long
    If address = 26 Then
        GetVIHandle = K2600_VIHandle
    ElseIf address = 18 Then
        GetVIHandle = K2450_VIHandle
    Else
        GetVIHandle = 0
    End If
End Function

' =========================================================================
' HELPER: SET VI HANDLE FOR A GIVEN DEVICE ADDRESS
' =========================================================================
Private Sub SetVIHandle(ByVal address As Integer, ByVal viHandle As Long)
    If address = 26 Then
        K2600_VIHandle = viHandle
    ElseIf address = 18 Then
        K2450_VIHandle = viHandle
    End If
End Sub

' =========================================================================
' HELPER: OPEN DEVICE VIA VISA AND CONFIGURE TERMINATION
' =========================================================================
Private Function VISA_OpenDevice(ByVal resource As String, ByVal timeout_ms As Long, ByRef viHandle As Long) As Boolean
    Dim status As Long
    Dim address As Integer
    
    viHandle = 0
    
    If Not VISA_InitResourceManager() Then
        VISA_OpenDevice = False
        Exit Function
    End If
    
    If Not MV_GPIB_ParseAddress(resource, address) Then
        MV_SetError "VISA open failed: cannot parse resource: " & resource
        VISA_OpenDevice = False
        Exit Function
    End If
    
    ' Check if already open for this address
    If GetVIHandle(address) <> 0 Then
        viHandle = GetVIHandle(address)
        If MV_GPIBDebug Then MV_Log "[VISA] Device at address " & CStr(address) & " already open (handle=" & CStr(viHandle) & ")"
        VISA_OpenDevice = True
        Exit Function
    End If
    
    On Error Resume Next
    status = viOpen(rmSession, resource, 0, timeout_ms, viHandle)
    On Error GoTo 0
    
    If status <> VI_SUCCESS Then
        MV_SetError "VISA viOpen failed for " & resource & ": status=" & CStr(status)
        viHandle = 0
        VISA_OpenDevice = False
        Exit Function
    End If
    
    ' Configure Termination Character (Line Feed = 10)
    On Error Resume Next
    Call viSetAttribute(viHandle, VI_ATTR_TERMCHAR_EN, 1)
    Call viSetAttribute(viHandle, VI_ATTR_TERMCHAR, 10)
    On Error GoTo 0
    
    ' Store handle
    SetVIHandle address, viHandle
    
    If MV_GPIBDebug Then MV_Log "[VISA] Device at address " & CStr(address) & " opened (handle=" & CStr(viHandle) & ")"
    
    VISA_OpenDevice = True
End Function

Public Sub MV_SetDebugMode(ByVal enabled As Boolean)
    MV_GPIBDebug = enabled
    If enabled Then
        MV_Log "[GPIB] Debug logging ON"
    Else
        MV_Log "[GPIB] Debug logging OFF"
    End If
End Sub

Public Function MV_GPIB_Connect(ByVal resource As String, ByRef deviceKey As String) As Boolean
    Dim address As Integer
    Dim viHandle As Long
    Dim timeout_ms As Long

    If Trim$(resource) = "" Then
        MV_SetError "GPIB connect failed: empty resource"
        MV_GPIB_Connect = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(resource, address) Then
        MV_SetError "GPIB connect failed: invalid address format: " & resource
        MV_GPIB_Connect = False
        Exit Function
    End If

    ' Convert timeout from seconds to milliseconds
    timeout_ms = CLng(MV_GPIB_TIMEOUT_S * 1000)

    If VISA_OpenDevice(resource, timeout_ms, viHandle) Then
        deviceKey = CStr(address)
        If MV_GPIBDebug Then MV_Log "[GPIB] Connected to address " & CStr(address)
        MV_GPIB_Connect = True
    Else
        deviceKey = ""
        MV_GPIB_Connect = False
    End If
End Function

' Issue a GPIB Selective Device Clear (SDC) to flush both the instrument input and
' output queues without resetting settings.  Use before a critical query when stale
' responses may be queued (e.g., after a timed-out OUTP? verification attempt).
Public Function MV_GPIB_Clear(ByVal deviceKey As String) As Boolean
    Dim address As Integer
    Dim viHandle As Long
    Dim status As Long

    If Trim$(deviceKey) = "" Then
        MV_GPIB_Clear = False
        Exit Function
    End If
    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_GPIB_Clear = False
        Exit Function
    End If
    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_GPIB_Clear = False
        Exit Function
    End If
    On Error Resume Next
    status = viClear(viHandle)
    On Error GoTo 0
    MV_GPIB_Clear = VISA_StatusIsSuccess(status)
End Function

Public Function MV_GPIB_Write(ByVal deviceKey As String, ByVal cmd As String) As Boolean
    Dim attempt As Integer
    Dim lastErr As String
    Dim address As Integer
    Dim viHandle As Long
    Dim status As Long
    Dim retCount As Long
    Dim fullCmd As String

    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB write failed: device is not connected"
        MV_GPIB_Write = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB write failed: invalid device address: " & deviceKey
        MV_GPIB_Write = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB write failed: device handle not found for address " & CStr(address)
        MV_GPIB_Write = False
        Exit Function
    End If

    If MV_GPIBDebug Then MV_Log "[GPIB][W] " & cmd

    fullCmd = cmd & vbLf
    
    For attempt = 1 To MV_GPIB_RETRY_COUNT
        On Error Resume Next
        status = viWrite(viHandle, fullCmd, Len(fullCmd), retCount)
        On Error GoTo 0
        
        If VISA_StatusIsSuccess(status) Then
            MV_GPIB_Write = True
            Exit Function
        End If
        
        lastErr = "viWrite returned " & CStr(status)
        If MV_GPIBDebug Then MV_Log "[GPIB][W][retry " & CStr(attempt) & "] " & lastErr
        MV_WaitSeconds 0.01
        DoEvents
    Next

    MV_SetError "GPIB write failed after retries: " & cmd & " :: " & lastErr
    MV_GPIB_Write = False
End Function

Public Function MV_GPIB_Query(ByVal deviceKey As String, ByVal cmd As String, ByRef outText As String) As Boolean
    Dim attempt As Integer
    Dim lastErr As String
    Dim address As Integer
    Dim viHandle As Long
    Dim status As Long
    Dim retCount As Long
    Dim fullCmd As String
    Dim readErr As String
    
    outText = ""
    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB query failed: device is not connected"
        MV_GPIB_Query = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB query failed: invalid device address: " & deviceKey
        MV_GPIB_Query = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB query failed: device handle not found for address " & CStr(address)
        MV_GPIB_Query = False
        Exit Function
    End If

    If MV_GPIBDebug Then MV_Log "[GPIB][Q] " & cmd

    fullCmd = cmd & vbLf

    ' Disabled by default: unconditional pre-query reads can trigger Keithley -420
    ' (query unterminated) on some instruments/backends.
    If MV_GPIB_ENABLE_PREQUERY_DRAIN Then
        If Not MV_GPIB_DrainPendingRead(viHandle) Then
            MV_SetError "GPIB query failed: unable to drain pending read buffer"
            MV_GPIB_Query = False
            Exit Function
        End If
    End If

    ' Write the command ONCE.  Retrying viWrite when the read timed out would
    ' re-queue a second response on the instrument, causing the next query to
    ' consume stale data (the well-known double-send corruption).
    Dim writeOk As Boolean
    writeOk = False
    For attempt = 1 To MV_GPIB_RETRY_COUNT
        On Error Resume Next
        status = viWrite(viHandle, fullCmd, Len(fullCmd), retCount)
        On Error GoTo 0
        If VISA_StatusIsSuccess(status) Then
            writeOk = True
            Exit For
        End If
        lastErr = "viWrite returned " & CStr(status)
        If MV_GPIBDebug Then MV_Log "[GPIB][Q][write retry " & CStr(attempt) & "] " & lastErr
        MV_WaitSeconds 0.01
        DoEvents
    Next

    If Not writeOk Then
        MV_SetError "GPIB query write failed: " & cmd & " :: " & lastErr
        MV_GPIB_Query = False
        Exit Function
    End If

    ' Retry reads only — never re-issue the write.
    For attempt = 1 To MV_GPIB_RETRY_COUNT
        MV_WaitSeconds 0.01
        If MV_GPIB_ReadLineFromHandle(viHandle, outText, readErr) Then
            If MV_GPIBDebug Then MV_Log "[GPIB][R] " & outText
            MV_GPIB_Query = True
            Exit Function
        End If
        lastErr = readErr
        If MV_GPIBDebug Then MV_Log "[GPIB][Q][read retry " & CStr(attempt) & "] " & lastErr
        outText = ""
        DoEvents
    Next

    MV_SetError "GPIB query failed after retries: " & cmd & " :: " & lastErr
    MV_GPIB_Query = False
End Function

Public Function MV_GPIB_Read(ByVal deviceKey As String, ByRef outText As String) As Boolean
    Dim address As Integer
    Dim viHandle As Long
    Dim readErr As String

    outText = ""
    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB read failed: device is not connected"
        MV_GPIB_Read = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB read failed: invalid device address: " & deviceKey
        MV_GPIB_Read = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB read failed: device handle not found for address " & CStr(address)
        MV_GPIB_Read = False
        Exit Function
    End If

    If MV_GPIB_ReadLineFromHandle(viHandle, outText, readErr) Then
        MV_GPIB_Read = True
    Else
        outText = ""
        MV_SetError "GPIB read failed: " & readErr
        MV_GPIB_Read = False
    End If
End Function

Public Function MV_GPIB_DrainDeviceReadBuffer(ByVal deviceKey As String) As Boolean
    Dim address As Integer
    Dim viHandle As Long

    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB drain failed: device is not connected"
        MV_GPIB_DrainDeviceReadBuffer = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB drain failed: invalid device address: " & deviceKey
        MV_GPIB_DrainDeviceReadBuffer = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB drain failed: device handle not found for address " & CStr(address)
        MV_GPIB_DrainDeviceReadBuffer = False
        Exit Function
    End If

    MV_GPIB_DrainDeviceReadBuffer = MV_GPIB_DrainPendingRead(viHandle)
End Function

Public Function MV_GPIB_WaitForMeasure(ByVal deviceKey As String, ByVal timeout_s As Double) As Boolean
    ' Note: VISA32 doesn't have a direct equivalent to MultiVu.GPIB.WaitForMeasure.
    ' This implementation performs a simple wait. For robust measurement synchronization,
    ' consider using query-based polling or instrument-specific wait commands.
    
    Dim address As Integer
    Dim viHandle As Long

    If Trim$(deviceKey) = "" Then
        MV_SetError "GPIB wait failed: device is not connected"
        MV_GPIB_WaitForMeasure = False
        Exit Function
    End If

    If Not MV_GPIB_ParseAddress(deviceKey, address) Then
        MV_SetError "GPIB wait failed: invalid device address: " & deviceKey
        MV_GPIB_WaitForMeasure = False
        Exit Function
    End If

    viHandle = GetVIHandle(address)
    If viHandle = 0 Then
        MV_SetError "GPIB wait failed: device handle not found for address " & CStr(address)
        MV_GPIB_WaitForMeasure = False
        Exit Function
    End If

    ' Simple timeout-based wait (VISA32 doesn't provide event-based measurement wait)
    ' For K2600/K2450 with integration time (NPLC), actual measurement time is:
    ' time_ms = NPLC * (20ms @ 50Hz or 16.67ms @ 60Hz)
    ' Recommend using query-based synchronization for critical measurements.
    
    If MV_GPIBDebug Then MV_Log "[GPIB] WaitForMeasure: waiting " & CStr(timeout_s) & "s for address " & CStr(address)
    
    MV_WaitSeconds timeout_s
    MV_GPIB_WaitForMeasure = True
End Function

Public Sub MV_GPIB_Disconnect(ByRef deviceKey As String)
    Dim address As Integer
    Dim viHandle As Long
    Dim status As Long
    
    If Trim$(deviceKey) = "" Then
        Exit Sub
    End If
    
    If MV_GPIB_ParseAddress(deviceKey, address) Then
        viHandle = GetVIHandle(address)
        If viHandle <> 0 Then
            On Error Resume Next
            status = viClose(viHandle)
            On Error GoTo 0
            
            SetVIHandle address, 0
            If MV_GPIBDebug Then MV_Log "[VISA] Device at address " & CStr(address) & " closed"
        End If
    End If
    
    deviceKey = ""
End Sub

Public Sub MV_GPIB_CloseAll()
    Dim status As Long
    
    ' Close K2600 device
    If K2600_VIHandle <> 0 Then
        On Error Resume Next
        status = viClose(K2600_VIHandle)
        On Error GoTo 0
        K2600_VIHandle = 0
        If MV_GPIBDebug Then MV_Log "[VISA] K2600 device (address 26) closed"
    End If
    
    ' Close K2450 device
    If K2450_VIHandle <> 0 Then
        On Error Resume Next
        status = viClose(K2450_VIHandle)
        On Error GoTo 0
        K2450_VIHandle = 0
        If MV_GPIBDebug Then MV_Log "[VISA] K2450 device (address 18) closed"
    End If
    
    ' Close Resource Manager
    If VISA_Initialized And rmSession <> 0 Then
        On Error Resume Next
        status = viClose(rmSession)
        On Error GoTo 0
        rmSession = 0
        VISA_Initialized = False
        If MV_GPIBDebug Then MV_Log "[VISA] Resource Manager closed"
    End If
    
    ' Clear device keys
    MV_K2600_Device = ""
    MV_K2450_Device = ""
End Sub

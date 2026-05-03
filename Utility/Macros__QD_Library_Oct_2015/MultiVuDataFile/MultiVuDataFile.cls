VERSION 1.0 CLASS
BEGIN
  MultiUse = -1 'True
END
Attribute VB_PredeclaredId = False
Attribute VB_Creatable = True
Attribute VB_Exposed = False
Attribute VB_GlobalNameSpace = False
Attribute VB_Name = "MultiVuDataFile"
'#Language "WWB-COM"
'#Uses "DataColumn.cls"
'#Uses "..\Utils\Utils.obm"
'MultiVuDataFile.cls
'Customer release class

'(Better) class for creation and writing of MultiVu data files
' *
' * (c) 2013 - Quantum Design, Inc.

Private Const REVISION = "$Rev: 33918 $"
Private Const SVN_ID = "$Id: MultiVuDataFile.cls 33918 2013-10-14 16:55:24Z dhurt $"

Enum TScaleType
	mvLinearScale
	mvLogScale
End Enum

Enum TStartupAxisType
	mvStartupAxisNone = &h0
	mvStartupAxisX = &h1
	mvStartupAxisY1 = &h2
	mvStartupAxisY2 = &h4
	mvStartupAxisY3 = &h8
	mvStartupAxisY4 = &h10
End Enum


Dim ColumnList() As Variant
Dim FN As Integer  'file handle
Dim FNS As String 'file name
Dim HaveWrittenHeader As Boolean
Dim KeepFileOpen As Boolean

Const CommentCol As String = "Comment"
Const TimeCol As String = "Time Stamp (sec)"

Private Sub Class_Initialize()
	'Make it so that we can add columns
	HaveWrittenHeader = False
	KeepFileOpen = False

	'Add default columns
	AddColumn(CommentCol)
	AddColumn(TimeCol, mvStartupAxisX)
End Sub

Property Get Version() As Long
	If InStr( 1, REVISION, ":" ) > 0  Then
		Version = CLng(Split(REVISION,": ")(1))
	Else
		Version = -1
	End If
End Property

Public Function GetCommentCol() As String
	GetCommentCol = CommentCol
End Function

Public Sub BeginBatchWrite()
	If FN = 0 Then OpenFile
	KeepFileOpen = True
End Sub

Public Sub EndBatchWrite()
	KeepFileOpen = False
	CloseFile
End Sub

Public Function GetTimeCol() As String
	GetTimeCol = TimeCol
End Function

'public function to create the file
Private Function CreateFile(FileName As String) As Boolean
	' make sure we have the folder which is supposed to hold the file in question
	If ( InStr(FileName,"\") <> 0 ) Then Utils.CreateFolderHierarchy(Left(FileName,InStrRev(FileName,"\")-1))

	FNS = FileName

	'open the file, which will create it if it doesn't already exist
	OpenFile

	'return FALSE if file already existed, TRUE if this was a new creation
	If LOF(FN) = 0 Then
		CreateFile = True
	Else
		CreateFile = False
	End If

	CloseFile
End Function

'private function to open the file
Private Sub OpenFile()
	FN = FreeFile
	Open FNS For Append As #FN
End Sub

'private function to close the file
'you should do this after every write to the file to make windows flush the buffer!
Private Sub CloseFile()
	If FN <> 0 Then Close #FN
	FN = 0
End Sub

'private function for writing a line without opening and closing the file
Private Sub QuickWrite(LineS As String)
	Print #FN, LineS
End Sub

'function to ask MVU to open the file
Public Sub OpenInMultiVu()
	MultiVu.DisplayGraph(0, FNS) 'not sure what the zero is for, but it seems to be the default
End Sub

Public Function FileName()
	FileName = FNS
End Function


'Function to add an column to the data file. Don't do this after you've written the header
Public Function AddColumn (Label As String, Optional StartupAxis As TStartupAxisType = mvStartupAxisNone, Optional ScaleType As TScaleType = mvLinearScale, Optional Persistent As Boolean = False)
	Dim i As Integer

	If HaveWrittenHeader <> False Then
		Debug.Print("Not adding column '" & Label & "' because header has already been written to file " & FNS & ".")
		Exit Function
	End If

	Dim dc As New DataColumn
	dc.Label = Label

	dc.ScaleType = mvStartupAxisNone

	If ( (StartupAxis And mvStartupAxisX) = mvStartupAxisX) Then
		'Unset all others because we can have only one x-axis
		For i = 0 To UBound(ColumnList)
			If ColumnList(i).StartupAxis And mvStartupAxisX = mvStartupAxisX Then
				ColumnList(i).StartupAxis = ColumnList(i).StartupAxis And (&hFFFFFFFF - mvStartupAxisX)
				'Debug.Print(i & " " & ColumnList(i).StartupAxis)
			End If
		Next
	End If

	'Set the startup axes to the requested values (can be anded for multiple axes per column)
	dc.StartupAxis = StartupAxis

	dc.ScaleType = ScaleType

	dc.Persistent = Persistent
	dc.IsFresh = False
	dc.Value = Utils.NaN()

	AddItemToArray(ColumnList, dc)
End Function

'Function to add multiple data columns (without specifying options) at once
Public Function AddMultipleColumns (ParamArray ColumnNames() As Variant)
	Dim i As Integer
	For i = LBound(ColumnNames) To UBound(ColumnNames)
		AddColumn(ColumnNames(i))
	Next i
End Function

Public Function CreateFileAndWriteHeader(FileName As String, Title As String, Optional ByVal PlainHeaderText As String = "; Copyright 1997-2012, Quantum Design, Inc. All rights reserved.")
	Dim i As Integer
	Dim NumYAxesFound As Integer
	Dim TempString As String

	'Make sure we don't add any more columns after this
	HaveWrittenHeader = True

	'Create the file if it doesn't already exist
	'If it already exists, exit the function so we don't write the header again
	'If it does not already exist, write the header
	If Not CreateFile(FileName) Then Exit Function

	OpenFile

	'Standard header items
	QuickWrite("[Header]")
	QuickWrite(PlainHeaderText)
	QuickWrite("TITLE, " & Title)
	QuickWrite("DATATYPE, COMMENT," & ColumnForLabel(CommentCol) + 1)
	QuickWrite("DATATYPE, TIME," & ColumnForLabel(TimeCol) + 1)
	QuickWrite("BYAPP, MultiVuDataFile VBA class")

	'Find the first item that wants to be the x axis
	For i = 0 To UBound(ColumnList)
		If ( (ColumnList(i).StartupAxis And mvStartupAxisX) = mvStartupAxisX) Then
			QuickWrite("STARTUPAXIS, X, " & i+1 & ", " & ScaleTypeString(ColumnList(i).ScaleType) & ", AUTO")
			Exit For
		End If
	Next i

	'Find up to four items that want to be y-axes
	NumYAxesFound = 0
	For i = 0 To UBound(ColumnList)
		If ( (ColumnList(i).StartupAxis And mvStartupAxisY1) = mvStartupAxisY1) Then
			NumYAxesFound = NumYAxesFound + 1
			QuickWrite("STARTUPAXIS, Y1" & ", " & i+1 & ", " & ScaleTypeString(ColumnList(i).ScaleType) & ", AUTO")
			If NumYAxesFound >=4 Then Exit For 'We've got 4 y-axes, so it's time to stop looking for more
		End If

		If ( (ColumnList(i).StartupAxis And mvStartupAxisY2) = mvStartupAxisY2) Then
			NumYAxesFound = NumYAxesFound + 1
			QuickWrite("STARTUPAXIS, Y2" & ", " & i+1 & ", " & ScaleTypeString(ColumnList(i).ScaleType) & ", AUTO")
			If NumYAxesFound >=4 Then Exit For 'We've got 4 y-axes, so it's time to stop looking for more
		End If

		If ( (ColumnList(i).StartupAxis And mvStartupAxisY3) = mvStartupAxisY3) Then
			NumYAxesFound = NumYAxesFound + 1
			QuickWrite("STARTUPAXIS, Y3" & ", " & i+1 & ", " & ScaleTypeString(ColumnList(i).ScaleType) & ", AUTO")
			If NumYAxesFound >=4 Then Exit For 'We've got 4 y-axes, so it's time to stop looking for more
		End If

		If ( (ColumnList(i).StartupAxis And mvStartupAxisY4) = mvStartupAxisY4) Then
			NumYAxesFound = NumYAxesFound + 1
			QuickWrite("STARTUPAXIS, Y4" & ", " & i+1 & ", " & ScaleTypeString(ColumnList(i).ScaleType) & ", AUTO")
			If NumYAxesFound >=4 Then Exit For 'We've got 4 y-axes, so it's time to stop looking for more
		End If
	Next i

	QuickWrite("[Data]")

	'Write out the column headers
	TempString = ""
	For i = 0 To UBound(ColumnList) - 1
		TempString = TempString & ColumnList(i).Label & ","
	Next
	'Last column header gets no comma afterward
	TempString = TempString & ColumnList(UBound(ColumnList)).Label
	QuickWrite(TempString)

	CloseFile
End Function

Private Function ColumnForLabel(ColumnLabel As String) As Integer
	Dim i As Integer

	ColumnForLabel = -1

	For i = 0 To UBound(ColumnList)
		If ColumnList(i).Label = ColumnLabel Then
			ColumnForLabel = i
			Exit Function
		End If
	Next
End Function

Private Function ScaleTypeString(ScaleType As TScaleType) As String
	ScaleTypeString = "LINEAR" 'Default
	If ScaleType = mvLogScale Then ScaleTypeString = "LOG"
End Function




Public Function SetValue(columnlabel As String, Value As Variant)
	Dim i As Integer

	i = ColumnForLabel(columnlabel)
	If i = -1 Then
		'If we get here, ColumnLabel was not found.
		Debug.Print("Error writing value '" & Value & "' to column '" & columnlabel & "'. Column not found.")
	Else
		'Otherwise, record the value and set it fresh
		ColumnList(i).Value = Value
		ColumnList(i).IsFresh = True
	End If

End Function

Public Function GetValue(columnlabel As String) As Variant
	Dim i As Integer

	i = ColumnForLabel(columnlabel)
	If i = -1 Then
		'If we get here, ColumnLabel was not found
		GetValue = Utils.NaN(vbSingle)
		Debug.Print("Error getting value from column '" & columnlabel & "'. Column not found.")
	Else
		GetValue = ColumnList(i).Value
	End If
End Function

Public Function GetFreshStatus(columnlabel As String) As Variant
	Dim i As Integer

	i = ColumnForLabel(columnlabel)
	If i = -1 Then
		'If we get here, ColumnLabel was not found
		GetFreshStatus = False
		Debug.Print("Error getting value from column '" & columnlabel & "'. Column not found.")
	Else
		GetFreshStatus = ColumnList(i).IsFresh
	End If
End Function

Public Function WriteData(Optional GetTimeNow As Boolean = True)
	Dim i As Integer
	Dim LastCol As Integer
	Dim TempString As String

	If GetTimeNow Then SetValue(TimeCol, Utils.GetTimeStamp())

	TempString = ""
	LastCol = UBound(ColumnList)
	For i = 0 To LastCol
		'Add the next data column to the output string if there is valid data present and it is (fresh or persistent)
		If ( ( Not Utils.isNaN(ColumnList(i).Value) ) And (ColumnList(i).Persistent Or ColumnList(i).IsFresh) ) Then
			TempString = TempString & ColumnList(i).Value
		End If

		'Add a comma after the value if we are not at the end
		If i < LastCol Then TempString = TempString & ","

		'Indicate that data is no longer fresh
		ColumnList(i).IsFresh = False
	Next

	If KeepFileOpen Then
		If FN = 0 Then OpenFile
		QuickWrite(TempString)
	Else
		OpenFile
		QuickWrite(TempString)
		CloseFile
	End If
End Function

'Function to set values form array and then write them to data file
'Format of array is ColLabel1, Value1, ColLabel2, Value2, ...
'Array() can contain values for all columns or a subset of columns, in any order
Public Function WriteDataUsingArray(Array() As Variant, Optional GetTimeNow As Boolean = True)
	Dim i As Integer
	Dim j As Integer
	Dim NumEntries As Integer

	j = UBound(Array)
	j = LBound(Array)

	NumEntries = UBound(Array) - LBound(Array) + 1

	If ( (NumEntries Mod 2) <> 0) Then
		Debug.Print("Error in WriteDataUsingArray(). Array() contains " & NumEntries & " entries. It should contain an even number of entries")
		Exit Function
	End If

	For i = LBound(Array) To UBound(Array)-1 Step 2
		SetValue(Array(i), Array(i+1))
	Next i

	WriteData(GetTimeNow)
End Function


Private Function AddItemToArray(ArrayToAppendTo() As Variant, ItemToAdd As Variant)
	Dim n As Integer
	If IsArrayAllocated(ArrayToAppendTo) Then
		n = UBound(ArrayToAppendTo)
		ReDim Preserve ArrayToAppendTo(0 To n+1)
		Set ArrayToAppendTo(n+1) = ItemToAdd
	Else
		ReDim ArrayToAppendTo(0 To 0)
		Set ArrayToAppendTo(0) = ItemToAdd
	End If
End Function

Private Function IsArrayAllocated(ArrayToTest() As Variant) As Boolean
	Dim n As Long 'dummy

	IsArrayAllocated = False 'Default return

	'Make sure we don't hang if an error occurs
	On Error Resume Next

	'If ArrayToTest is not even an array, return false
	If (IsArray(ArrayToTest) = False) Then
		IsArrayAllocated = False
		Exit Function
	End If

	'Find upper bound of array. If this fails, the array is not allocated
	n = UBound(ArrayToTest, 1)
	If (Err.Number = 0) Then
		' Under some circumstances, if an array
		' is not allocated, Err.Number will be
		' 0. To acccomodate this case, we test
		' whether LBound <= Ubound. If this
		' is True, the array is allocated. Otherwise,
		' the array is not allocated.
		If LBound(ArrayToTest) <= UBound(ArrayToTest) Then
			' no error. array has been allocated.
			IsArrayAllocated = True
		Else
			IsArrayAllocated = False
		End If
		Else
			' error. unallocated array
			IsArrayAllocated = False
	End If
End Function

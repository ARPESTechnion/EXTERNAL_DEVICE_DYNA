'#Language "WWB-COM"
'#Uses "MultiVuDataFile.cls"

Option Explicit

Const TCol As String = "Temperature (K)"
Const TCalCol As String = "Cal Temp (K)"
Const TErrCol As String = "T Err (%)"
Const FCol As String = "Field (Oe)"
Const PCol As String = "Pressure (Torr)"
Const TAvgCol As String = "Avg Temp (K)"

Sub Main
	Debug.Clear
	Dim i As Integer
	Dim AvgCnt As Integer
	Dim TAvg As Single
	Dim F As New MultiVuDataFile

	Wait(2)

	'Set up the columns that you would like to write to file
	'The Label strings are used both as column headers and to access these columns programmatically (like key-value coding)
	'You can add axis types if you want a column to be used for multiple axes:
	'F.AddColumn(TCol, mvStartupAxisX + mvStartupAxisY1)
	F.AddColumn(TCol, mvStartupAxisY1, mvLogScale)
	F.AddColumn(TAvgCol, mvStartupAxisNone, mvLinearScale, False)
	F.AddColumn(TCalCol, mvStartupAxisY1, mvLogScale)
	F.AddColumn(TErrCol, mvStartupAxisY2)
	F.AddColumn(FCol, mvStartupAxisY3)
	F.AddColumn(PCol, mvStartupAxisY4) 'This will not actually be set as Y4 if there are 4 other y-columns before it

	'Create the file and write the header.
	'If the file exists, this will do nothing.
	'Be sure that all of your columns are the same as the existing file if you are appending!
	F.CreateFileAndWriteHeader("c:/test.dat", "Test Data File")

	'You should not add columns after creating the file. The class won't let you, and will print out an error.
	F.AddColumn("Won't be added")

	'Open the file for viewing in MultiVu
	F.OpenInMultiVu()

	'These values are not set every time before F.WriteData(), so they will appear only once unless the column is set persistent in F.AddColumn()
	F.SetValue(F.GetCommentCol(), "Hello!")

	AvgCnt = 0
	TAvg = 0
	For i = 1 To 50
		'Set values to record them in the class
		F.SetValue(TCol, 2*i)
		F.SetValue(TCalCol, 2*i* (1+i/100))
		'You can use GetValue to read back a previously set value for math
		F.SetValue(TErrCol, (1 - F.GetValue(TCol)/F.GetValue(TCalCol))*100)
		F.SetValue(FCol, 1000.0 + 10*i)
		F.SetValue(PCol, 5.0)
		'Because of the possibility of mistyping, it is recommended that you use constants for column labels
		F.SetValue("Mistyped Column", 1.234)

		'Calculate average temperature
		'As long as TAvgCol is not set to persistent, we will get entries in the data file for this only once very 10 rows
		TAvg = TAvg + F.GetValue(TCol)
		AvgCnt = AvgCnt + 1
		If AvgCnt = 10 Then
			F.SetValue(TAvgCol, TAvg/10)
			AvgCnt = 0
			TAvg = 0
		End If

		'Write out the current values to the file. This creates one row.
		F.WriteData()

		Wait(0.1)
	Next i

	'You can also write data compactly using an array:
	Dim MyData(1 To 8) As Variant
	MyData(1) = TCol
	MyData(2) = 100.0
	MyData(3) = TCalCol
	MyData(4) = 99.9
	MyData(5) = FCol
	MyData(6) = 1000.0
	MyData(7) = "Oops"
	MyData(8) = 1.2345
	F.WriteDataUsingArray(MyData)
End Sub

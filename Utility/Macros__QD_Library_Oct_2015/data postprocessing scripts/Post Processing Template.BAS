'#Language "WWB-COM"
'Scripted by John Hamilton for QD Apps.


' This script calculates the slope from the high field saturation and subtracts it from the data set.

Option Explicit

Sub Main


	'===========================================Declare and Define Variables================================================

	Dim inputFilePath As String
	Dim outputFilePath As String
	Dim elementString() As String
	Dim inputLine As String
	Dim isData As Boolean
	Dim i As Integer
	Dim y() As Double
	ReDim Preserve y(0)
	Dim x() As Double
	ReDim Preserve x(0)

	Dim Index1 As Integer			'The column index of your x-values (usually field (3))
	Dim Index2 As Integer			'The column index of your y-values (usually moment (varies depending on data aquisition)

	isData=False





'====================Select Files===================================================='
	MsgBox("Select your input data file")
	inputFilePath = GetFilePath(,"dat",,"Select your data file",0)
	If inputFilePath="" Then
		MsgBox("User canceled: Exiting")
		Exit All
	End If

	MultiVu.DisplayGraph(0,inputFilePath)
	OutPutFile:
	MsgBox("Select or create your output data file")
	outputFilePath = GetFilePath(,"dat",,"Select or create your output file",3)
	If outputFilePath="" Then
		MsgBox("User canceled: Exiting")
		Exit All
	End If

	If StrComp(inputFilePath,outputFilePath,1)=0 Then
		MsgBox"Error: Input and Output Files cannot be the same"
		GoTo OutPutFile
	End If

	Open inputFilePath For Input As #1

'================================================Load Data============================================================

	Open inputFilePath For Input As #1

	i = 0

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If isData Then
				ReDim Preserve x(UBound(x)+1)			'Expand the dimentions to fit the number of data points
				ReDim Preserve y(UBound(y)+1)
				x(i) = Val(elementString(Index1)) 			'your x values
				y(i) = Val(elementString(Index2)) 			'your y values
				i = i + 1

		End If
		If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then	'Indicates the next line to be data points
			isData = True
		End If

	Loop
	Close #1



'==========================================================================================================================
'============================================Your computations go here=====================================================
'==========================================================================================================================






	'=======================================================================================================================
	'=======================================Writes New Data to File=========================================================
	'=======================================================================================================================
	i=0
	Open inputFilePath For Input As #1
	Open outputFilePath For Output As #2
	isData=False
	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")

			If isData Then
				'if it's a data row, go in and print the original data as well as your corrected data to this line

				Print #2, inputLine;",";CStr(Calc1);",";CStr(Calc2)	'you can add more!
				i=i+1
			End If

		    If isData=False Then
			    If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					Print #2,inputLine; "," ;"Column Header for Calc1"; "," ;"Column Header for Calc2"	'you can add more!
					isData = True
					End If
				Else
					'if it is not a data row, do nothing and copy the line directly to new output file
					Print #2, inputLine
				End If
			End If

	Loop
	Close #1
	Close #2


	'Display result on a graph
	MultiVu.DisplayGraph(0,outputFilePath)


End Sub

'#Language "WWB-COM"
'Scripted by John Hamilton for QD Apps.


'	This script is for low field correction in combination with a GGG data set taken in the same maner'
'	The script follows a data proceedure of high field to low and back (i.e. +100 Oe -> -100 Oe -> +100 Oe).

'	The user will be prompted to select THREE files. The first is you GGG data set, the second
'	will be the data set you wish to apply the correction to, and the third will be the outputed
'	file with the corrections implemented in a new column.


Option Explicit


Sub Main
	On Error GoTo InputWindow


	'=======================================================================================================================
	'===========================================Declare and Define Variables================================================
	'=======================================================================================================================

	Dim elementString() As String
	Dim inputLine As String
	Dim inputFilePath1 As String
	Dim inputFilePath2 As String
	Dim outputFilePath1 As String
	Dim i As Integer
	Dim isData As Boolean
	Dim y2() As Double
	ReDim Preserve y2(0)
	Dim x2() As Double
	ReDim Preserve x2(0)
	Dim y3() As Double
	ReDim Preserve y3(0)
	Dim x3() As Double
	ReDim Preserve x3(0)
	Dim y() As Double
	ReDim Preserve y(0)
	Dim x() As Double
	ReDim Preserve x(0)
	Dim Adjustment As Double
	Dim Adjustment2 As Double
	Dim moment As Double
	Dim field As Double
	Dim PartOfFile As Integer
	Dim ListArray() As String
	Dim index As Integer




	InputWindow:
	'===================================================Error Trap==========================================================

	If Err.Number <> 0 Then
		If Err.Description = "User pressed cancel." Then
			MsgBox("User canceled: Exiting")
			Exit All
		End If
		MsgBox("Error: " + Err.Description)
		Err.Clear
		Exit All
	End If


	'================================================Information Box========================================================

	MsgBox"This Script Will Extract a Field Correction from a GGG Sample Data Run and Apply it to Another Data Sample."


	'=======================================================================================================================
	'========================================File Designations==============================================================
	'=======================================================================================================================

	MsgBox("Select your GGG data file.")
	inputFilePath1 = GetFilePath(,"dat",,"Select your data file",0)
	If inputFilePath1="" Then
		MsgBox("User canceled: Exiting")
		Exit All
	End If

	MultiVu.DisplayGraph(0,inputFilePath1)

	Open inputFilePath1 For Input As #1
	i = 0
	ReDim ListArray(1)

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then	'Indicates the next line to be data points
			ReDim ListArray(UBound(elementString))
			For i=0 To UBound(elementString)
				ListArray(i)=CStr(elementString(i))
			Next
		End If

	Loop
	Close #1

	MsgBox("Select the data file you want to apply the correction to.")
	inputFilePath2 = GetFilePath(,"dat",,"Select your data file",0)
	If inputFilePath2="" Then
		MsgBox("User canceled: Exiting")
		Exit All
	End If

	OutPutFile:
	MsgBox("Select or create your output data file")
	outputFilePath1 = GetFilePath(,"dat",,"Select or create your output file",1)
	If outputFilePath1="" Then
		MsgBox("User canceled: Exiting")
		Exit All
	End If


	If StrComp(inputFilePath1,outputFilePath1,1)=0 Or StrComp(inputFilePath2,outputFilePath1,1)=0 Then
		MsgBox"Error: Input and Output Files cannot be the same"
		GoTo OutPutFile
	End If


	Begin Dialog UserDialog 380,182 ' %GRID:10,7,1,1
		OKButton 40,126,130,28
		CancelButton 210,126,130,28
		DropListBox 70,49,210,42,ListArray(),.SelectMoment
		Text 80,21,210,14,"Select moment (Y-axis)",.Text7,2
	End Dialog
	Dim dlg As UserDialog
	Dialog dlg

	index=CInt(dlg.SelectMoment)
	'=======================================================================================================================
	'=====Open the data file and scan the file line by line. Each line is stored in a string variable called inputLine======
	'=====Split inputLine into columns by finding commam and store them into the elementString() with index starts at 0=====
	'=======================================================================================================================

	Open inputFilePath1 For Input As #1

	i = 0
	PartOfFile=0
	isData=False

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If isData Then
			If PartOfFile=0 Then
				If i<>0 Then
					If x(i-1)<Val(elementString(3))And Abs(Val(elementString(3)))>80 Then		'This indicates the first turn
						PartOfFile=1
						i=0
					End If
				End If
			End If

			Select Case PartOfFile
				Case 0										'First sweep
					ReDim Preserve x(UBound(x)+1)			'Expand the dimentions to fit the number of data points
					ReDim Preserve y(UBound(y)+1)
					x(i) = Val(elementString(3)) 			'Field
					y(i) = Val(elementString(index)) 			'Moment
					i = i + 1
				Case 1										'Second Sweep
					ReDim Preserve x2(UBound(x2)+1)			'Expand the dimentions to fit the number of data points
					ReDim Preserve y2(UBound(y2)+1)
					x2(i) = Val(elementString(3)) 			'Field
					y2(i) = Val(elementString(index)) 			'Moment
					i = i + 1
			End Select
		End If
		If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then	'Indicates the next line to be data points
			isData = True
		End If
	Loop
	Close #1


	'================================================Calculations==========================================================

	Adjustment=AdjCalc(x(),y())							'Calculate Adjustment for first sweep
	Adjustment2=AdjCalc(x2(),y2())						'Calculate Adjustment for second sweep


	'=======================================================================================================================
	'======================================Write the Output to a new file===================================================
	'=======================================================================================================================

	Open inputFilePath2 For Input As #1
	Open outputFilePath1 For Output As #2

	isData = False
	field=0
	i=0
	PartOfFile=0

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If isData Then
			If field<>0 Then
				If Val(elementString(3))>field And PartOfFile=0 And Val(elementString(3))<=(-80) Then
					PartOfFile=1
				ElseIf Val(elementString(3))<field And PartOfFile=1  And Val(elementString(3))>=(80) Then
					PartOfFile=2
				End If
			End If
			Select Case PartOfFile
				Case 0
					field= Val(elementString(3))				'Convert string to numerical value'
					moment = Val(elementString(index))
					Print #2, inputLine;"," ;CStr(field+Adjustment); "," ;CStr(Adjustment)		'(100-Abs(field))/100)
				Case 1
					field= Val(elementString(3))
					moment = Val(elementString(index))
					Print #2, inputLine;"," ;CStr(field+Adjustment2); "," ;CStr(Adjustment2)
			End Select
		End If
	    If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
	    	'if the first word of the line is "comment", turn on isData and put two extra columns
			Print #2,inputLine; "," ;"H_corrected (Oe)"; "," ;"Ave"
			isData = True
		Else
			'if it is not a data row, do nothing and copy the line directly to new output file
			Print #2, inputLine
		End If
	Loop
	Close #1
	Close #2
	MultiVu.DisplayGraph(0,outputFilePath1)

End Sub
Function AdjCalc(ByVal x() As Double ,ByVal y() As Double) As Double

	'=======================================================================================================================
	'========================================Calculates the Field Correction================================================
	'=======================================================================================================================

	Dim slope As Double

	slope=FindSlope(x(),y())
	AdjCalc=FindIntercept(x(),y(),slope)/slope

End Function

Function FindIntercept(ByVal x() As Double ,ByVal y() As Double,ByVal slope As Double) As Double

	'=======================================================================================================================
	'========================================Calculates the Y-Intercept=====================================================
	'=======================================================================================================================

	Dim Intercept1 As Double
	Dim Intercept2 As Double
	Dim i As Integer

	For i=1 To UBound(x)
		If x(i)*x(i-1)<0 Then						'Locates where there are two points on eitherside of the y-axis
			Intercept1=y(i-1)-slope*x(i-1)			'Caculats a projected y-intercept based on one of the two points selected
			Intercept2=y(i)-slope*x(i)				'Caculats a projected y-intercept based on the other point selected
		End If
		FindIntercept=((Intercept1+Intercept2)/2)	'Returns the average of the two y-intercepts
	Next

End Function

Function FindSlope(ByVal x() As Double ,ByVal y() As Double) As Double

	'=======================================================================================================================
	'========================================Calculates the Slope (Least Squares Method)====================================
	'=======================================================================================================================

	Dim i As Integer
	Dim slope As Double
	Dim Intercept As Double
	Dim sum_y As Double
	sum_y = 0
	Dim sum_x As Double
	sum_x = 0
	Dim sum_x2 As Double
	sum_x2 = 0
	Dim sum_xy As Double
	sum_xy = 0
	Dim x_avg As Double
	Dim y_avg As Double

	For i = 0 To UBound(x)-1
		sum_y = sum_y + y(i)
		sum_x = sum_x + x(i)
		sum_x2 = sum_x2 + (x(i)*x(i))
		sum_xy = sum_xy + (x(i)*y(i))
	Next i
	x_avg=sum_x/UBound(x)
	y_avg=sum_y/UBound(y)
	FindSlope=(UBound(y)*sum_xy - (sum_x*sum_y))/(UBound(y)*sum_x2 - sum_x*sum_x)

End Function

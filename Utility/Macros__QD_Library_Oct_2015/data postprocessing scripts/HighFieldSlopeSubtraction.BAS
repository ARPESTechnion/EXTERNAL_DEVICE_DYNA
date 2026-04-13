'#Language "WWB-COM"
'Scripted by John Hamilton for QD Apps.


' This script calculates the slope from the high field saturation and subtracts it from the data set.

Option Explicit


Dim Limit As Integer
Dim x_avg As Double
Dim y_avg As Double
Dim elementString() As String
Dim inputLine As String
Dim isData As Boolean
Dim moment As Double
Dim field As Double
Dim SmoothX() As Double
Dim SmoothY() As Double
Dim i As Integer



Sub Main
	On Error GoTo InputWindow


	'===========================================Declare and Define Variables================================================

	Dim inputFilePath As String
	Dim outputFilePath As String

	isData=False
	Dim y() As Double
	ReDim Preserve y(0)
	Dim x() As Double
	ReDim Preserve x(0)
	Dim slope As Double
	Dim MinField As Double
	Dim MaxField As Double
	Dim Accuracy As Integer
	Dim Index As Integer
	Dim AxisPrint As Boolean



	InputWindow:
	'===================================================Error Trap==========================================================

	If Err.Number <> 0 Then
		MsgBox("Error: " + Err.Description)
		Err.Clear
		Exit All
	End If


	'========================================File Designations==============================================================

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
	'================================================User Input=========================================================




	Begin Dialog UserDialog 380,385 ' %GRID:10,7,1,1
		OKButton 30,343,130,28
		CancelButton 220,343,130,28
		Text 10,21,370,56,"This Script Will Determine Slope From High Field Region and Produce a Data Set With the High Field Slope Removed.",.Text1
		TextBox 40,189,90,21,.FieldMin
		TextBox 220,189,110,21,.FieldMax
		Text 70,161,40,14,"From",.Text2
		Text 260,161,30,14,"To",.Text3
		CheckBox 90,301,190,14,"Apply Smooth Filter",.CheckBox1
		Text 50,98,290,28,"Input a high field region for determining the slope.",.Text10,2
		Text 140,196,30,14,"Oe",.Text11
		Text 340,196,30,14,"Oe",.Text12
		DropListBox 80,245,210,42,ListArray(),.SelectMoment
	End Dialog
	Dim dlg As UserDialog
	Dialog dlg

	MinField=CStr(dlg.FieldMin)
	MaxField=CStr(dlg.FieldMax)

	If MinField>MaxField Then
		slope=MinField
		MinField=MaxField
		MaxField=slope
	End If

	Index=CInt(dlg.SelectMoment)

'================================================Load Data============================================================

	Open inputFilePath For Input As #1

	i = 0

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If isData Then

				ReDim Preserve x(UBound(x)+1)			'Expand the dimentions to fit the number of data points
				ReDim Preserve y(UBound(y)+1)
				x(i) = Val(elementString(3)) 			'Field
				y(i) = Val(elementString(Index)) 			'Moment
				i = i + 1

		End If


		If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then	'Indicates the next line to be data points
			isData = True
		End If

	Loop
	Close #1





	If dlg.CheckBox1=1 Then

		Begin Dialog UserDialog 400,203 ' %GRID:10,7,1,1
			Text 80,21,230,63,"Please Enter An Integer Value for Moving Average Accuracy (i.e. a value of 5 will use the 2 values on either side of the data point to calculate the smoothed value).",.Text1
			TextBox 110,112,160,35,.TextBox1
			OKButton 60,161,110,28
			CancelButton 230,161,110,28
		End Dialog
		Dim dlg1 As UserDialog
		Dialog dlg1

		Accuracy=CInt(dlg1.TextBox1)
		Call SmoothFilter(x(),y(),Accuracy)
		slope=SlopeCalc(SmoothX(),SmoothY(),MinField,MaxField)
	Else
		slope=SlopeCalc(x(),y(),MinField,MaxField)
	End If




	'=======================================================================================================================
	'=======================================Writes New Data to File=========================================================
	'=======================================================================================================================
i=0

	Open inputFilePath For Input As #1
	Open outputFilePath For Output As #2
	isData=False
	AxisPrint=True
	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If dlg.CheckBox1=1 Then

			If isData Then
				'if it's a data row, go in and compute the Magnetic correction. Print the result to new file'

				field= SmoothX(i)
				moment = SmoothY(i)
				Print #2, inputLine;",";CStr(moment);",";CStr(moment-(field*slope));",";CStr(slope*field + y_avg - slope*x_avg)
				i=i+1
			End If

		    If isData=False Then
			    If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					Print #2,inputLine; "," ;"[HFSS]Smooth Moment (emu)"; "," ;"[HFSS] Smooth m - H * slope (emu)"; "," ; "[HFSS] Smooth Lin. Reg. Fit (emu)"
					isData = True
				ElseIf StrComp(elementString(LBound(elementString)),"STARTUPAXIS",1) = 0 Then
					If AxisPrint Then
						Print #2, "STARTUPAXIS,X,4"
						Print #2, "STARTUPAXIS,Y1,";CStr(Index+1)
						Print #2, "STARTUPAXIS,Y1,";CStr(UBound(ListArray)+4)
						Print #2, "STARTUPAXIS,Y2,";CStr(UBound(ListArray)+3)
						Print #2, "STARTUPAXIS,Y3,";CStr(UBound(ListArray)+2)
						AxisPrint=False
					End If
				Else
					'if it is not a data row, do nothing and copy the line directly to new output file
					Print #2, inputLine
				End If
			End If
		Else

			If isData Then
				'if it's a data row, go in and compute the Magnetic correction. Print the result to new file'
				field= Val(elementString(3))
				moment = Val(elementString(Index)) 'Convert string to numerical value'
				Print #2, inputLine;",";CStr(moment-(field*slope));",";CStr(slope*field + y_avg - slope*x_avg)
			End If

			If isData=False Then
		    	If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					Print #2,inputLine; "," ;"[HFSS] m - H * slope (emu)"; ","; "[HFSS] Lin. Reg. Fit (emu)"
					isData = True
				ElseIf StrComp(elementString(LBound(elementString)),"STARTUPAXIS",1) = 0 Then
					If AxisPrint Then
						Print #2, "STARTUPAXIS,X,4"
						Print #2, "STARTUPAXIS,Y1,";CStr(Index+1)
						Print #2, "STARTUPAXIS,Y1,";CStr(UBound(ListArray)+3)
						Print #2, "STARTUPAXIS,Y2,";CStr(UBound(ListArray)+2)
						AxisPrint=False
					End If
				Else
					'if it is not a data row, do nothing and copy the line directly to new output file
					Print #2, inputLine
				End If
			End If
		End If
	Loop
	Close #1
	Close #2


	'Display result on a graph
	MultiVu.DisplayGraph(0,outputFilePath)


End Sub
Function SlopeCalc(ByVal x() As Double, ByVal y() As Double,ByVal MinX As Double,ByVal MaxX As Double) As Double

	'=============================================Calculate Slope====================================================

	Dim sum_y As Double
	sum_y = 0
	Dim sum_x As Double
	sum_x = 0
	Dim sum_x2 As Double
	sum_x2 = 0
	Dim sum_xy As Double
	sum_xy = 0
	Dim n As Integer
	Dim temp As Double
	n=0

	If MinX>MaxX Then
		temp=MinX
		MinX=MaxX
		MaxX=temp
	End If
	For i = 0 To (UBound(x)-1)
		If x(i)>=MinX And x(i)<=MaxX Then
			sum_y = sum_y + y(i)
			sum_x = sum_x + x(i)
			sum_x2 = sum_x2 + (x(i)*x(i))
			sum_xy = sum_xy + (x(i)*y(i))
			n=n+1
		End If
	Next i
	x_avg=sum_x/n
	y_avg=sum_y/n
	SlopeCalc =((n*sum_xy - (sum_x*sum_y)))/(n*sum_x2 - sum_x*sum_x)
End Function
Sub SmoothFilter(ByVal x() As Double, ByVal y() As Double, Optional ByVal Accuracy As Integer)

	Dim n As Integer
	Dim Limit As Integer
	Dim z As Integer

	If Accuracy<1 Then
		Accuracy=1
	End If

	Limit=Accuracy/2

	ReDim Preserve SmoothX(UBound(x))
	ReDim Preserve SmoothY(UBound(x))

	For i=(0) To (UBound(x))

		SmoothX(i)=0
		SmoothY(i)=0
		z=0
		For n=0 To 2*Limit
			If i+n>=Limit Then
				If i+n-Limit<=(UBound(x)-1)Then
					SmoothX(i)=SmoothX(i)+x(i+n-Limit)
					SmoothY(i)=SmoothY(i)+y(i+n-Limit)
					z=z+1
				End If
			End If
		Next n
		SmoothX(i)=(SmoothX(i)/z)
		SmoothY(i)=(SmoothY(i)/z)
	Next i
End Sub

'#Language "WWB-COM"
'Scripted by John Hamilton for QD Apps.


' This script is intended to ease the extrapolation of data from a simple hysteresis loop of ferromagnetic materials.
' It calculates:
' High Field Slope after saturation,
' Positive Saturation Moment (M_Sat_POS), Negative Saturation Moment (M_Sat_NEG), and Average Saturation moment (M_Sat_AVE).
' Then the high field slope is subtracted from the moment data, and
' if desired by user, the moment data is shifted To make M_sat_POS = M_sat_NEG (correcting For instrument offset typ. ~1e-6 emu),
' then we determine:
' Increasing field Coercivity (H_Coer_INC), Decreasing field Coercivity (H_Coer_DEC), Average Coercivity (H_Coer_AVE), Exchange Bias (H_Ex),
' Decreasing field Remanence (M_Rem_DEC), and Increasing field Remanence (M_Rem_INC).


Option Explicit

Dim l As Integer
Dim i As Integer
Dim x_avg As Double
Dim y_avg As Double
Dim elementString() As String
Dim inputLine As String
Dim isData As Boolean
Dim moment As Double
Dim field As Double
Dim SmoothX() As Double
Dim SmoothY() As Double
Dim X1 As Double
Dim X2 As Double
Dim Y1 As Double
Dim Y2 As Double
Dim FirstOccurance As Boolean


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
	Dim Index As Integer
	Dim fieldAdjust As Double
	Dim Accuracy As Integer
	Dim Saturation1 As Double
	Dim Saturation2 As Double
	Dim Bias As Double
	Dim ListArray() As String
	Dim TimeStampZero As Double
	Dim TimeStart As Double
	Dim TimeEnd As Double
	Dim warn As String
	Dim WarnX As Integer
	Dim WarnY As Integer
	Dim Temp As Double
	Dim AxisPrint As Boolean
	Dim Slope1 As Double
	Dim xAvePrint As Double
	Dim yAvePrint As Double
	Dim OffSet As Double
	Dim Data As Boolean






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

	Begin Dialog UserDialog 380,581 ' %GRID:10,7,1,1
		OKButton 40,539,130,28
		CancelButton 210,539,130,28
		Text 10,21,370,28,"This Script Will Analyze a Ferromagnetic Hysteresis M(H) Loop to Infer Msat, Mrem, Hcoer, and Hex. ",.Text1,2
		TextBox 30,294,90,21,.FieldMin
		TextBox 210,294,110,21,.FieldMax
		Text 60,273,40,14,"From",.Text2
		Text 250,273,30,14,"To",.Text3
		CheckBox 100,497,190,14,"Apply Smooth Filter",.CheckBox1
		Text 30,105,330,42,"Please enter the relative time stamps for the start and end of the 4-quadrant hysteresis loop. (May leave blank if loop is the only data on the file)",.Text4,2
		Text 70,154,40,14,"Start",.Text5
		TextBox 40,182,90,21,.TimeStart
		Text 240,154,30,14,"End",.Text6
		Text 150,189,30,14,"min",.Text8
		Text 310,189,30,14,"min",.Text9
		Text 40,224,290,28,"Input a high field region for determining saturation moment.",.Text10,2
		Text 130,301,30,14,"Oe",.Text11
		Text 330,301,30,14,"Oe",.Text12
		DropListBox 80,434,210,42,ListArray(),.SelectMoment
		TextBox 210,182,90,21,.TimeEnd
		Text 80,406,210,14,"Select moment (Y-axis)",.Text7,2
		CheckBox 20,350,20,21,"",.CheckBox2
		Text 70,350,300,28,"Positive and negative saturation moments are NOT expected to be identical.",.Text13,2
	End Dialog
	Dim dlg As UserDialog
	Dialog dlg
	MinField=CStr(dlg.FieldMin)
	MaxField=CStr(dlg.FieldMax)


	If dlg.TimeStart="" Then
		TimeStart=0
	Else
		TimeStart=CStr(dlg.TimeStart)*60
	End If
	If dlg.TimeEnd="" Then
		TimeEnd=10000
	Else
		TimeEnd=CStr(dlg.TimeEnd)*60
	End If

	If TimeStart>TimeEnd Then
		Temp=TimeStart
		TimeStart=TimeEnd
		TimeEnd=Temp
	End If

	If MinField>MaxField Then
		Temp=MinField
		MinField=MaxField
		MaxField=Temp
	End If

	Index=CInt(dlg.SelectMoment)

'================================================Load Data============================================================
	Open inputFilePath For Input As #1
	isData=False
	i = 0
	Data=True

	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If isData Then

			If Data Then
				TimeStampZero=Val(elementString(1))
				TimeStart=TimeStart+TimeStampZero
				TimeEnd=TimeEnd+TimeStampZero
				If TimeStart=0 Then
					ReDim Preserve x(UBound(x)+1)			'Expand the dimentions to fit the number of data points
					ReDim Preserve y(UBound(y)+1)
					x(i) = Val(elementString(3)) 			'Field
					y(i) = Val(elementString(Index)) 			'Moment
					i = i + 1
				End If
				Data=False
			ElseIf Val(elementString(1))>=TimeStart And Val(elementString(1))<=TimeEnd Then
				ReDim Preserve x(UBound(x)+1)			'Expand the dimentions to fit the number of data points
				ReDim Preserve y(UBound(y)+1)
				x(i) = Val(elementString(3)) 			'Field
				y(i) = Val(elementString(Index)) 			'Moment
				i = i + 1
			End If

		End If


		If StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then	'Indicates the next line to be data points
			isData = True

		End If

	Loop
	Close #1

	If dlg.CheckBox1=1 Then

		Begin Dialog UserDialog 400,203 ' %GRID:10,7,1,1
			Text 80,21,230,63,"Please Enter An Integer Value for Moving Average Accuracy (i.e. a value of 4 or 5 will use the 2 values on either side of the data point to calculate the smoothed value).",.Text1
			TextBox 110,112,160,35,.TextBox1
			OKButton 60,161,110,28
			CancelButton 230,161,110,28
		End Dialog
		Dim dlg1 As UserDialog
		Dialog dlg1

		Accuracy=CInt(dlg1.TextBox1)
		Call SmoothFilter(x(),y(),Accuracy)
		slope=SlopeCalc(SmoothX(),SmoothY(),MinField,MaxField)
		xAvePrint=x_avg
		yAvePrint=y_avg
		For i=0 To (UBound(SmoothX)-1)
			y(i)=SmoothY(i)-SmoothX(i)*slope
			x(i)=SmoothX(i)
		Next i
		Slope1=SlopeCalc(x(),y(),MinField,MaxField)
	Else

		slope=SlopeCalc(x(),y(),MinField,MaxField)

		xAvePrint=x_avg
		yAvePrint=y_avg
		For i=0 To (UBound(x)-1)
			y(i)=y(i)-x(i)*slope
		Next i
		Slope1=SlopeCalc(x(),y(),MinField,MaxField)


	End If
		Saturation1=FindSaturation(x(),y(),MinField,MaxField,Slope1,0)
		Saturation2=FindSaturation(x(),y(),MinField,MaxField,Slope1,1)

		If dlg.CheckBox2=0 Then
			OffSet=SaturationOffsetCorrection(Saturation1,Saturation2)
		End If
		For i=0 To (UBound(x)-1)
			y(i)=y(i)-OffSet
		Next
		Saturation1=FindSaturation(x(),y(),MinField,MaxField,Slope1,0)
		Saturation2=FindSaturation(x(),y(),MinField,MaxField,Slope1,1)
		Call yInterceptCalc(x(),y())
		Call xInterceptCalc(x(),y())
		Bias=(X2+X1)/2

	If (X2-X1)/2 < 0 Then
		warn="WARNING: Non-Physical Negative Coercivity Detected; Please Read App Note ===>"

	End If

	'=======================================================================================================================
	'=======================================Writes New Data to File=========================================================
	'=======================================================================================================================

	Open inputFilePath For Input As #1
	Open outputFilePath For Output As #2
isData=False
AxisPrint=True
i=0
Data=False


	Do Until EOF(1)
		Line Input #1,inputLine
		elementString = Split(inputLine,",")
		If dlg.CheckBox1=1 Then

		    If isData=False Then
		    	If StrComp(elementString(LBound(elementString)),"Title",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					Print #2, inputLine
					Print #2, ";High Field Slope [emu/Oe]: " + CStr(slope)
					If dlg.CheckBox2=1 Then
						Print #2, ";M_Sat_POS [emu]: "+CStr(Saturation1);", ";"M_Sat_NEG [emu]: "+CStr(Saturation2);", ";"M_Sat_AVE [emu]: "+CStr((Abs(Saturation2)+Abs(Saturation1))/2)
					Else
						Print #2, ";M_Sat_AVE [emu]: "+CStr(Saturation1);", ";"M_Sat_OffSet [emu]: "+CStr(OffSet)
					End If
					Print #2, ";M_Rem_DEC [emu]: " +CStr(Y2);", ";"M_Rem_INC [emu]: "+CStr(Y1);", ";"M_Rem_AVE [emu]: "+CStr((Abs(Y2)+Abs(Y1))/2)
					Print #2, ";H_Coer_INC [Oe]: " +CStr(X2);", ";"H_Coer_DEC [Oe]: " +CStr(X1);", ";"H_Coer_AVE [Oe]: " +CStr(((X2)-(X1))/2)
					Print #2, ";H_Ex [Oe]: " +CStr(Bias)
				ElseIf StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					If dlg.Checkbox2=1 Then
						Print #2,inputLine; "," ;"[FA] m-H*slope(emu)"; ","; "[FA] Lin. Reg. Fit (emu)"
					Else
						Print #2,inputLine; "," ;"[FA] m-H*slope(emu)-offset"; ","; "[FA] Lin. Reg. Fit (emu)"
					End If
					Data=True
				ElseIf StrComp(elementString(LBound(elementString)),"STARTUPAXIS",1) = 0 Then
					If AxisPrint Then
						Print #2, "STARTUPAXIS,X,4"
						Print #2, "STARTUPAXIS,Y1,";CStr(Index+1)
						Print #2, "STARTUPAXIS,Y1,";CStr(UBound(ListArray)+3)
						Print #2, "STARTUPAXIS,Y2,";CStr(UBound(ListArray)+2)
						AxisPrint=False
					End If

				ElseIf Data=True Then
					If Val(elementString(1))>=TimeStart And Val(elementString(1))<=TimeEnd Then
						isData = True
					End If
				Else
					'if it is not a data row, do nothing and copy the line directly to new output file
					Print #2, inputLine
				End If
			End If
			If isData Then
				field= x(i)
				moment = y(i)
				Print #2, inputLine;",";CStr(moment);",";CStr(slope*field + yAvePrint - slope*xAvePrint)
				i=i+1
				If Val(elementString(1))>=TimeEnd Then
					isData=False
				End If
			End If
		Else

			If isData=False Then
				If StrComp(elementString(LBound(elementString)),"Title",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					Print #2, inputLine
					Print #2, ";High Field Slope [emu/Oe]: " + CStr(slope)
					If dlg.CheckBox2=1 Then
						Print #2, ";M_Sat_POS [emu]: "+CStr(Saturation1);", ";"M_Sat_NEG [emu]: "+CStr(Saturation2);", ";"M_Sat_AVE [emu]: "+CStr((Abs(Saturation2)+Abs(Saturation1))/2)
					Else
						Print #2, ";M_Sat_AVE [emu]: "+CStr(Saturation1);", ";"M_Sat_OffSet [emu]: "+CStr(OffSet)
					End If
					Print #2, ";M_Rem_DEC [emu]: " +CStr(Y2);", ";"M_Rem_INC [emu]: "+CStr(Y1);", ";"M_Rem_AVE [emu]: "+CStr((Abs(Y2)+Abs(Y1))/2)
					Print #2, ";H_Coer_INC [Oe]: " +CStr(X2);", ";"H_Coer_DEC [Oe]: " +CStr(X1);", ";"H_Coer_AVE [Oe]: " +CStr(((X2)-(X1))/2)
					Print #2, ";H_Ex [Oe]: " +CStr(Bias)
				ElseIf StrComp(elementString(LBound(elementString)),"Comment",1) = 0 Then
			    	'if the first word of the line is "comment", turn on isData and put two extra columns
					If dlg.Checkbox2=1 Then
						Print #2,inputLine; "," ;"[FA] m-H*slope(emu)"; ","; "[FA] Lin. Reg. Fit (emu)"
					Else
						Print #2,inputLine; "," ;"[FA] m-H*slope(emu)-offset"; ","; "[FA] Lin. Reg. Fit (emu)"
					End If
					Data=True
				ElseIf StrComp(elementString(LBound(elementString)),"STARTUPAXIS",1) = 0 Then

					If AxisPrint Then
						Print #2, "STARTUPAXIS,X,4"
						Print #2, "STARTUPAXIS,Y1,";CStr(Index+1)
						Print #2, "STARTUPAXIS,Y1,";CStr(UBound(ListArray)+3)
						Print #2, "STARTUPAXIS,Y2,";CStr(UBound(ListArray)+2)
						AxisPrint=False
					End If

				ElseIf Data=True Then
					If Val(elementString(1))>=TimeStart And Val(elementString(1))<=TimeEnd Then
						isData = True
					End If
				Else
					'if it is not a data row, do nothing and copy the line directly to new output file
					Print #2, inputLine
				End If
			End If
			If Data=True Then
				If Val(elementString(1))>TimeEnd Then
					isData=False
				End If
			End If
			If isData Then
				'if it's a data row, go in and compute the Magnetic correction. Print the result to new file'
				field= Val(elementString(3))
				moment = Val(elementString(Index)) 'Convert string to numerical value'
				Print #2, inputLine;",";CStr(moment-(field*slope)-OffSet);",";CStr(slope*field + yAvePrint - slope*xAvePrint)
				i=i+1

			End If
		End If
	Loop

	Close #1
	Close #2
	'Display result on a graph
	MultiVu.DisplayGraph(0,outputFilePath)

	If dlg.CheckBox2=1 Then
'
	Begin Dialog UserDialog 710,371 ' %GRID:10,7,1,1
		Text 310,14,90,14,"Results!",.Text1
		Text 100,77,300,14,"M_Sat_POS: " + CStr(Format(Saturation1,"0.0000E+00")) + " emu",.Text2
		Text 100,105,300,14,"M_Sat_NEG: " + CStr(Format(Saturation2,"0.0000E+00")) + " emu",.Text3
		Text 100,133,300,14,"M_Sat_AVE: " + CStr(Format((Abs(Saturation2)+Abs(Saturation1))/2,"0.0000E+00")) + " emu",.Text4
		Text 410,77,290,14,"M_Rem_DEC: " + CStr(Format(Y2,"0.0000E+00")) + " emu",.Text5
		Text 410,105,290,14,"M_Rem_INC: " + CStr(Format(Y1,"0.0000E+00")) + " emu",.Text6
		Text 410,133,290,14,"M_Rem_AVE: " + CStr(Format((Abs(Y2)+Abs(Y1))/2,"0.0000E+00")) + " emu",.Text7
		Text 100,189,300,14,"H_Coer_INC: " + CStr(Format(X2,"0.0000E+00")) + " Oe",.Text8
		Text 100,217,300,14,"H_Coer_DEC: " + CStr(Format(X1,"0.0000E+00")) + " Oe",.Text9
		Text 100,245,300,14,"H_Coer_AVE: " + CStr(Format(((X2)-(X1))/2,"0.0000E+00")) + " Oe",.Text10
		Text 410,203,290,14,"High Field Slope: " + CStr(Format(slope,"0.0000E+00")) + " emu/Oe",.Text11
		Text 410,231,290,14,"H_Ex: " + CStr(Format(Bias,"0.0000E+00")) + " Oe",.Text12
		Text 190,322,340,28,CStr(warn),.Text13,2
		OKButton 40,315,140,35
		PushButton 540,315,160,21,"PPMS App Note",.AppNoteLink
		PushButton 540,343,160,21,"MPMS3 App Note",.AppNoteLink2
		Text 400,259,290,49,"For accurate determination of coercivities below 500 Oe, please read App Note 1070-207 (on PPMS) or 1500-011 (MPMS3)",.Text14
	End Dialog
		Dim dlg2 As UserDialog
		Select Case Dialog(dlg2)
			Case 1
				Call Shell("explorer.exe http://www.qdusa.com/sitedocs/appNotes/ppms/1070-207.pdf",vbNormalFocus)
			Case 2
				Call Shell("explorer.exe ""https://www.qdusa.com/pharos/view.php?fDocumentId=2046""",vbNormalFocus)
			Case Else
		End Select

	Else

		Begin Dialog UserDialog 710,371 ' %GRID:10,7,1,1
			Text 310,14,90,14,"Results!",.Text1
			Text 100,91,300,14,"M_Sat_AVE: " + CStr(Format((Abs(Saturation2)+Abs(Saturation1))/2,"0.0000E+00")) + " emu",.Text4
			Text 100,119,300,14,"M_Sat_OffSet : "+CStr(Format(OffSet,"0.0000E+00")) + " emu",.Text2
			Text 410,77,290,14,"M_Rem_DEC: " + CStr(Format(Y2,"0.0000E+00")) + " emu",.Text5
			Text 410,105,290,14,"M_Rem_INC: " + CStr(Format(Y1,"0.0000E+00")) + " emu",.Text6
			Text 410,133,290,14,"M_Rem_AVE: " + CStr(Format((Abs(Y2)+Abs(Y1))/2,"0.0000E+00")) + " emu",.Text7
			Text 100,189,300,14,"H_Coer_INC: " + CStr(Format(X2,"0.0000E+00")) + " Oe",.Text8
			Text 100,217,300,14,"H_Coer_DEC: " + CStr(Format(X1,"0.0000E+00")) + " Oe",.Text9
			Text 100,245,300,14,"H_Coer_AVE: " + CStr(Format(((X2)-(X1))/2,"0.0000E+00")) + " Oe",.Text10
			Text 410,203,290,14,"High Field Slope: " + CStr(Format(slope,"0.0000E+00")) + " emu/Oe",.Text11
			Text 410,231,290,14,"H_Ex: " + CStr(Format(Bias,"0.0000E+00")) + " Oe",.Text12
			Text 190,322,340,28,CStr(warn),.Text13,2
			OKButton 40,315,140,35
			PushButton 540,315,160,21,"PPMS App Note",.AppNoteLink
			PushButton 540,343,160,21,"MPMS3 App Note",.AppNoteLink2
			Text 400,259,290,49,"For accurate determination of coercivities below 500 Oe, please read App Note 1070-207 (on PPMS) or 1500-011 (MPMS3)",.Text14
		End Dialog
		Dim dlg4 As UserDialog
		'Dialog dlg4
		Select Case Dialog(dlg4)
			Case 1
				Call Shell("explorer.exe http://www.qdusa.com/sitedocs/appNotes/ppms/1070-207.pdf",vbNormalFocus)
			Case 2
				Call Shell("explorer.exe ""https://www.qdusa.com/pharos/view.php?fDocumentId=2046""",vbNormalFocus)
			Case Else
		End Select
	End If

End Sub
Function FindSaturation(ByVal x() As Double, ByVal y() As Double,ByVal MinX As Double,ByVal MaxX As Double,ByVal slope As Double,ByVal HighLow As Integer)
Dim Sumx As Double
Dim Sumy As Double
Dim n As Integer
n=0
Sumx=0
Sumy=0
If HighLow=0 Then
	For i=0 To (UBound(x)-1)
		If x(i)>=Abs(MinX) And x(i)<=Abs(MaxX) Then ' And y(i)>0
			Sumx = Sumx+x(i)
			Sumy=Sumy+y(i)
			n=n+1
		End If
	Next i
	FindSaturation=(Sumy/n)+slope*(Sumx/n)
ElseIf HighLow=1 Then
	For i=0 To (UBound(x)-1)
		If x(i)<=-Abs(MinX) And x(i)>=-Abs(MaxX) Then ' And y(i)<0
			Sumx = Sumx+x(i)
			Sumy=Sumy+y(i)
			n=n+1
		End If
	Next i
	FindSaturation=(Sumy/n)+slope*(Sumx/n)
End If

End Function

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
	Dim Temp As Double
	n=0

	If MinX>MaxX Then
		Temp=MinX
		MinX=MaxX
		MaxX=Temp
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
Sub yInterceptCalc(ByVal x() As Double,ByVal y() As Double)
	FirstOccurance=True
	Dim YIntercept As Double
	For l = 0 To (UBound(x)-1)
		If x(l)*x(l+1)<0 Then

			YIntercept=y(l)-x(l)*((y(l+1)-y(l))/(x(l+1)-x(l)))

			If x(l)<x(l+1) Then
				Y1=YIntercept
			ElseIf x(l)>x(l+1) Then
				Y2=YIntercept
			End If


		End If
	Next l

End Sub
Sub xInterceptCalc(ByVal x() As Double,ByVal y() As Double)
	Dim XIntercept As Double
	FirstOccurance=True
	For l = 0 To (UBound(x)-1)
		If y(l)*y(l+1)<0 Then

			XIntercept=x(l+1)-y(l+1)/((y(l+1)-y(l))/(x(l+1)-x(l)))

			If x(l)<x(l+1) Then
				X2=XIntercept
			ElseIf x(l)>x(l+1) Then
				X1=XIntercept
			End If

		End If
	Next l

End Sub
Sub SmoothFilter(ByVal x() As Double, ByVal y() As Double, Optional ByVal Accuracy As Integer)
Dim n As Integer
	Dim Limit As Integer
	Dim z As Integer

	If Accuracy<1 Then
		Accuracy=1
	End If

	Limit=Accuracy/2

	ReDim Preserve SmoothX(0)
	ReDim Preserve SmoothY(0)

	For i=(0) To (UBound(x))

		ReDim Preserve SmoothX(UBound(SmoothX)+1)
		ReDim Preserve SmoothY(UBound(SmoothY)+1)

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
Function SaturationOffsetCorrection(ByVal Sat1 As Double,ByVal Sat2 As Double) As Double
	If Sat1>Sat2 Then
		SaturationOffsetCorrection=Sat1-(Sat1-Sat2)/2
	Else
		SaturationOffsetCorrection=Sat2-(Sat2-Sat1)/2
	End If
End Function

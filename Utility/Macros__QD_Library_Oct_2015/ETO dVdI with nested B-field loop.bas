'dVdI_example.bas

'#Uses ".\SDO\SDO.obm"
'#Uses ".\ETO\ETO.obm"
'#Uses ".\MultiVuDataFile\MultiVuDataFile.cls"

'This script will perform a basic dVdI in 4-wire mode; at each DC current it will scan the magnetic field
 'And make a dV/dI resistance measurement at Each field

Option Explicit
Const TCol As String = "Temperature (K)"
Const FCol As String = "Field (Oe)"
Const ResCol As String = "Resistance (Ohms)"
Const DCCol As String = "DC Offset (mA)"
Const ACCol As String = "AC Excitation (mA)"


Sub Main

	Dim F As New MultiVuDataFile

	'Set up the columns that you would like to write to file
	'The Label strings are used both as column headers and to access these columns programmatically (like key-value coding)
	'You can add axis types if you want a column to be used for multiple axes:
	'F.AddColumn(TCol, mvStartupAxisX + mvStartupAxisY1)

	F.AddColumn(TCol,mvStartupAxisNone)
	F.AddColumn(FCol,mvStartupAxisNone)
	F.AddColumn(ResCol,mvStartupAxisY1)
	F.AddColumn(DCCol,mvStartupAxisX)
	F.AddColumn(ACCol,mvStartupAxisNone)

	'*** USER INPUT NEEDED HERE ***
	'Create the file and write the header.
	'If the file exists, this will do nothing.
	'Be sure that all of your columns are the same as the existing file if you are appending!
	F.CreateFileAndWriteHeader("c:\QDVersalab\Data\test6.dat", "Test Data File")


	'Open the file for viewing in MultiVu
	F.OpenInMultiVu()


	Dim I As Double
	Dim Frequency As Single
	Dim ChannelNum As Byte
	Dim TotalGain As TGain
	Dim ACAmplitude As Single
	Dim MaxDCCurrent As Single
	Dim StepsPerQuadrant As Integer
	Dim AveragingTime As Single
	Dim CurrentRange As IRange
	Dim I_Stepsize As Single
	Dim MMode As Mode
	Dim SettlingTime As Single
	Dim Resistance As Single
	Dim Temperature As Double
	Dim Status As Long
	Dim Field As Double
	Dim B As Double
	Dim Minfield As Double
	Dim Maxfield As Double
	Dim B_stepsize As Double

	Debug.Clear

	MMode=Resistance
	ETO.Set_Mode(MMode)

'*** USER INPUT NEEDED HERE ***
'Define ETO Params
	Frequency = 18.3		'Hz
	ChannelNum = 1			'which channel to use for dV/dI
	TotalGain = B_3X
	ACAmplitude = 0.5	   	'mA
	MaxDCCurrent = 5		'mA
	StepsPerQuadrant = 3
	AveragingTime = 0.5		'sec: averaging time must be larger than 0.5 sec but less than 1 minute
	CurrentRange = F_10mA	'the current range must be large enough for the DC current + the AC current
	SettlingTime = 0.5		'sec

	I_Stepsize = Abs(MaxDCCurrent)/StepsPerQuadrant
'*** USER INPUT NEEDED HERE ***
'Define Field Scan params
	Minfield = 0
	Maxfield = 100
	B_stepsize = 25

'Initialize Module parameters
	ETO.Turn_Channel_Off(1)
	ETO.Turn_Channel_Off(2)

'Initialize Measurement
	ETO.Set_Frequency(ChannelNum, Frequency)
	ETO.Set_Ave_Time(ChannelNum, AveragingTime)
	ETO.Set_I_Range(ChannelNum, CurrentRange)
	ETO.Set_Total_Gain(1,TotalGain)
	ETO.Set_AC_Current(ChannelNum, ACAmplitude)
	ETO.Set_DC_Current(ChannelNum, 0.0)
	ETO.Set_Ave_Time(ChannelNum, AveragingTime)
	ETO.Set_Feedback_Enable(ChannelNum, 1)
	ETO.Set_Output_Enable(ChannelNum, 1)

	Wait(3)


	For I = 0 To MaxDCCurrent Step I_Stepsize
		ETO.Set_DC_Current(ChannelNum,I)
		For B = Minfield To Maxfield Step B_stepsize
			MultiVu.SetField(B,200,0,0)
			WaitFor(2,0,0)
			Resistance = MeasureResistance(ChannelNum, SettlingTime, AveragingTime)
			MultiVu.GetTemperature(Temperature,Status)
			MultiVu.GetField(Field,Status)
			F.SetValue(TCol, Temperature)
			F.SetValue(ResCol, Resistance)
			F.SetValue(FCol, Field)
			F.SetValue(DCCol, ETO.Read_DC_Offset(ChannelNum))
			F.SetValue(ACCol, ETO.Read_AC_Amplitude(ChannelNum))
			F.WriteData()
		Next B
	Next I

'Turn off Channels when done
	ETO.Turn_Channel_Off(1)
	ETO.Turn_Channel_Off(2)

End Sub

Function TriggerMeasurement(Channel As Integer)
	If Channel = 1 Then
		ETO.Trigger1()
	Else
		ETO.Trigger2()
	End If
End Function

Function MeasureResistance(ChNum As Byte, Settle As Single, AveT As Single) As Single
	Wait(Settle)
	TriggerMeasurement(ChNum)
	If AveT > 1.0 Then
		Wait(AveT+0.5)
		Else
		Wait(AveT*1.5)
	End If

	MeasureResistance=ETO.Read_Resistance(ChNum)
End Function










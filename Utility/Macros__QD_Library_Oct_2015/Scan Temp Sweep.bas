Sub fn_TempSweep

   Dim R As Double
   Dim Rp As Long
   Dim Current As Double


'======================================================================================================='
'=================================Adjust the values below==============================================='
'======================================================================================================='

   Const STARTING_TEMP=295.00
   Const ENDING_TEMP=275.00
   Const NUMBER_OF_STEPS=5
   Const TEMP_SWEEP_RATE=10.00
   Const APPROACH=No_OShoot				'Fast or No_OShoot
   Const SPACING = S_Log				'Uniform, S_Log or Inverse (1/T)
'======================================================================================================='


   T2 = ENDING_TEMP
   n = NUMBER_OF_STEPS
   Rate = TEMP_SWEEP_RATE
   RateType = APPROACH
   Select Case SPACING
   	Case 0		'Uniform Spacing
   		T1 = STARTING_TEMP
   		d1 = (T2-T1)/(n-1)
   	Case 1		'Log Spacing
   		T1 = Log(STARTING_TEMP)
   		d1 = (Log(T2)-(T1))/(n-1)
   	Case 2		'1/T Spacing
   		T1 = 1/(STARTING_TEMP)
   		d1=((1/(T2))-(T1))/(n-1)
   End Select
   Current=STARTING_TEMP
   Dir1 = Abs(d1)/d1





	MultiVu.SetTemperature(Current,20,Fast)		'Set the temperature to the starting value
	MultiVu.WaitFor(1,0,0)								'Wait for the system to reach starting temperature
	MultiVu.SetTemperature(T2,Rate,RateType)	'Set the temperature to the ending value at specified rate and approach type.

   	While Dir1*Current < Dir1*T2
      Do
         DoEvents

 '==============================================================================================='
		'Type in your own commands to perform actions while the temperature is approaching the next sweep point
		'Do Things While the temperature Is approaching the Next sweep point
 '==============================================================================================='




         ' Get Current Temperature
         MultiVu.GetTemperature(R,Rp)
      Loop While Dir1*R < Dir1*Current

 '==============================================================================================='
      'Type in your own commands to perform actions once the temperature has reached the sweep point
      'Do Things now that the temperature has reached the sweep point
 '==============================================================================================='


			'Increase to next sweep point
	T1 = T1 + d1
	Select Case SPACING
	   	Case 0		'Uniform Spacing
	   		Current=T1
	   	Case 1		'Log Spacing
	   		Current=Exp(T1)
	   	Case 2
	   		Current=1/T1
    End Select

   Wend
End Sub


Sub Main
   Call fn_TempSweep
End Sub

Enum Temp_Spacing
	Uniform
	S_Log
	Inverse
End Enum

Enum Rate_Type
	Fast
	No_OShoot
End Enum

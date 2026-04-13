Sub fn_TempStep

   Dim R As Double
   Dim Rp As Long
   Dim Current As Double


'======================================================================================================='
'=================================Adjust the values below==============================================='
'======================================================================================================='

   Const STARTING_TEMP=300.00
   Const ENDING_TEMP=275.00
   Const NUMBER_OF_STEPS=5
   Const TEMP_SWEEP_RATE=10.00
   Const APPROACH=Fast				'Fast or No_OShoot
   Const SPACING = S_Log				'Uniform, S_Log or Inverse (1/T)
   Const WAIT_DELAY=0					'How long you want to wait at each set point before moving on
'======================================================================================================='


   T2 = ENDING_TEMP
   n = NUMBER_OF_STEPS
   Rate = TEMP_SWEEP_RATE
   RateType=APPROACH
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

	MultiVu.SetTemperature(Current,20.00,0)

   For iT1 = 1 To (n)
      If iT1 <> n Then
         MultiVu.SetTemperature(Current,Rate,RateType)			'Sets temperature to next set point
      Else
         MultiVu.SetTemperature(T2,Rate,RateType)			'sets temperature to last set point (used for rounding errors)
      End If
      MultiVu.WaitFor(1,WAIT_DELAY,0)									'wait for temp to stabilize at current set point

 '==============================================================================================='
 '========Insert your commands to peroform actions when the temperature has stabilized at the current set point================='
 '==============================================================================================='
MultiVu.GetTemperature(R,Rp)
Debug.Print(R)

    T1 = T1 + d1				'Sets next set point
    Select Case SPACING
	   	Case 0		'Uniform Spacing
	   		Current=T1
	   	Case 1		'Log Spacing
	   		Current=Exp(T1)
	   	Case 2
	   		Current=1/T1
    End Select
   Next iT1
End Sub

Sub Main
   Call fn_TempStep
End Sub

Enum Rate_Type
	Fast
	No_OShoot
End Enum

Enum Temp_Spacing
	Uniform
	S_Log
	Inverse
End Enum

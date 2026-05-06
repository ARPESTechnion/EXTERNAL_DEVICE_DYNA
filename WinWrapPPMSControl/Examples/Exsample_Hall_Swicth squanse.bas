Sub fn_ExsampleHallSwicthsquanse
   Dim DFIELD2 As Double
   Dim IB2 As Long
   Dim B2 As Double
   Dim MAXRATE As Double
   Dim MINRATE As Double
   Dim MAXTEMP As Double
   Dim MINTEMP As Double
   Dim D1 As Double
   Dim IT1 As Long
   Dim T1 As Double
   ' Connect to K7001                    'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0001 Remark
   ' Open All                            'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0002 Remark
   ' Set chennel A (1,2,3,4)             'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0003 Remark
   ' Set chennel B (4,2,3,1)             'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0004 Remark
   ' Set chennel C (1,5,6,4)             'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0005 Remark
   ' Set chennel D (4,5,6,1)             'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0006 Remark
   DynaCool.SetTemperature(300.000000,10.000000,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0007 Set Temp
   DynaCool.SetField(0.0,100.0,0,0)      'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0008 Set Field
   DynaCool.WaitFor(1+2*1+4*0+8*0,0,0)   'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0009 Wait For %t
   T1 = 300.000000                       'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
   D1 = (10.000000-300.000000)/(30-1)    'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
   DynaCool.GetTempLimits(MINTEMP,MAXTEMP,MINRATE,MAXRATE) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
   For IT1 = 1 To (30)                   'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      If IT1 = 1 Then                    'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
   		DynaCool.SetTemperature(300.000000,MAXRATE,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      ElseIf IT1 <> 30 Then              'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
         DynaCool.SetTemperature(T1,10.000000,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      Else                               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
         DynaCool.SetTemperature(10.000000,10.000000,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      End If                             'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      WaitFor(1,0,0)                     'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0010 Scan Temp
      DynaCool.SetField(-10000.0,50.0,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0011 Set Field
      DynaCool.WaitFor(0+2*1+4*0+8*0,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0012 Wait For %t
      B2 = -10000.0                      'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
      DFIELD2 = (10000.0--10000.0)/(81-1) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
      For IB2 = 1 To (81)                'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         If IB2 = 1 Then                 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
            DynaCool.SetField(-10000.0,200,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         ElseIf IB2 = 81 Then            'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
            DynaCool.SetField(10000.0,100.0,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         Else                            'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
            DynaCool.SetField(B2,100.0,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         End If                          'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         WaitFor(2,0,0)                  'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0013 Scan Field
         ' close chennel A               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0014 Remark
         DynaCool.SequenceMeasure("ETOLC 'Chennel A'") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0015 ETOLC
         DynaCool.SequenceMeasure("ETOR 'C:\QdDynacool\default_ETO.qmap' 0 3 1 0 0.01 128.1738 4.60 1 1 0 0 0 0") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0016 ETOR
         ' close chennel B               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0017 Remark
         DynaCool.SequenceMeasure("ETOLC 'Chennel A'") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0018 ETOLC
         DynaCool.SequenceMeasure("ETOR 'C:\QdDynacool\default_ETO.qmap' 0 3 1 0 0.01 128.1738 4.60 1 1 0 0 0 0") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0019 ETOR
         ' close chennel C               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0020 Remark
         DynaCool.SequenceMeasure("ETOLC 'Chennel A'") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0021 ETOLC
         DynaCool.SequenceMeasure("ETOR 'C:\QdDynacool\default_ETO.qmap' 0 3 1 0 0.01 128.1738 4.60 1 1 0 0 0 0") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0022 ETOR
         ' close chennel D               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0023 Remark
         DynaCool.SequenceMeasure("ETOLC 'Chennel A'") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0024 ETOLC
         DynaCool.SequenceMeasure("ETOR 'C:\QdDynacool\default_ETO.qmap' 0 3 1 0 0.01 128.1738 4.60 1 1 0 0 0 0") 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0025 ETOR
         DynaCool.WaitFor(0+2*0+4*0+8*0,0,0) 'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0026 Wait For %t
         ' Open All                      'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0027 Remark
         B2 = B2 + DFIELD2               'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0028 ENB
      Next IB2                           'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0028 ENB
      T1 = T1 + D1                       'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0029 ENT
   Next IT1                              'mvseq:Exsample_Hall_Swicth squanse.seq(1)>0029 ENT
End Sub

Sub Main
   Call fn_ExsampleHallSwicthsquanse
End Sub

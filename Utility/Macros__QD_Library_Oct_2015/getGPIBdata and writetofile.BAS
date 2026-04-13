'#Language "WWB-COM"
'#Uses "Utils\Utils.obm"
'#Uses "MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "LS-370 bridge\LSBridge.obm"

Option Explicit

Dim lStatus As Long
Dim fTemp As Double
Dim fField As Double
Dim fRes As Double
Dim T As Double
Dim B As Double
Dim fResults As New MultiVuDataFile
' the location where the data file will be generated
' (defaults to the root data directory for the architecture the script is being run on)
' NOTE: directory will be automatically created if it does not exist
Dim sDataDirectory As String
' the file name pattern for the data file - we are using the current date/time as part of the file name
' to prevent overwriting of or appending to existing files
Const sFilenamePattern = "Scripting Data_%Y%m%d_%H%M.dat"
' labels for our data columns for easier access
Const T_col = "Temperature (K)"
Const H_col = "Field (Oe)"
Const R_col = "Resistance (Ohm)"

Sub Main
	' verify that we have the correct version of Utils.obm
	Utils.CheckForRequiredVersion("Utils",Utils.Version(),25881)
	' clear out any previous debug messages
	Debug.Clear
	' set up the default (system-dependent) data directory
	sDataDirectory = Utils.systemDirectory() & "\Data\"
	' initialize LS bridge (or other GPIB device)
	If LSBridge.Init <> 1 Then
		Debug.Print "GPIB instrument does not initialize properly"
	End If

	' create a new MV data file
	fResults.AddColumn(T_col, mvStartupAxisY1)
	fResults.AddColumn(H_col, mvStartupAxisY2, mvLogScale)
	fResults.AddColumn(R_col,mvStartupAxisY3)
	fResults.CreateFileAndWriteHeader(sDataDirectory & Utils.DateAndTime(sFilenamePattern),"Example Resistance Data")
	' open the newly created data file for display in MultiVu
	fResults.OpenInMultiVu()

	For T = 300 To 50 Step -50
		MultiVu.SetTemperature(T,50,0)
		Waitfor(1,0,0)  'mvseq:sequencename>0001 Wait for %t
		For B = -20000 To 20000 Step 1000
			MultiVu.SetField(B,300,0,0)
			' wait for field; bitmask=2
			WaitFor(2,0,0) 'mvseq:sequencename>0002 Wait for %t
			' read the current temperature (and status)
			MultiVu.GetTemperature(fTemp,lStatus)
			' read the current field (and status)
			MultiVu.GetField(fField,lStatus)
			' read the resistance from LSBridge (or other instrument)
			LSBridge.ReadRes(fRes)
			' write the data to the file
			fResults.WriteDataUsingArray(Array( _
											T_col, fTemp, _
											H_col, fField, _
											R_col, fRes))
		Next B
	Next T
	MultiVu.SetField(0,300,0,0)
End Sub

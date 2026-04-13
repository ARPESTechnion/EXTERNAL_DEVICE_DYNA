'#Language "WWB-COM"
'#Uses "Utils\Utils.obm"
'#Uses "MultiVuDataFile\MultiVuDataFile.cls"
'#Uses "KeithleyMeters\Keithley2601.obm"

Option Explicit

Dim lStatus As Long
Dim fRes As Double
Dim fI As Double
Dim fV As Double


Dim fResults As New MultiVuDataFile
' the location where the data file will be generated
' (defaults to the root data directory for the architecture the script is being run on)
' NOTE: directory will be automatically created if it does not exist
Dim sDataDirectory As String
' the file name pattern for the data file - we are using the current date/time as part of the file name
' to prevent overwriting of or appending to existing files
Const sFilenamePattern = "Scripting Data_%Y%m%d_%H%M.dat"
' labels for our data columns for easier access
Const I_col = "Current (A)"
Const V_col = "Voltage (V)"
Const R_col = "Resistance (Ohm)"

Sub Main
	' verify that we have the correct version of Utils.obm
	Utils.CheckForRequiredVersion("Utils",Utils.Version(),25881)
	' clear out any previous debug messages
	Debug.Clear
	' set up the default (system-dependent) data directory
	sDataDirectory = Utils.systemDirectory() & "\Data\"
	' initialize GPIB device
	If Keithley2601.Init <> 1 Then
		Debug.Print "GPIB instrument does not initialize properly"
	End If

	' create a new MV data file
	fResults.AddColumn(I_col, mvStartupAxisY1)
	fResults.AddColumn(V_col, mvStartupAxisY2)
	fResults.AddColumn(R_col,mvStartupAxisY3)
	fResults.CreateFileAndWriteHeader(sDataDirectory & Utils.DateAndTime(sFilenamePattern),"Example Resistance Data")
	' open the newly created data file for display in MultiVu
	fResults.OpenInMultiVu()
	

	
	' configure system: V = 80mV source, I probe and 1mA current compliance
	Keithley2601.Config_setVasSource(0.08, 0.001, 0.001)
	
	' read the measurements
	Keithley2601.ReadRes(fV, fI, fRes)
	
	' write the data to the file
	fResults.WriteDataUsingArray(Array( _
											V_col, fV, _
											I_col, fI, _
											R_col, fRes))

End Sub

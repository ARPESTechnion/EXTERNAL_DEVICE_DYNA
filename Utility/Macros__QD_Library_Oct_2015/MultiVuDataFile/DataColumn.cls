VERSION 1.0 CLASS
BEGIN
  MultiUse = -1 'True
END
Attribute VB_PredeclaredId = False
Attribute VB_Creatable = True
Attribute VB_Exposed = False
Attribute VB_GlobalNameSpace = False
Attribute VB_Name = "DataColumn"
'#Language "WWB-COM"

'Data file column class
'Not much going on here--really just a struct for now.
'But maybe later we'll add more, like automatic setting of value using an SDO.

Option Explicit

Public Label As String
Public Value As Variant
Public ScaleType As Integer
Public StartupAxis As Integer
Public Persistent As Boolean
Public IsFresh As Boolean

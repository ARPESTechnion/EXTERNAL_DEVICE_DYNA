"""
v3.core.constants  —  Centralized configuration for the experiment system.

All instrument addresses, VISA timeouts, physical limits, CSV column schema,
and operational defaults live here.  Imported by every other v3 module that
needs a constant — no magic numbers scattered across files.
"""

from __future__ import annotations

# ============================================================================
# Instrument VISA / network addresses
# ============================================================================
KEITHLEY2600_ADDRESS = "GPIB0::26::INSTR"
KEITHLEY2450_ADDRESS = "GPIB0::18::INSTR"
LOCKIN_ADDRESS = "GPIB0::8::INSTR"
STRAIN_RP100_ADDRESS = "ASRL3::INSTR"
STRAIN_METER_ADDRESS = "GPIB0::28::INSTR"
SWITCH_BACKEND = "keithley7001"  # "my_switch" | "keithley7001"
SWITCH_ADDRESS_MY = "USB0::0x0957::0x0507::MY56482243::INSTR"
SWITCH_ADDRESS_7001 = "GPIB0::7::INSTR"
# Backward-compatible alias used in older code paths.
SWITCH_ADDRESS = SWITCH_ADDRESS_MY

#DYNA_HOST = '132.68.75.98'
DYNA_HOST = "localhost"
DYNA_PORT = 5000

# ============================================================================
# Instrument names (canonical keys used by InstrumentBus)
# ============================================================================
INST_KEITHLEY2600 = "keithley2600"
INST_KEITHLEY2450 = "keithley2450"
INST_LOCKIN = "lockin"
INST_SWITCH = "switch"
INST_DYNA = "dyna"
INST_STRAIN = "strain"

ALL_INSTRUMENTS = (
    INST_KEITHLEY2600,
    INST_KEITHLEY2450,
    INST_LOCKIN,
    INST_SWITCH,
    INST_DYNA,
    INST_STRAIN,
)

# Switch matrix routing/label capacity by backend.
SWITCH_PIN_MAX = 10 if str(SWITCH_BACKEND).strip().lower() == "keithley7001" else 8

# Logical switch channels supported by the app/script DSL.
LOGICAL_CHANNELS = tuple("abcdefghij") if SWITCH_PIN_MAX >= 10 else tuple("abcdefgh")
MIN_SWITCH_CONFIGS = 2
MAX_SWITCH_CONFIGS = len(LOGICAL_CHANNELS)

# ============================================================================
# VISA / communication timeouts (milliseconds for VISA, seconds for TCP)
# ============================================================================
VISA_TIMEOUT_MS = 5_000          # per-call VISA timeout
DYNA_SOCKET_TIMEOUT_S = 30.0    # TCP socket timeout for PPMS

# ============================================================================
# Physical / safety limits
# ============================================================================
HELMHOLTZ_MAX_CURRENT_A = 3.0         # Total current limit (A) across both coils
HELMHOLTZ_MAX_CURRENT_PER_COIL_A = 1.5  # per-coil limit (current / 2)
TEMP_MIN_K = 1.6
TEMP_MAX_K = 400.0
FIELD_MAX_OE = 140_000.0
DYNA_COOLING_CONFIRM_THRESHOLD_K = 295.0

# ============================================================================
# Default operational parameters
# ============================================================================
DEFAULT_RAMP_RATE_mA_per_s = 100.0
HELMHOLTZ_MAX_RAMP_RATE_mA_per_s = 100.0
DEFAULT_COMPLIANCE_V = 3.0
DEFAULT_DYNA_FIELD_RATE = 50.0        # Oe/s (hardware-safe maximum)
DEFAULT_DYNA_TEMP_RATE = 10.0         # K/min
DYNA_TEMP_RATE_MIN_K_MIN = 0.0        # K/min (minimum allowed temperature rate)
DYNA_TEMP_RATE_MAX_K_MIN = 50.0       # K/min (maximum allowed temperature rate)

# Wait / stability
STABILITY_POLL_INTERVAL_S = 2.0
STABILITY_MAX_WAIT_S = 18_000         # 5 hours
STABILITY_REQUIRED_COUNT = 2          # consecutive stable readings

# ============================================================================
# Data file configuration
# ============================================================================
DEFAULT_DATA_DIR = "Data_Route"
DEFAULT_LOG_DIR = "Logs"
AUTO_LOG_MAX_SIZE_BYTES = 50 * 1024 * 1024    # 50 MB

# Normalized channel-aware CSV schema.
CSV_FIELDNAMES: list[str] = [
    "Time(s)",
    "Temp(K)",
    "Field(Oe)",
    "Helmholtz_Current(A)",
    "Helmholtz_Field(G)",
    "Hall_Voltage(V)",
    "Hall_Voltage_Error(V)",
    "Hall_Field(G)",
    "Hall_Field_Error(G)",
    "Strain_Voltage_Ch1(V)",
    "Strain_Voltage_Ch2(V)",
    "Strain_Capacitance(pF)",
    "Strain_Loss",
    "Strain_Force",
    "Channel",
    "LockIn_X(V)",
    "LockIn_X_Error(V)",
    "LockIn_Y(V)",
    "LockIn_Y_Error(V)",
    "LockIn_R(V)",
    "LockIn_R_Error(V)",
    "LockIn_Theta(deg)",
    "LockIn_Theta_Error(deg)",
    "LockIn_Average_Count",
    "Frequency(Hz)",
    "Sensitivity(V)",
    "Resistor(Ohm)",
    "Output_Voltage(V)",
    "Output_Current(A)",
    "Time_Constant(s)",
    "Sample_Resistance(Ohm)",
    "Sample_Resistance_Error(Ohm)",
    "IV_Point",
    "IV_Sweep_Direction",
    "IV_Source_Current(mA)",
    "IV_Source_Voltage(V)",
    "IV_Measured_Voltage(V)",
    "IV_Measured_Current(mA)",
    "Measurement_Type",
    "Notes",
]

# Mapping from internal data_point keys → CSV column names.
# Measurement functions produce dicts with the LEFT keys;
# DataManager translates them to CSV columns using the RIGHT keys.
DATA_KEY_TO_CSV: dict[str, str] = {
    "Time":                     "Time(s)",
    "Temp":                     "Temp(K)",
    "In-plane_Field":           "Field(Oe)",
    "Helmholtz_Current":        "Helmholtz_Current(A)",
    "Helmholtz_Field":          "Helmholtz_Field(G)",
    "Hall Voltage":             "Hall_Voltage(V)",
    "Hall Voltage Error":       "Hall_Voltage_Error(V)",
    "Hall Field":               "Hall_Field(G)",
    "Hall Field Error":         "Hall_Field_Error(G)",
    "Strain Voltage Ch1":       "Strain_Voltage_Ch1(V)",
    "Strain Voltage Ch2":       "Strain_Voltage_Ch2(V)",
    "Strain Capacitance":       "Strain_Capacitance(pF)",
    "Strain Loss":              "Strain_Loss",
    "Strain Force":             "Strain_Force",
    "Channel":                  "Channel",
    "LockIn_X":                 "LockIn_X(V)",
    "LockIn_X_Error":           "LockIn_X_Error(V)",
    "LockIn_Y":                 "LockIn_Y(V)",
    "LockIn_Y_Error":           "LockIn_Y_Error(V)",
    "LockIn_R":                 "LockIn_R(V)",
    "LockIn_R_Error":           "LockIn_R_Error(V)",
    "LockIn_Theta":             "LockIn_Theta(deg)",
    "LockIn_Theta_Error":       "LockIn_Theta_Error(deg)",
    "LockIn_Average_Count":     "LockIn_Average_Count",
    "LockIn_Frequency":         "Frequency(Hz)",
    "LockIn_Sensitivity":       "Sensitivity(V)",
    "LockIn_R_lockin":          "Resistor(Ohm)",
    "LockIn_Output_Voltage":    "Output_Voltage(V)",
    "LockIn_Output_Current":    "Output_Current(A)",
    "LockIn_Time_Constant":     "Time_Constant(s)",
    "Sample_Resistance":        "Sample_Resistance(Ohm)",
    "Sample_Resistance_Error":  "Sample_Resistance_Error(Ohm)",
    "IV_Point":                 "IV_Point",
    "IV_Sweep_Direction":        "IV_Sweep_Direction",
    "IV_Source_Current":        "IV_Source_Current(mA)",
    "IV_Source_Voltage":        "IV_Source_Voltage(V)",
    "IV_Measured_Voltage":      "IV_Measured_Voltage(V)",
    "IV_Measured_Current":      "IV_Measured_Current(mA)",
}

# Auto-log CSV columns
AUTO_LOG_FIELDNAMES: list[str] = [
    "Timestamp",
    "Elapsed_Time(s)",
    "Temperature(K)",
    "PPMS_Field(Oe)",
    "Helmholtz_Current_A(A)",
    "Helmholtz_Current_B(A)",
    "Helmholtz_Resistance_A(Ohm)",
    "Helmholtz_Resistance_B(Ohm)",
    "Helmholtz_Field(G)",
]

# ============================================================================
# UI update configuration
# ============================================================================
UI_TICK_INTERVAL_MS = 100           # main update_ui heartbeat
UI_EVENT_QUEUE_CAPACITY = 5_000
COMMAND_QUEUE_CAPACITY = 100
MAX_RESULTS_POINTS = 100_000       # deque maxlen for results_data
MAX_PLOT_POINTS = 10_000
AUTO_LOG_QUEUE_CAPACITY = 200

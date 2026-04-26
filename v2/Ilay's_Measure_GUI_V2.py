import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import csv
import threading
from datetime import datetime
from pathlib import Path
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import json

# =============================================================================
# MOCKUP MODE - Set to True to use mockup instruments instead of real hardware
# ============================================================================
USE_MOCKUP = False
# ============================================================================

# Import instruments based on mockup mode
if USE_MOCKUP:
    # Mockup instrument drivers
    from Utility.Keithley2600 import MockKeithley2600 as Keithley2600
    from Utility.Mock_Kethley2450 import MockKeithley2450 as Keithley2450Wrapper
    from Utility.MySwitch import MockSwitch as MySwitch
    from Utility.New_Mock_LockIn import MockLockInSR830 as LockInSR830
    print("=" * 60)
    print("MOCKUP MODE ENABLED - Using simulated instruments")
    print("=" * 60)
else:
    # Real instrument drivers
    from Utility.Keithley2600 import Keithley2600
    from Utility.Keithley2450_Wrapper import Keithley2450Wrapper
    from Utility.MySwitch import MySwitch
    from Utility.New_LockIn import LockInSR830

from Utility.DynaClass import DynaClass

# ============================================================================
# INSTRUMENT CONFIGURATION - Update these addresses for your hardware setup
# ============================================================================
# Keithley 2600 (Helmholtz coil control) - USB address
KEITHLEY2600_ADDRESS = 'GPIB0::26::INSTR'

# Keithley 2450 (Hall bar measurements) - GPIB address
# Common formats: 'GPIB0::18::INSTR', 'USB0::0x05E6::0x2450::XXXXXXX::INSTR'
KEITHLEY2450_ADDRESS = 'GPIB0::18::INSTR'

# Lock-in Amplifier SR830 - GPIB address
LOCKIN_ADDRESS = 'GPIB0::8::INSTR'

# Switch - USB address
SWITCH_ADDRESS = 'USB0::0x0957::0x0507::MY56482243::INSTR'

# PPMS DynaClass - Network connection
DYNA_HOST = 'localhost'
#DYNA_HOST = '132.68.75.98'
DYNA_PORT = 5000
# ============================================================================

# Initialize instruments
init_errors = []

if USE_MOCKUP:
    print("\n" + "=" * 60)
    print("INITIALIZING MOCKUP INSTRUMENTS")
    print("=" * 60)
    
    print("Initializing Keithley 2600 (Helmholtz - Mockup)...")
    try:
        keithley = Keithley2600()
        keithley.connect()
        keithley.reset()
        keithley.set_4wires(wires4=False, Ch='ab')
        print(f"  Mockup Keithley 2600 initialized")
    except Exception as exc:
        keithley = None
        init_errors.append(f"Keithley 2600: {exc}")
        print(f"  FAILED: {exc}")

    print("Initializing Keithley 2450 (Hall bar - Mockup)...")
    try:
        keithley2450 = Keithley2450Wrapper(KEITHLEY2450_ADDRESS)
        keithley2450.connect()
        keithley2450.reset()
        print(f"  Mockup Keithley 2450 initialized")
    except Exception as exc:
        keithley2450 = None
        init_errors.append(f"Keithley 2450: {exc}")
        print(f"  FAILED: {exc}")

    print("Initializing Lock-in SR830 (Mockup)...")
    try:
        lockin = LockInSR830()
        lockin.sine_output_off()  # Set sine output to minimum (0.004V)
        print(f"  Mockup Lock-in SR830 initialized")
    except Exception as exc:
        lockin = None
        init_errors.append(f"Lock-in SR830: {exc}")
        print(f"  FAILED: {exc}")

    print("Initializing Switch (Mockup)...")
    try:
        switch = MySwitch()
        switch.connect()
        switch.open_all()
        print(f"  Mockup Switch initialized")
    except Exception as exc:
        switch = None
        init_errors.append(f"Switch: {exc}")
        print(f"  FAILED: {exc}")

    print("Initializing PPMS DynaClass (Real - Network)...")
    try:
        dyna = DynaClass(DYNA_HOST, DYNA_PORT)
        dyna.connect()
        print(f"  Connected to {DYNA_HOST}:{DYNA_PORT}")
    except Exception as exc:
        dyna = None
        init_errors.append(f"PPMS DynaClass: {exc}")
        print(f"  FAILED to connect to {DYNA_HOST}:{DYNA_PORT}: {exc}")

else:
    print("\n" + "=" * 60)
    print("INITIALIZING REAL INSTRUMENTS")
    print("=" * 60)
    
    print("Initializing Keithley 2600 (Helmholtz)...")
    try:
        keithley = Keithley2600()
        keithley.address = KEITHLEY2600_ADDRESS
        keithley.connect()
        keithley.reset()
        keithley.set_4wires(wires4=False, Ch='ab')
        print(f"  Connected to {keithley.address}")
    except Exception as exc:
        keithley = None
        init_errors.append(f"Keithley 2600: {exc}")
        print(f"  FAILED to connect to {KEITHLEY2600_ADDRESS}: {exc}")

    print("Initializing Keithley 2450 (Hall bar)...")
    try:
        keithley2450 = Keithley2450Wrapper(KEITHLEY2450_ADDRESS)
        # Verify connection with a simple query.
        keithley2450.query("*IDN?")
        print(f"  Connected to {KEITHLEY2450_ADDRESS}")
    except Exception as exc:
        keithley2450 = None
        init_errors.append(f"Keithley 2450: {exc}")
        print(f"  FAILED to connect to {KEITHLEY2450_ADDRESS}: {exc}")

    print("Initializing PPMS DynaClass...")
    try:
        dyna = DynaClass(DYNA_HOST, DYNA_PORT)
        result = dyna.connect()
        if result is False:
            raise RuntimeError("PPMS connection failed")
        print(f"  Connected to {DYNA_HOST}:{DYNA_PORT}")
    except Exception as exc:
        dyna = None
        init_errors.append(f"PPMS DynaClass: {exc}")
        print(f"  FAILED to connect to {DYNA_HOST}:{DYNA_PORT}: {exc}")

    print("Initializing Lock-in SR830...")
    try:
        lockin = LockInSR830(resource=LOCKIN_ADDRESS)
        lockin.sine_output_off()  # Set sine output to minimum (0.004V)
        print(f"  Connected to {LOCKIN_ADDRESS}")
    except Exception as exc:
        lockin = None
        init_errors.append(f"Lock-in SR830: {exc}")
        print(f"  FAILED to connect to {LOCKIN_ADDRESS}: {exc}")

    print("Initializing Switch...")
    try:
        switch = MySwitch()
        switch.address = SWITCH_ADDRESS
        switch.connect()
        switch.open_all()
        print(f"  Connected to {switch.address}")
    except Exception as exc:
        switch = None
        init_errors.append(f"Switch: {exc}")
        print(f"  FAILED to connect to {SWITCH_ADDRESS}: {exc}")

if init_errors:
    print("\n" + "=" * 60)
    print("Instrument initialization completed with errors:")
    for err in init_errors:
        print(f"  - {err}")
    print("=" * 60)
else:
    print("\n" + "=" * 60)
    print("All instruments initialized successfully!")
    print("=" * 60)

class KeithleyGUI:
    def __init__(self):
        self.current = 0
        self.compliance_voltage = 3
        self.actual_current_a = 0
        self.actual_current_b = 0
        self.enabled = False
        self.rate = 0.01
        self.error_triggered = False
        self.is_ramping = False  # Flag to track if current is still ramping

    def enable_output(self):
        self.enabled = True
        if keithley is not None:
            keithley.enable_source(Ch="ab")
        self.error_triggered = False

    def disable_output(self):
        self.enabled = False
        if keithley is not None:
            keithley.disable_source(Ch='ab')
        self.actual_current_a = 0
        self.actual_current_b = 0

    def set_current(self, current):
        if current > 3:
            raise ValueError("Total current exceeds limit of 3 A")
        self.current = current / 2

    def set_compliance(self, voltage):
        self.compliance_voltage = voltage
        if keithley is not None:
            keithley.set_voltage_compliance(voltage, Ch="ab")

    def set_ramp_rate(self, rate):
        self.rate = rate / 1000

    def update_current(self):
        if not self.enabled:
            self.is_ramping = False
            return

        max_step = self.rate * 0.1  # Update every 100 ms
        all_zero = True
        still_ramping = False

        for ch in ['a', 'b']:
            actual = getattr(self, f'actual_current_{ch}')
            target = self.current
            delta = max_step if abs(target - actual) > max_step else abs(target - actual)
            if abs(target - actual) > 1e-6:
                actual += delta if actual < target else -delta
                actual = round(actual, 4)
                still_ramping = True  # Current is still being updated
            else:
                actual = round(target, 4)

            setattr(self, f'actual_current_{ch}', actual)
            if keithley is not None:
                keithley.set_current(actual, Ch=ch)
                keithley.apply_current(compliance_voltage=self.compliance_voltage, Ch=ch)

                if abs(actual * keithley.get_resistance(Ch=ch)) > self.compliance_voltage:
                    if not self.error_triggered:
                        self.error_triggered = True
                        self.disable_output()
                        self.is_ramping = False
                        return f"[{time.strftime('%H:%M:%S')}] Compliance voltage reached. Outputs disabled."

            if abs(actual) > 1e-6:
                all_zero = False

        # Update the ramping flag
        self.is_ramping = still_ramping

        if all_zero and self.current == 0:
            self.disable_output()
            self.is_ramping = False
            return f"[{time.strftime('%H:%M:%S')}] Current ramped to zero. Outputs disabled."

    def measure_resistance(self, ch):
        if not self.enabled:
            return None
        actual_current = getattr(self, f'actual_current_{ch}')
        if abs(actual_current) < 1e-6:
            return None
        if keithley is None:
            return None
        return keithley.get_resistance(Ch=ch)

class DualSMUGUI:
    def __init__(self, root):
        self.root = root
        self.device = KeithleyGUI()
        self.last_plot_time = time.time()
        self.plot_interval = tk.DoubleVar(value=1.0)
        self.time_data = []
        self.resistance_a = []
        self.resistance_b = []
        self.start_time = time.time()

        self.temp_data = []
        self.field_data = []
        self.time_data_dyna = []
        self.start_time_dyna = time.time()
        self.dyna_plot_interval = tk.DoubleVar(value=1.0)
        self.last_plot_time_dyna = time.time()

        # Results data
        self.results_data = []
        self.current_temp = None
        self.current_inplane_field = None
        self.current_helmholtz_current = 0
        self.current_helmholtz_field = 0
        self.measurement_start_time = None  # Set when script runs or first measurement
        self.time_offset = 0.0  # Time offset when appending to existing files

        # Data file management
        self.data_file = None
        self.csv_writer = None
        self.data_filename = None
        self.data_file_dir = Path("Data_Route")
        if not self.data_file_dir.exists():
            self.data_file_dir.mkdir(exist_ok=True)

        # Switch
        self.channels = ['a', 'b']
        self.channel_configs = {
            'a': {'I+': tk.IntVar(value=1), 'V+': tk.IntVar(value=2), 'V-': tk.IntVar(value=3), 'I-': tk.IntVar(value=4)},
            'b': {'I+': tk.IntVar(value=5), 'V+': tk.IntVar(value=6), 'V-': tk.IntVar(value=7), 'I-': tk.IntVar(value=8)}
        }
        self.active_channel = None

        # Script execution
        self.script_running = False
        self.script_paused = False
        self.script_thread = None
        self.current_script_line = 0
        self.script_filename = tk.StringVar(value="script.txt")
        self.script_dirty = False
        self.script_has_saved_path = False
        self.current_note = ""  # Note to add to next measurement

        # Instrument connection state and UI control registry
        self.instrument_connected = {
            "helmholtz": keithley is not None,
            "hall": keithley2450 is not None,
            "dyna": dyna is not None,
            "lockin": lockin is not None,
            "switch": switch is not None
        }
        self.tab_controls = {
            "helmholtz": [],
            "hall": [],
            "dyna": [],
            "lockin": [],
            "switch": []
        }
        self.widget_enabled_state = {}
        self.connection_ui = {}
        self.results_conn_leds = {}
        self._dyna_comm_lock = threading.Lock()
        self._dyna_snapshot_lock = threading.Lock()
        self._dyna_snapshot = {
            "temp_val": None,
            "field_val": None,
            "temp_text": "Temp: Disconnected",
            "field_text": "PPMS Field: Disconnected"
        }
        self._dyna_poller_stop = threading.Event()
        self._dyna_poller_thread = None
        self._pending_callbacks = []  # Track scheduled callbacks for cleanup
        self._update_ui_callback_id = None  # Track update_ui callback for cleanup
        self._results_plot_update_pending = False  # Coalesce frequent Results plot updates
        self._last_results_plot_update = 0.0
        self._results_plot_min_interval = 0.5  # seconds
        self._message_box_max_lines = 1000  # Limit message box size to prevent memory leak
        self._dyna_message_box_max_lines = 500  # Limit dyna message box size
        self._csv_lock = threading.Lock()  # Protect CSV write operations

        # Auto-logging system for continuous operation
        self.log_dir = Path("Logs")
        if not self.log_dir.exists():
            self.log_dir.mkdir(exist_ok=True)
        self.auto_log_file = None
        self.auto_log_writer = None
        self.auto_log_filename = None
        self.auto_log_max_size = 50 * 1024 * 1024  # 50MB per log file
        self.auto_log_enabled = tk.BooleanVar(value=True)
        self.auto_log_lock = threading.Lock()
        self._max_plot_points = 10000  # Keep only recent 10k points in memory for plots
        
        # Track when plots were reset to filter display
        self.dyna_plot_reset_time = None
        self.helmholtz_plot_reset_time = None
        
        # Photo annotation system (Switch tab)
        self.device_photo_path = None  # Path to current device photo
        self.photo_image = None  # PIL Image object
        self.photo_labels = {}  # {label_num: {"x": px, "y": px, "color": str}}
        self.selected_label = None  # Currently selected label for editing
        self.label_text_size = tk.IntVar(value=20)  # Font size for labels
        self.label_color = tk.StringVar(value="white")  # Current label color
        self.annotations_file = Path("device_annotations.json")  # Store annotations
        self.photo_canvas = None  # Will be created in create_switch_widgets
        self.dragging_label = None  # Which label is being dragged (if any)
        self.drag_offset = (0, 0)  # Mouse offset from label center when dragging
        self.label_placement_window = None  # Non-blocking popup for label placement
        self.label_buttons = {}  # Store references to label buttons (1-8) for state updates
        self.pause_button = None  # Script pause button (Results tab)

        root.title("Keithley and Dyna Controller GUI")
        # Window geometry will be set automatically after all widgets are created
        root.configure(bg="#000000")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Create main frame for the GUI
        main_frame = ttk.Frame(root)
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.keithley_tab = ttk.Frame(self.notebook)
        self.keithley2450_tab = ttk.Frame(self.notebook)
        self.dyna_tab = ttk.Frame(self.notebook)
        self.results_tab = ttk.Frame(self.notebook)
        self.switch_tab = ttk.Frame(self.notebook)
        self.lockin_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.results_tab, text="Results")
        self.notebook.add(self.dyna_tab, text="Dyna")
        self.notebook.add(self.keithley_tab, text="Helmholtz")
        self.notebook.add(self.lockin_tab, text="LockIn")
        self.notebook.add(self.keithley2450_tab, text="Hall bar")
        self.notebook.add(self.switch_tab, text="Switch")

        # Simple frames for control tabs
        self.left_frame = ttk.Frame(self.keithley_tab, padding=10)
        self.left_frame.grid(row=0, column=0, sticky="ns")

        self.right_frame = ttk.Frame(self.keithley_tab, width=460, height=350)
        self.right_frame.grid(row=0, column=1, sticky="nw", padx=(10, 0))
        self.right_frame.grid_propagate(False)

        self.keithley_tab.grid_columnconfigure(1, weight=0)
        self.keithley_tab.grid_rowconfigure(0, weight=0)

        self.dyna_left_frame = ttk.Frame(self.dyna_tab, padding=10)
        self.dyna_left_frame.grid(row=0, column=0, sticky="ns")

        self.dyna_right_frame = ttk.Frame(self.dyna_tab)
        self.dyna_right_frame.grid(row=0, column=1, sticky="nsew")

        self.create_widgets()
        self.create_keithley2450_widgets()
        self.create_dyna_widgets()
        self.create_results_widgets()
        self.create_switch_widgets()
        self.create_lockin_widgets()
        self._apply_connection_states()
        self._start_dyna_poller()
        
        # Initialize auto-logging if enabled
        if self.auto_log_enabled.get():
            self._initialize_auto_log()
        
        self.update_ui()
        
        # Auto-fit window to content with small padding
        root.update_idletasks()
        required_width = root.winfo_reqwidth()
        required_height = root.winfo_reqheight()
        window_width = required_width + 10
        window_height = required_height + 10
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        pos_x = max(0, (screen_width - window_width) // 2)
        pos_y = max(0, (screen_height - window_height) // 2)
        root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Show mockup mode warning if enabled (after window is displayed)
        if USE_MOCKUP:
            self.root.after(100, self._show_mockup_warning)

    def _show_mockup_warning(self):
        """Display mockup mode warning popup after window is shown"""
        messagebox.showwarning(
            "Mockup Mode Active",
            "⚠️ MOCKUP MODE ENABLED ⚠️\n\n"
            "The system is currently running with simulated instruments.\n"
            "No real hardware will be controlled.\n\n"
            "To use real instruments, set USE_MOCKUP = False in the code."
        )

    # ------------------------------
    # UI: Helmholtz tab
    # ------------------------------
    def create_widgets(self):
        self._create_connection_header(self.keithley_tab, "Helmholtz (K2600)", "helmholtz", columnspan=2)
        self.left_frame.grid_configure(row=1, column=0, sticky="ns")
        self.right_frame.grid_configure(row=1, column=1, sticky="nw", padx=(10, 0))
        self.keithley_tab.grid_rowconfigure(0, weight=0)
        self.keithley_tab.grid_rowconfigure(1, weight=1)

        def row(label, var, unit):
            l = ttk.Label(self.left_frame, text=label)
            l.grid(column=0, row=row.i, sticky='w', pady=5)
            e = ttk.Entry(self.left_frame, textvariable=var, width=10)
            e.grid(column=1, row=row.i)
            u = ttk.Label(self.left_frame, text=unit)
            u.grid(column=2, row=row.i, sticky='w')
            self._register_tab_control("helmholtz", e)
            row.i += 1
        row.i = 0

        self.set_current = tk.DoubleVar(value=0.0)
        self.compliance_voltage = tk.DoubleVar(value=10.0)
        self.ramp_rate = tk.DoubleVar(value=100)

        row("Current Output", self.set_current, "A")
        row("Compliance Voltage", self.compliance_voltage, "V")
        row("Ramp Rate", self.ramp_rate, "mA/s")
        row("Plot Interval", self.plot_interval, "s")

        set_button = ttk.Button(self.left_frame, text="Set", command=self.set_values)
        set_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("helmholtz", set_button)

        update_button = ttk.Button(self.left_frame, text="Update", command=self.set_values)
        update_button.grid(column=1, row=row.i, pady=10)
        self._register_tab_control("helmholtz", update_button)
        row.i += 1

        self.readout_a = tk.Label(self.left_frame, text="Ch A: -- A / -- Ω", font=("Courier", 14), fg="#FF6200", bg="#000000")
        self.readout_b = tk.Label(self.left_frame, text="Ch B: -- A / -- Ω", font=("Courier", 14), fg="#FF6200", bg="#000000")
        self.readout_a.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1
        self.readout_b.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1

        self.field_display = tk.Label(
            self.left_frame,
            text="Helmholtz Field: -- G",
            font=("Courier", 14),
            fg="#00A000",
            bg="#000000"
        )
        self.field_display.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1

        enable_button = ttk.Button(self.left_frame, text="Enable Output", command=self.enable_output)
        enable_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("helmholtz", enable_button)

        disable_button = ttk.Button(self.left_frame, text="Disable Output", command=self.disable_output)
        disable_button.grid(column=1, row=row.i, pady=10)
        self._register_tab_control("helmholtz", disable_button)

        reset_button = ttk.Button(self.left_frame, text="Reset Plot", command=self.reset_helmholtz_plot)
        reset_button.grid(column=2, row=row.i, pady=10)
        self._register_tab_control("helmholtz", reset_button)
        row.i += 1

        # Real-time Helmholtz resistance plot (Keithley 2600)
        self.fig_keithley = Figure(figsize=(4.8, 3.2))
        self.ax_keithley = self.fig_keithley.add_subplot(111)
        self.ax_keithley.set_title("Helmholtz Coils Resistance vs Time")
        self.ax_keithley.set_xlabel("Time [s]")
        self.ax_keithley.set_ylabel("Resistance [Ohm]")
        self.ax_keithley.grid(True, alpha=0.3)

        self.line_res_a, = self.ax_keithley.plot([], [], '-o', color='tab:blue', markersize=3, label='Ch A')
        self.line_res_b, = self.ax_keithley.plot([], [], '-o', color='tab:orange', markersize=3, label='Ch B')
        self.ax_keithley.legend(loc='upper left', fontsize=9)

        self.canvas_keithley = FigureCanvasTkAgg(self.fig_keithley, master=self.right_frame)
        self.toolbar_keithley = NavigationToolbar2Tk(self.canvas_keithley, self.right_frame)
        self.toolbar_keithley.update()
        self.canvas_keithley.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.fig_keithley.tight_layout()

    # ------------------------------
    # UI: Dyna tab
    # ------------------------------
    def create_dyna_widgets(self):
        self._create_connection_header(self.dyna_tab, "PPMS (Dyna)", "dyna", columnspan=2)
        self.dyna_left_frame.grid_configure(row=1, column=0, sticky="ns")
        self.dyna_right_frame.grid_configure(row=1, column=1, sticky="nsew")
        self.dyna_tab.grid_rowconfigure(1, weight=1)

        def row(frame, label, var, unit):
            l = ttk.Label(frame, text=label)
            l.grid(column=0, row=row.i, sticky='w', pady=5)
            e = ttk.Entry(frame, textvariable=var, width=10)
            e.grid(column=1, row=row.i)
            u = ttk.Label(frame, text=unit)
            u.grid(column=2, row=row.i, sticky='w')
            self._register_tab_control("dyna", e)
            row.i += 1
        row.i = 0

        self.set_temp = tk.DoubleVar(value=300.0)
        self.temp_rate = tk.DoubleVar(value=1.0)
        self.temp_mode = tk.StringVar(value="no_overshoot")

        row(self.dyna_left_frame, "Temperature", self.set_temp, "K")
        row(self.dyna_left_frame, "Temp Rate", self.temp_rate, "K/min")

        ttk.Label(self.dyna_left_frame, text="Temp Mode").grid(column=0, row=row.i, sticky='w', pady=5)
        mode_combo = ttk.Combobox(self.dyna_left_frame, textvariable=self.temp_mode, values=["fast_settle", "no_overshoot"], state="readonly")
        mode_combo.grid(column=1, row=row.i)
        self._register_tab_control("dyna", mode_combo)
        row.i += 1

        set_temp_button = ttk.Button(self.dyna_left_frame, text="Set Temp", command=self.set_temperature)
        set_temp_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("dyna", set_temp_button)
        row.i += 1

        ttk.Separator(self.dyna_left_frame, orient='horizontal').grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=10)
        row.i += 1

        self.set_field = tk.DoubleVar(value=0.0)
        self.field_rate = tk.DoubleVar(value=10.0)
        self.field_mode = tk.StringVar(value="no_overshoot")

        row(self.dyna_left_frame, "Field", self.set_field, "Oe")
        row(self.dyna_left_frame, "Field Rate", self.field_rate, "Oe/s")

        ttk.Label(self.dyna_left_frame, text="Field Mode").grid(column=0, row=row.i, sticky='w', pady=5)
        field_mode_combo = ttk.Combobox(self.dyna_left_frame, textvariable=self.field_mode, values=["linear", "no_overshoot", "oscillate"], state="readonly")
        field_mode_combo.grid(column=1, row=row.i)
        self._register_tab_control("dyna", field_mode_combo)
        row.i += 1

        set_field_button = ttk.Button(self.dyna_left_frame, text="Set Field", command=self.set_field_cmd)
        set_field_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("dyna", set_field_button)
        row.i += 1

        ttk.Separator(self.dyna_left_frame, orient='horizontal').grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=10)
        row.i += 1

        row(self.dyna_left_frame, "Dyna Plot Interval", self.dyna_plot_interval, "s")

        self.temp_display = tk.Label(self.dyna_left_frame, text="Temp: -- K", font=("Courier", 14), fg="#FF6200", bg="#000000")
        self.temp_display.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1

        self.field_display_dyna = tk.Label(self.dyna_left_frame, text="PPMS Field: -- Oe", font=("Courier", 14), fg="#00A000", bg="#000000")
        self.field_display_dyna.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1

        self.dyna_message_box = tk.Text(self.dyna_left_frame, height=3, width=50, font=("Courier", 10), wrap="word", state="disabled", bg="lightgray")
        self.dyna_message_box.grid(column=0, row=row.i, columnspan=3, pady=10)
        row.i += 1

        reset_plot_button = ttk.Button(self.dyna_left_frame, text="Reset Plot", command=self.reset_plot)
        reset_plot_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("dyna", reset_plot_button)
        row.i += 1

        # Auto-logging section
        ttk.Separator(self.dyna_left_frame, orient='horizontal').grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=10)
        row.i += 1

        ttk.Label(self.dyna_left_frame, text="Auto Data Logging:", font=("Arial", 10, "bold")).grid(column=0, row=row.i, columnspan=3, sticky='w', pady=(0, 5))
        row.i += 1

        log_enable_check = ttk.Checkbutton(self.dyna_left_frame, text="Enable Auto-Logging", variable=self.auto_log_enabled, command=self._toggle_auto_logging)
        log_enable_check.grid(column=0, row=row.i, columnspan=2, sticky='w', pady=2)
        row.i += 1

        self.log_dir_display = tk.Label(self.dyna_left_frame, text=f"Dir: {self.log_dir}", font=("Courier", 9), fg="#0000FF", bg="#F0F0F0", anchor='w', relief="sunken")
        self.log_dir_display.grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=2)
        row.i += 1

        change_dir_button = ttk.Button(self.dyna_left_frame, text="Change Log Dir", command=self._change_log_directory)
        change_dir_button.grid(column=0, row=row.i, columnspan=2, pady=5)
        row.i += 1

        self.log_file_display = tk.Label(self.dyna_left_frame, text="Log: Not started", font=("Courier", 8), fg="#006600", bg="#F0F0F0", anchor='w', relief="sunken", wraplength=350)
        self.log_file_display.grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=2)
        row.i += 1

        self.fig_dyna = Figure(figsize=(5, 4))
        self.ax_dyna_temp = self.fig_dyna.add_subplot(211)
        self.ax_dyna_temp.set_title("Temperature vs Time")
        self.ax_dyna_temp.set_ylabel("Temperature [K]")
        self.ax_dyna_field = self.fig_dyna.add_subplot(212)
        self.ax_dyna_field.set_title("Field vs Time")
        self.ax_dyna_field.set_ylabel("Field [Oe]")
        self.ax_dyna_field.set_xlabel("Time [s]")
        self.canvas_dyna = FigureCanvasTkAgg(self.fig_dyna, master=self.dyna_right_frame)
        self.toolbar_dyna = NavigationToolbar2Tk(self.canvas_dyna, self.dyna_right_frame)
        self.toolbar_dyna.update()
        self.canvas_dyna.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.line_temp, = self.ax_dyna_temp.plot([], [], '-o', color='tab:red', markersize=4)
        self.line_field, = self.ax_dyna_field.plot([], [], '-o', color='tab:green', markersize=4)
        self.fig_dyna.tight_layout()

    # ------------------------------
    # UI: Results tab
    # ------------------------------
    def create_results_widgets(self):
        self.results_left_frame = ttk.Frame(self.results_tab, padding=10)
        self.results_left_frame.grid(row=0, column=0, sticky="ns")

        self.results_middle_frame = ttk.Frame(self.results_tab, padding=10)
        self.results_middle_frame.grid(row=0, column=1, sticky="ns")

        self.results_right_frame = ttk.Frame(self.results_tab)
        self.results_right_frame.grid(row=0, column=2, sticky="nsew")

        # Graph controls (upper-left), stacked vertically for better fit
        graph_controls_frame = ttk.LabelFrame(self.results_left_frame, text="Graph Controls", padding=6)
        graph_controls_frame.grid(column=0, row=0, sticky='ew', pady=(0, 8))

        # Get available columns for axis selection
        self.available_columns = [
            "Time(s)", "Temp(K)", "Field(Oe)", "Helmholtz_Current(A)", "Helmholtz_Field(G)",
            "Hall_Voltage(V)", "Hall_Voltage_Error(V)", "Hall_Field(G)", "Hall_Field_Error(G)",
            "X_a(V)", "X_a_Error(V)", "Y_a(V)", "Y_a_Error(V)", "R_a(V)", "R_a_Error(V)", "Theta_a(deg)", "Theta_a_Error(deg)",
            "X_b(V)", "X_b_Error(V)", "Y_b(V)", "Y_b_Error(V)", "R_b(V)", "R_b_Error(V)", "Theta_b(deg)", "Theta_b_Error(deg)",
            "Frequency(Hz)", "Sensitivity(V)", "Resistor(Ohm)", "Output_Voltage(V)", "Output_Current(A)",
            "Time_Constant(s)", "Sample_a_Resistance(Ohm)", "Sample_a_Resistance_Error(Ohm)", "Sample_b_Resistance(Ohm)", "Sample_b_Resistance_Error(Ohm)"
        ]

        # Graph 1 controls
        g1_frame = ttk.LabelFrame(graph_controls_frame, text="Graph 1", padding=6)
        g1_frame.grid(column=0, row=0, sticky='ew', pady=(0, 8))

        ttk.Label(g1_frame, text="X1:").grid(column=0, row=0, sticky='w', padx=(0, 5), pady=2)
        self.x1_var = tk.StringVar(value="Time(s)")
        x1_menu = ttk.Combobox(g1_frame, textvariable=self.x1_var, values=self.available_columns, width=18, state="readonly")
        x1_menu.grid(column=1, row=0, sticky='ew', pady=2)
        x1_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())

        ttk.Label(g1_frame, text="Y:").grid(column=0, row=1, sticky='w', padx=(0, 5), pady=2)
        self.y1_var = tk.StringVar(value="Hall_Field(G)")
        y1_menu = ttk.Combobox(g1_frame, textvariable=self.y1_var, values=self.available_columns, width=18, state="readonly")
        y1_menu.grid(column=1, row=1, sticky='ew', pady=2)
        y1_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())
        
        ttk.Label(g1_frame, text="Style:").grid(column=0, row=2, sticky='w', padx=(0, 5), pady=2)
        self.graph1_style = tk.StringVar(value="Line + Markers")
        g1_style_menu = ttk.Combobox(
            g1_frame,
            textvariable=self.graph1_style,
            values=["Line + Markers", "Markers Only", "Line Only"],
            width=18,
            state="readonly"
        )
        g1_style_menu.grid(column=1, row=2, sticky='ew', pady=2)
        g1_style_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())
        g1_frame.grid_columnconfigure(1, weight=1)

        # Graph 2 controls
        g2_frame = ttk.LabelFrame(graph_controls_frame, text="Graph 2", padding=6)
        g2_frame.grid(column=0, row=1, sticky='ew')

        ttk.Label(g2_frame, text="X2:").grid(column=0, row=0, sticky='w', padx=(0, 5), pady=2)
        self.x2_var = tk.StringVar(value="Time(s)")
        x2_menu = ttk.Combobox(g2_frame, textvariable=self.x2_var, values=self.available_columns, width=18, state="readonly")
        x2_menu.grid(column=1, row=0, sticky='ew', pady=2)
        x2_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())

        ttk.Label(g2_frame, text="Y:").grid(column=0, row=1, sticky='w', padx=(0, 5), pady=2)
        self.y2_var = tk.StringVar(value="R_a(V)")
        y2_menu = ttk.Combobox(g2_frame, textvariable=self.y2_var, values=self.available_columns, width=18, state="readonly")
        y2_menu.grid(column=1, row=1, sticky='ew', pady=2)
        y2_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())
        
        ttk.Label(g2_frame, text="Style:").grid(column=0, row=2, sticky='w', padx=(0, 5), pady=2)
        self.graph2_style = tk.StringVar(value="Line + Markers")
        g2_style_menu = ttk.Combobox(
            g2_frame,
            textvariable=self.graph2_style,
            values=["Line + Markers", "Markers Only", "Line Only"],
            width=18,
            state="readonly"
        )
        g2_style_menu.grid(column=1, row=2, sticky='ew', pady=2)
        g2_style_menu.bind("<<ComboboxSelected>>", lambda e: self.update_plots())
        g2_frame.grid_columnconfigure(1, weight=1)

        graph_controls_frame.grid_columnconfigure(0, weight=1)

        # LED Indicator section
        ttk.Label(self.results_left_frame, text="Status Indicators:", font=("Arial", 10, "bold")).grid(column=0, row=2, sticky='w', pady=(8, 3))
        
        # LockIn LED
        led_frame_lockin = ttk.Frame(self.results_left_frame)
        led_frame_lockin.grid(column=0, row=3, sticky='w', pady=1)
        self.led_lockin = tk.Label(led_frame_lockin, text="●", font=("Arial", 12), fg="#FF0000")
        self.led_lockin.pack(side=tk.LEFT, padx=3)
        ttk.Label(led_frame_lockin, text="LockIn").pack(side=tk.LEFT)
        
        # Hall Bar LED
        led_frame_hall = ttk.Frame(self.results_left_frame)
        led_frame_hall.grid(column=0, row=4, sticky='w', pady=1)
        self.led_hall = tk.Label(led_frame_hall, text="●", font=("Arial", 12), fg="#FF0000")
        self.led_hall.pack(side=tk.LEFT, padx=3)
        ttk.Label(led_frame_hall, text="Hall Bar").pack(side=tk.LEFT)
        
        # Switch LED
        led_frame_switch = ttk.Frame(self.results_left_frame)
        led_frame_switch.grid(column=0, row=5, sticky='w', pady=1)
        self.led_switch = tk.Label(led_frame_switch, text="●", font=("Arial", 12), fg="#FF0000")
        self.led_switch.pack(side=tk.LEFT, padx=3)
        ttk.Label(led_frame_switch, text="Switch").pack(side=tk.LEFT)
        
        # Initialize LED state tracking
        self.led_switch_blinking = False
        self.led_switch_blink_id = None

        # System Status Displays section
        ttk.Separator(self.results_left_frame, orient='horizontal').grid(column=0, row=6, sticky='ew', pady=6)
        ttk.Label(self.results_left_frame, text="System Status:", font=("Arial", 11, "bold")).grid(column=0, row=7, sticky='w', pady=(3, 2))
        
        # PPMS/Dyna displays
        ppms_header = ttk.Frame(self.results_left_frame)
        ppms_header.grid(column=0, row=8, sticky='w', pady=(3, 1))
        ppms_led = tk.Label(ppms_header, text="●", font=("Arial", 10), fg="#FF0000")
        ppms_led.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(ppms_header, text="PPMS:", font=("Arial", 10, "bold", "underline")).pack(side=tk.LEFT)
        self.results_conn_leds["dyna"] = ppms_led
        self.results_dyna_temp = tk.Label(self.results_left_frame, text="Temp: -- K", font=("Courier", 11, "bold"), fg="#664400", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_dyna_temp.grid(column=0, row=9, sticky='ew', pady=2, padx=(10, 0))
        self.results_dyna_field = tk.Label(self.results_left_frame, text="PPMS Field: -- Oe", font=("Courier", 11, "bold"), fg="#006600", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_dyna_field.grid(column=0, row=10, sticky='ew', pady=2, padx=(10, 0))
        
        # Helmholtz displays
        helm_header = ttk.Frame(self.results_left_frame)
        helm_header.grid(column=0, row=11, sticky='w', pady=(5, 1))
        helm_led = tk.Label(helm_header, text="●", font=("Arial", 10), fg="#FF0000")
        helm_led.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(helm_header, text="Helmholtz:", font=("Arial", 10, "bold", "underline")).pack(side=tk.LEFT)
        self.results_conn_leds["helmholtz"] = helm_led
        self.results_helmholtz_field = tk.Label(self.results_left_frame, text="Field: -- G", font=("Courier", 11, "bold"), fg="#006600", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_helmholtz_field.grid(column=0, row=12, sticky='ew', pady=2, padx=(10, 0))
        self.results_helmholtz_ch_a = tk.Label(self.results_left_frame, text="Ch A: -- A / -- Ω", font=("Courier", 11, "bold"), fg="#003388", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_helmholtz_ch_a.grid(column=0, row=13, sticky='ew', pady=2, padx=(10, 0))
        self.results_helmholtz_ch_b = tk.Label(self.results_left_frame, text="Ch B: -- A / -- Ω", font=("Courier", 11, "bold"), fg="#664400", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_helmholtz_ch_b.grid(column=0, row=14, sticky='ew', pady=2, padx=(10, 0))
        
        # Hall Bar displays
        hall_header = ttk.Frame(self.results_left_frame)
        hall_header.grid(column=0, row=15, sticky='w', pady=(5, 1))
        hall_led = tk.Label(hall_header, text="●", font=("Arial", 10), fg="#FF0000")
        hall_led.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(hall_header, text="Hall Bar (K2450):", font=("Arial", 10, "bold", "underline")).pack(side=tk.LEFT)
        self.results_conn_leds["hall"] = hall_led
        self.results_hall_voltage = tk.Label(self.results_left_frame, text="Voltage: -- V", font=("Courier", 11, "bold"), fg="#006600", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_hall_voltage.grid(column=0, row=16, sticky='ew', pady=2, padx=(10, 0))
        self.results_hall_field = tk.Label(self.results_left_frame, text="Field: -- G", font=("Courier", 11, "bold"), fg="#006600", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_hall_field.grid(column=0, row=17, sticky='ew', pady=2, padx=(10, 0))
        
        # LockIn displays
        lockin_header = ttk.Frame(self.results_left_frame)
        lockin_header.grid(column=0, row=18, sticky='w', pady=(5, 1))
        lockin_led = tk.Label(lockin_header, text="●", font=("Arial", 10), fg="#FF0000")
        lockin_led.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(lockin_header, text="LockIn:", font=("Arial", 10, "bold", "underline")).pack(side=tk.LEFT)
        self.results_conn_leds["lockin"] = lockin_led
        self.results_lockin_x = tk.Label(self.results_left_frame, text="X: -- V", font=("Courier", 11, "bold"), fg="#663366", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_lockin_x.grid(column=0, row=19, sticky='ew', pady=2, padx=(10, 0))
        self.results_lockin_y = tk.Label(self.results_left_frame, text="Y: -- V", font=("Courier", 11, "bold"), fg="#663366", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_lockin_y.grid(column=0, row=20, sticky='ew', pady=2, padx=(10, 0))
        self.results_lockin_r = tk.Label(self.results_left_frame, text="R: -- V", font=("Courier", 11, "bold"), fg="#663366", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_lockin_r.grid(column=0, row=21, sticky='ew', pady=2, padx=(10, 0))
        self.results_lockin_phase = tk.Label(self.results_left_frame, text="Phase: -- °", font=("Courier", 11, "bold"), fg="#663366", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_lockin_phase.grid(column=0, row=22, sticky='ew', pady=2, padx=(10, 0))

        # Switch status
        switch_header = ttk.Frame(self.results_left_frame)
        switch_header.grid(column=0, row=23, sticky='w', pady=(5, 1))
        switch_led = tk.Label(switch_header, text="●", font=("Arial", 10), fg="#FF0000")
        switch_led.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(switch_header, text="Switch:", font=("Arial", 10, "bold", "underline")).pack(side=tk.LEFT)
        self.results_conn_leds["switch"] = switch_led
        self.results_switch_status = tk.Label(self.results_left_frame, text="Switch: --", font=("Courier", 11, "bold"), fg="#006600", bg="#FFFFFF", anchor='w', width=26, relief="solid", borderwidth=1)
        self.results_switch_status.grid(column=0, row=24, sticky='ew', pady=2, padx=(10, 0))

        # Script control section - moved to middle frame
        ttk.Label(self.results_middle_frame, text="Script Control:", font=("Arial", 10, "bold")).grid(column=0, row=0, columnspan=3, sticky='w', pady=(0,5))

        # Script buttons
        script_button_frame = ttk.Frame(self.results_middle_frame)
        script_button_frame.grid(column=0, row=1, columnspan=3, pady=5)

        ttk.Button(script_button_frame, text="Run Script", command=self.run_script).grid(column=0, row=0, padx=2)
        ttk.Button(script_button_frame, text="Load Script", command=self.load_script).grid(column=1, row=0, padx=2)
        ttk.Button(script_button_frame, text="Save Script", command=self.save_script_as).grid(column=2, row=0, padx=2)
        self.pause_button = ttk.Button(script_button_frame, text="Pause", command=self.pause_script)
        self.pause_button.grid(column=3, row=0, padx=2)
        ttk.Button(script_button_frame, text="Abort", command=self.abort_script).grid(column=4, row=0, padx=2)

        # Script status
        self.script_status = tk.StringVar(value="Status: Idle")
        ttk.Label(self.results_middle_frame, textvariable=self.script_status, font=("Courier", 10), background="#f0f0f0", relief="sunken").grid(column=0, row=2, columnspan=3, sticky='ew', pady=5)

        # Message box
        self.message_box = tk.Text(self.results_middle_frame, height=3, width=50, font=("Courier", 10), wrap="word", state="disabled", bg="lightgray")
        self.message_box.grid(column=0, row=3, columnspan=3, pady=10)

        # Script editor
        ttk.Label(self.results_middle_frame, text="Script Editor:", font=("Arial", 10, "bold")).grid(column=0, row=4, columnspan=3, sticky='w', pady=(10,5))

        # Script text area
        script_frame = ttk.Frame(self.results_middle_frame)
        script_frame.grid(column=0, row=5, columnspan=3, sticky='nsew', pady=5)

        self.script_text = tk.Text(script_frame, height=10, width=50, font=("Courier", 10))
        script_scrollbar = ttk.Scrollbar(script_frame, orient="vertical", command=self.script_text.yview)
        self.script_text.configure(yscrollcommand=script_scrollbar.set)
        self.script_text.bind("<<Modified>>", self._on_script_modified)
        
        # Configure tag for highlighting current line
        self.script_text.tag_configure("current_line", background="#FFFF99", foreground="black")
        
        # Configure tag for highlighting loop body line (red highlight)
        self.script_text.tag_configure("loop_body_line", background="#FF9999", foreground="black")

        self.script_text.pack(side="left", fill="both", expand=True)
        script_scrollbar.pack(side="right", fill="y")

        # Configure grid weights for proper resizing
        self.results_middle_frame.grid_rowconfigure(5, weight=1)
        self.results_middle_frame.grid_columnconfigure(0, weight=1)
        self.results_tab.grid_columnconfigure(2, weight=1)

        # Create results graphs (two stacked subplots)
        self.fig = Figure(figsize=(6, 7))
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)
        
        self.ax1.set_title("Graph 1")
        self.ax2.set_title("Graph 2")
        
        # Pack canvas in right frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.results_right_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.results_right_frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.fig.subplots_adjust(left=0.16, right=0.97, top=0.95, bottom=0.10, hspace=0.48)

    def plot_results(self):
        """
        Update plots using the new flexible dual-graph system.
        Automatically called when dropdown selections change.
        """
        self.update_plots()

    # Plot helpers (Results, Dyna, Helmholtz)
    def reset_plot(self):
        """Reset only the Dyna tab graphs - clears display and shows only future data."""
        # Clear Dyna plot data in memory
        self.time_data_dyna.clear()
        self.temp_data.clear()
        self.field_data.clear()
        
        # Mark reset time to filter future data display
        self.dyna_plot_reset_time = time.time()
        
        # Reset time reference
        self.start_time_dyna = time.time()
        self.last_plot_time_dyna = time.time()

        # Update Dyna graph axes
        self.update_dyna_plot()
        self.canvas_dyna.draw()

        self.log_message(f"[{time.strftime('%H:%M:%S')}] Dyna plot reset - showing only new data.")
        self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] Dyna plot reset - showing only new data.")

    def reset_helmholtz_plot(self):
        """Reset only the Helmholtz resistance plot - clears display and shows only future data."""
        # Clear Helmholtz plot data in memory
        self.time_data.clear()
        self.resistance_a.clear()
        self.resistance_b.clear()
        
        # Mark reset time to filter future data display
        self.helmholtz_plot_reset_time = time.time()
        
        # Reset time reference
        self.start_time = time.time()
        self.line_res_a.set_data([], [])
        self.line_res_b.set_data([], [])
        self.ax_keithley.set_xlim(0, 1)
        self.ax_keithley.set_ylim(-0.05, 0.05)
        self.canvas_keithley.draw()
        self.log_message(f"[{time.strftime('%H:%M:%S')}] Helmholtz plot reset - showing only new data.")

    def update_plots(self):
        """
        Update both Results graphs from the active CSV file.
        Auto-called when any axis dropdown changes.
        """
        try:

            # Return early if no data file
            if self.data_filename is None or not Path(self.data_filename).exists():
                return

            # Read CSV data
            df = pd.read_csv(self.data_filename)

            # ──── Update Graph 1 ────
            self._update_single_graph(
                self.ax1,
                self.x1_var.get(), self.y1_var.get(),
                df,
                self.graph1_style.get()
            )

            # ──── Update Graph 2 ────
            self._update_single_graph(
                self.ax2,
                self.x2_var.get(), self.y2_var.get(),
                df,
                self.graph2_style.get()
            )

            self.fig.tight_layout(pad=1.2, h_pad=2.0)
            self.canvas.draw()
        except Exception as e:
            self.log_message(f"Error updating plots: {e}")

    def _update_single_graph(self, ax, x_col, y_col, df, plot_style):
        """
        Update a single graph from the DataFrame, skipping NaN values.

        Parameters
        ----------
        ax : matplotlib axis
            Axis to plot on
        x_col : str
            Column name for X-axis
        y_col : str
            Column name for Y-axis
        df : pandas.DataFrame
            Data to plot
        plot_style : str
            One of: "Line + Markers", "Markers Only", "Line Only"
        """
        ax.clear()

        # Check if columns exist
        if x_col not in df.columns or y_col not in df.columns:
            ax.text(0.5, 0.5, "Invalid column selection", ha='center', va='center', transform=ax.transAxes)
            ax.set_title("Error")
            return

        # Extract data, removing rows where EITHER x or y is NaN (preserves row correspondence)
        df_clean = df[[x_col, y_col]].dropna()
        x_data = df_clean[x_col].values
        y_data = df_clean[y_col].values

        if len(x_data) > 0 and len(y_data) > 0:
            style_map = {
                "Markers Only": 'o',
                "Line Only": '-',
                "Line + Markers": '-o'
            }
            line_style = style_map.get(plot_style, '-o')
            ax.plot(x_data, y_data, line_style, color='#1f77b4', label=y_col, markersize=3)
            ax.set_xlabel(x_col, fontsize=9, labelpad=8)
            ax.set_ylabel(y_col, fontsize=9, labelpad=8)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.set_title(f"{y_col} vs {x_col}", fontsize=10, pad=10)

    def update_dyna_plot(self):
        """Update Dyna temperature and field plots."""
        self.line_temp.set_data(self.time_data_dyna, self.temp_data)
        self.line_field.set_data(self.time_data_dyna, self.field_data)
        if len(self.time_data_dyna) > 1:
            xlim = (max(0, self.time_data_dyna[0]), self.time_data_dyna[-1])
            self.ax_dyna_temp.set_xlim(xlim)
            self.ax_dyna_field.set_xlim(xlim)
            if self.temp_data:
                min_temp = min(self.temp_data)
                max_temp = max(self.temp_data)
                if min_temp == max_temp:
                    if min_temp == 0:
                        self.ax_dyna_temp.set_ylim(-1, 1)
                    else:
                        self.ax_dyna_temp.set_ylim(min_temp * 0.99, min_temp * 1.01)
                else:
                    self.ax_dyna_temp.set_ylim(min_temp * 0.9, max_temp * 1.1)
            if self.field_data:
                min_field = min(self.field_data)
                max_field = max(self.field_data)
                if min_field == max_field:
                    if min_field == 0:
                        self.ax_dyna_field.set_ylim(-1, 1)
                    else:
                        self.ax_dyna_field.set_ylim(min_field * 0.99, min_field * 1.01)
                else:
                    self.ax_dyna_field.set_ylim(min_field * 0.9, max_field * 1.1)
        self.canvas_dyna.draw()

    def update_plot(self):
        """Update real-time Helmholtz resistance plot."""
        self.line_res_a.set_data(self.time_data, self.resistance_a)
        self.line_res_b.set_data(self.time_data, self.resistance_b)

        if len(self.time_data) > 1:
            self.ax_keithley.set_xlim(max(0, self.time_data[0]), self.time_data[-1])

            all_resistances = []
            all_resistances.extend([v for v in self.resistance_a if v is not None])
            all_resistances.extend([v for v in self.resistance_b if v is not None])

            if all_resistances:
                min_res = min(all_resistances)
                max_res = max(all_resistances)
                if min_res == max_res:
                    pad = 1.0 if min_res == 0 else abs(min_res) * 0.01
                    self.ax_keithley.set_ylim(min_res - pad, max_res + pad)
                else:
                    span = max_res - min_res
                    pad = span * 0.1
                    self.ax_keithley.set_ylim(min_res - pad, max_res + pad)

        self.canvas_keithley.draw()

    # ------------------------------
    # UI helpers (LEDs, logging)
    # ------------------------------
    def led_on(self, led_type):
        """Turn on a specific LED (green) - thread-safe"""
        def update_led():
            if led_type == "lockin":
                self.led_lockin.config(fg="#00FF00")
            elif led_type == "hall":
                self.led_hall.config(fg="#00FF00")
            elif led_type == "switch":
                self.led_switch.config(fg="#00FF00")
        
        # Schedule on main thread if called from worker thread (use 50ms for batching)
        try:
            self.root.after(50, update_led)
        except:
            # Fallback if root is not available
            update_led()
    
    def led_off(self, led_type):
        """Turn off a specific LED (red) - thread-safe"""
        def update_led():
            if led_type == "lockin":
                self.led_lockin.config(fg="#FF0000")
            elif led_type == "hall":
                self.led_hall.config(fg="#FF0000")
            elif led_type == "switch":
                # Stop blinking if active
                if self.led_switch_blink_id is not None:
                    try:
                        self.root.after_cancel(self.led_switch_blink_id)
                    except:
                        pass
                    self.led_switch_blink_id = None
                self.led_switch_blinking = False
                self.led_switch.config(fg="#FF0000")
        
        # Schedule on main thread if called from worker thread (use 50ms for batching)
        try:
            self.root.after(50, update_led)
        except:
            # Fallback if root is not available
            update_led()
    
    def led_blink(self, led_type, duration_ms=100):
        """Blink a specific LED"""
        if led_type == "switch":
            if self.led_switch_blinking:
                return  # Already blinking
            self.led_switch_blinking = True
            self._toggle_led_blink(duration_ms)
    
    def _toggle_led_blink(self, duration_ms):
        """Toggle LED blink state"""
        if not self.led_switch_blinking:
            return
        
        try:
            if not self.root.winfo_exists():
                return
            
            current_color = self.led_switch.cget("fg")
            new_color = "#FF0000" if current_color == "#00FF00" else "#00FF00"
            self.led_switch.config(fg=new_color)
            
            if self.led_switch_blinking:  # Check again before rescheduling
                self.led_switch_blink_id = self.root.after(duration_ms, self._toggle_led_blink, duration_ms)
                self._pending_callbacks.append(self.led_switch_blink_id)
        except:
            pass  # Widget may have been destroyed

    # ------------------------------
    # Instrument connection helpers
    # ------------------------------
    def _register_tab_control(self, instrument_key, widget, enabled_state=None):
        self.tab_controls[instrument_key].append(widget)
        if enabled_state is None:
            try:
                enabled_state = widget.cget("state")
            except Exception:
                enabled_state = "normal"
        self.widget_enabled_state[widget] = enabled_state

    def _set_tab_controls_enabled(self, instrument_key, enabled):
        for widget in self.tab_controls.get(instrument_key, []):
            try:
                if enabled:
                    widget.configure(state=self.widget_enabled_state.get(widget, "normal"))
                else:
                    widget.configure(state="disabled")
            except Exception:
                try:
                    widget.state(["!disabled"] if enabled else ["disabled"])
                except Exception:
                    pass

    def _create_connection_header(self, parent, label, instrument_key, columnspan=1):
        frame = ttk.Frame(parent, padding=2)
        frame.grid(row=0, column=0, columnspan=columnspan, sticky="ew")
        frame.grid_columnconfigure(3, weight=1)

        led = tk.Label(frame, text="●", font=("Arial", 12), fg="#00FF00")
        led.grid(row=0, column=0, sticky="w", padx=(0, 6))

        status_label = ttk.Label(frame, text=f"{label}: Connected")
        status_label.grid(row=0, column=1, sticky="w")

        button = ttk.Button(frame, text="Disconnect", command=lambda: self._toggle_instrument_connection(instrument_key))
        button.grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.connection_ui[instrument_key] = {
            "frame": frame,
            "led": led,
            "status": status_label,
            "button": button,
            "label": label
        }

    def _apply_connection_states(self):
        for instrument_key, connected in self.instrument_connected.items():
            self._set_instrument_connected(instrument_key, connected, update_controls=True)

    def _set_instrument_connected(self, instrument_key, connected, update_controls=True):
        self.instrument_connected[instrument_key] = connected
        ui = self.connection_ui.get(instrument_key)
        if ui:
            color = "#00FF00" if connected else "#FF0000"
            text = "Connected" if connected else "Disconnected"
            ui["led"].config(fg=color)
            ui["status"].config(text=f"{ui['label']}: {text}")
            ui["button"].config(text="Disconnect" if connected else "Connect")
        results_led = self.results_conn_leds.get(instrument_key)
        if results_led:
            results_led.config(fg="#00FF00" if connected else "#FF0000")
        if update_controls:
            self._set_tab_controls_enabled(instrument_key, connected)

    def _toggle_instrument_connection(self, instrument_key):
        if self.instrument_connected.get(instrument_key, False):
            self._disconnect_instrument(instrument_key)
        else:
            self._connect_instrument(instrument_key)

    def _connect_instrument(self, instrument_key):
        success = False
        if instrument_key == "helmholtz":
            success = self._connect_helmholtz()
        elif instrument_key == "hall":
            success = self._connect_hall()
        elif instrument_key == "dyna":
            success = self._connect_dyna()
        elif instrument_key == "lockin":
            success = self._connect_lockin()
        elif instrument_key == "switch":
            success = self._connect_switch()

        self._set_instrument_connected(instrument_key, success, update_controls=True)

    def _disconnect_instrument(self, instrument_key):
        if instrument_key == "helmholtz":
            self._disconnect_helmholtz()
        elif instrument_key == "hall":
            self._disconnect_hall()
        elif instrument_key == "dyna":
            self._disconnect_dyna()
        elif instrument_key == "lockin":
            self._disconnect_lockin()
        elif instrument_key == "switch":
            self._disconnect_switch()

        self._set_instrument_connected(instrument_key, False, update_controls=True)

    def _connect_helmholtz(self):
        global keithley
        try:
            keithley = Keithley2600()
            if not USE_MOCKUP:
                keithley.address = KEITHLEY2600_ADDRESS
            keithley.connect()
            keithley.reset()
            keithley.set_4wires(wires4=False, Ch="ab")
            try:
                self.device.disable_output()
            except Exception:
                pass
            self.log_message("Helmholtz connected")
            return True
        except Exception as exc:
            keithley = None
            self.log_message(f"ERROR: Failed to connect Helmholtz: {exc}")
            return False

    def _disconnect_helmholtz(self):
        global keithley
        try:
            try:
                self.device.disable_output()
            except Exception:
                pass
            if keithley is not None:
                try:
                    keithley.disable_source(Ch="ab")
                except Exception:
                    pass
                try:
                    keithley.disconnect()
                except Exception:
                    pass
        finally:
            keithley = None
            self.log_message("Helmholtz disconnected")

    def _connect_hall(self):
        global keithley2450
        try:
            keithley2450 = Keithley2450Wrapper(KEITHLEY2450_ADDRESS)
            if not USE_MOCKUP:
                keithley2450.query("*IDN?")
            keithley2450.connect()
            keithley2450.reset()
            self.log_message("Keithley 2450 connected")
            return True
        except Exception as exc:
            keithley2450 = None
            self.log_message(f"ERROR: Failed to connect Keithley 2450: {exc}")
            return False

    def _disconnect_hall(self):
        global keithley2450
        try:
            if keithley2450 is not None:
                try:
                    keithley2450.disable_source()
                except Exception:
                    pass
                try:
                    keithley2450.shutdown()
                except Exception:
                    pass
                try:
                    keithley2450.disconnect()
                except Exception:
                    pass
        finally:
            keithley2450 = None
            self.log_message("Keithley 2450 disconnected")

    def _connect_dyna(self):
        global dyna
        try:
            dyna = DynaClass(DYNA_HOST, DYNA_PORT)
            result = self._dyna_call("connect")
            if result is False:
                raise RuntimeError("PPMS connection failed")
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] Dyna connected")
            return True
        except Exception as exc:
            dyna = None
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: Dyna connect failed: {exc}")
            return False

    def _disconnect_dyna(self):
        global dyna
        try:
            if dyna is not None:
                self._dyna_call("disconnect")
                self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] Dyna disconnected")
        except Exception as exc:
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: Dyna disconnect failed: {exc}")
        finally:
            dyna = None

    def _connect_lockin(self):
        global lockin
        try:
            if USE_MOCKUP:
                lockin = LockInSR830()
            else:
                lockin = LockInSR830(resource=LOCKIN_ADDRESS)
            try:
                lockin.initialize_default_state(reset=False)
            except Exception:
                pass
            self.log_message("LockIn connected")
            return True
        except Exception as exc:
            lockin = None
            self.log_message(f"ERROR: Failed to connect LockIn: {exc}")
            return False

    def _disconnect_lockin(self):
        global lockin
        try:
            if lockin is not None:
                try:
                    lockin.sine_output_off()
                except Exception:
                    pass
                try:
                    if hasattr(lockin, "inst"):
                        lockin.inst.close()
                    if hasattr(lockin, "rm"):
                        lockin.rm.close()
                except Exception:
                    pass
        finally:
            lockin = None
            self.log_message("LockIn disconnected")

    def _connect_switch(self):
        global switch
        try:
            switch = MySwitch()
            if not USE_MOCKUP:
                switch.address = SWITCH_ADDRESS
            switch.connect()
            switch.open_all()
            self.log_message("Switch connected")
            return True
        except Exception as exc:
            switch = None
            self.log_message(f"ERROR: Failed to connect switch: {exc}")
            return False

    def _disconnect_switch(self):
        global switch
        try:
            if switch is not None:
                try:
                    switch.open_all()
                except Exception:
                    pass
                try:
                    switch.disconnect()
                except Exception:
                    pass
        finally:
            switch = None
            self.log_message("Switch disconnected")

    def _require_instrument(self, instrument_key, action_label):
        if not self.instrument_connected.get(instrument_key, False):
            self.log_message(f"ERROR: {action_label} requires {instrument_key} connection")
            return False
        return True

    def _dyna_call(self, method_name, *args, **kwargs):
        if dyna is None:
            raise RuntimeError("Dyna not connected")
        with self._dyna_comm_lock:
            method = getattr(dyna, method_name)
            return method(*args, **kwargs)

    # ------------------------------
    # Auto-logging system for long-term operation
    # ------------------------------
    def _toggle_auto_logging(self):
        """Enable or disable auto-logging"""
        if self.auto_log_enabled.get():
            self._initialize_auto_log()
            self.log_dyna_message("Auto-logging enabled")
        else:
            self._close_auto_log()
            self.log_dyna_message("Auto-logging disabled")

    def _change_log_directory(self):
        """Allow user to change log directory"""
        from tkinter import filedialog
        new_dir = filedialog.askdirectory(title="Select Log Directory", initialdir=self.log_dir)
        if new_dir:
            self.log_dir = Path(new_dir)
            if not self.log_dir.exists():
                self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir_display.config(text=f"Dir: {self.log_dir}")
            self.log_dyna_message(f"Log directory changed to: {self.log_dir}")
            
            # Reinitialize log if enabled
            if self.auto_log_enabled.get():
                self._close_auto_log()
                self._initialize_auto_log()

    def _initialize_auto_log(self):
        """Create a new auto-log file or reuse existing one from today"""
        try:
            with self.auto_log_lock:
                # Close existing log if open
                if self.auto_log_file is not None:
                    self.auto_log_file.close()
                
                # Generate filename with shortened date (YYMMDD)
                date_str = datetime.now().strftime("%y%m%d")
                base_filename = f"{date_str}_external_PPMS_log.csv"
                potential_log = self.log_dir / base_filename
                
                # Check if log from today exists and is not full
                if potential_log.exists():
                    file_size = potential_log.stat().st_size
                    if file_size < self.auto_log_max_size:
                        # Reuse existing log
                        self.auto_log_filename = potential_log
                        self.auto_log_file = open(self.auto_log_filename, 'a', newline='')
                        self.auto_log_writer = csv.writer(self.auto_log_file)
                        
                        self.log_file_display.config(text=f"Log: {self.auto_log_filename.name}")
                        self.log_dyna_message(f"Auto-log resumed: {self.auto_log_filename.name} ({file_size / 1024 / 1024:.1f} MB)")
                        return
                
                # Create new log file (existing one is full or doesn't exist)
                self.auto_log_filename = potential_log
                self.auto_log_file = open(self.auto_log_filename, 'w', newline='')
                self.auto_log_writer = csv.writer(self.auto_log_file)
                
                # Write header
                self.auto_log_writer.writerow([
                    "Timestamp", "Elapsed_Time(s)", 
                    "Temperature(K)", "PPMS_Field(Oe)", 
                    "Helmholtz_Current_A(A)", "Helmholtz_Current_B(A)",
                    "Helmholtz_Resistance_A(Ohm)", "Helmholtz_Resistance_B(Ohm)",
                    "Helmholtz_Field(G)"
                ])
                self.auto_log_file.flush()
                
                # Update UI
                self.log_file_display.config(text=f"Log: {self.auto_log_filename.name}")
                self.log_dyna_message(f"Auto-log started: {self.auto_log_filename.name}")
                
        except Exception as e:
            self.log_dyna_message(f"ERROR: Failed to initialize auto-log: {e}")
            self.auto_log_enabled.set(False)

    def _write_auto_log(self):
        """Write current data to auto-log file"""
        if not self.auto_log_enabled.get() or self.auto_log_file is None:
            return
        
        try:
            with self.auto_log_lock:
                # Get current data
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elapsed = round(time.time() - self.start_time_dyna, 2)
                
                # Get Dyna data (from snapshot)
                dyna_snapshot = self._get_dyna_snapshot()
                temp_val = dyna_snapshot.get("temp_val", "")
                field_val = dyna_snapshot.get("field_val", "")
                
                # Get Helmholtz data
                if self.instrument_connected.get("helmholtz", False) and self.device.enabled:
                    current_a = self.device.actual_current_a
                    current_b = self.device.actual_current_b
                    res_a = self.device.measure_resistance(ch='a')
                    res_b = self.device.measure_resistance(ch='b')
                    field_g = self.current_helmholtz_field
                else:
                    current_a = current_b = res_a = res_b = field_g = ""
                
                # Write row
                self.auto_log_writer.writerow([
                    timestamp, elapsed,
                    temp_val if temp_val is not None else "",
                    field_val if field_val is not None else "",
                    current_a, current_b,
                    res_a if res_a is not None else "",
                    res_b if res_b is not None else "",
                    field_g
                ])
                self.auto_log_file.flush()
                
                # Check if rotation needed
                self._check_log_rotation()
                
        except Exception as e:
            self.log_dyna_message(f"ERROR: Failed to write auto-log: {e}")

    def _check_log_rotation(self):
        """Check if log file size exceeds limit and rotate if needed"""
        try:
            if self.auto_log_filename and self.auto_log_filename.exists():
                file_size = self.auto_log_filename.stat().st_size
                
                if file_size >= self.auto_log_max_size:
                    # Get the old filename for the message
                    old_filename = self.auto_log_filename.name
                    
                    # Close and rotate
                    self._close_auto_log()
                    self._initialize_auto_log()
                    
                    # Reset graphs to use new log
                    self.reset_plot()
                    self.reset_helmholtz_plot()
                    
                    # Show popup notification
                    new_filename = self.auto_log_filename.name
                    messagebox.showinfo(
                        "Auto-Log Rotated",
                        f"Log file size limit reached.\n\n"
                        f"Old log: {old_filename}\n"
                        f"New log: {new_filename}\n\n"
                        f"Graphs have been reset to use the new log file."
                    )
                    self.log_dyna_message(f"Log rotated: {new_filename}")
                    
        except Exception as e:
            self.log_dyna_message(f"ERROR: Failed to check log rotation: {e}")

    def _close_auto_log(self):
        """Close the auto-log file"""
        try:
            with self.auto_log_lock:
                if self.auto_log_file is not None:
                    self.auto_log_file.close()
                    self.auto_log_file = None
                    self.auto_log_writer = None
                self.log_file_display.config(text="Log: Closed")
        except Exception as e:
            self.log_dyna_message(f"ERROR: Failed to close auto-log: {e}")

    def log_message(self, message):
        """Thread-safe logging that schedules GUI updates on the main thread"""
        # Use 50ms delay instead of 0 to batch updates and prevent event queue backup
        try:
            if self.root.winfo_exists():
                callback_id = self.root.after(50, self._update_message_box, message)
                # Limit pending callbacks to prevent unbounded growth
                if len(self._pending_callbacks) < 1000:
                    self._pending_callbacks.append(callback_id)
        except:
            pass  # Root may have been destroyed
    
    def _update_message_box(self, message):
        """Internal method to update message box - runs on main thread"""
        try:
            if not self.root.winfo_exists():
                return
            
            self.message_box.config(state="normal")
            
            # Check line count BEFORE inserting (prevents temporary overflow)
            line_count = int(self.message_box.index('end-1c').split('.')[0])
            if line_count >= self._message_box_max_lines:
                # Delete oldest lines to make room
                excess = line_count - self._message_box_max_lines + 5
                self.message_box.delete("1.0", f"{excess}.0")
            
            self.message_box.insert("end", message + "\n")
            self.message_box.see("end")
            self.message_box.config(state="disabled")
        except:
            pass  # Widget may have been destroyed

    def _schedule_results_plot_update(self):
        """Schedule/throttle Results plot updates on main thread."""
        try:
            if not self.root.winfo_exists():
                return

            now = time.time()
            elapsed = now - self._last_results_plot_update

            if self._results_plot_update_pending:
                return

            if elapsed >= self._results_plot_min_interval:
                delay_ms = 0
            else:
                delay_ms = int((self._results_plot_min_interval - elapsed) * 1000)

            self._results_plot_update_pending = True
            callback_id = self.root.after(delay_ms, self._run_scheduled_results_plot_update)
            if len(self._pending_callbacks) < 1000:
                self._pending_callbacks.append(callback_id)
        except:
            pass

    def _run_scheduled_results_plot_update(self):
        """Execute a scheduled Results plot update on main thread."""
        self._results_plot_update_pending = False
        self._last_results_plot_update = time.time()
        self.update_plots()

    def log_dyna_message(self, message):
        """Thread-safe logging for PPMS messages"""
        try:
            if self.root.winfo_exists():
                callback_id = self.root.after(50, self._update_dyna_message_box, message)
                # Limit pending callbacks to prevent unbounded growth
                if len(self._pending_callbacks) < 1000:
                    self._pending_callbacks.append(callback_id)
        except:
            pass  # Root may have been destroyed
    
    def _update_dyna_message_box(self, message):
        """Internal method to update PPMS message box - runs on main thread"""
        try:
            if not self.root.winfo_exists():
                return
            
            self.dyna_message_box.config(state="normal")
            
            # Check line count BEFORE inserting (prevents temporary overflow)
            line_count = int(self.dyna_message_box.index('end-1c').split('.')[0])
            if line_count >= self._dyna_message_box_max_lines:
                # Delete oldest lines to make room
                excess = line_count - self._dyna_message_box_max_lines + 5
                self.dyna_message_box.delete("1.0", f"{excess}.0")
            
            self.dyna_message_box.insert("end", message + "\n")
            self.dyna_message_box.see("end")
            self.dyna_message_box.config(state="disabled")
        except:
            pass  # Widget may have been destroyed

    def highlight_script_line(self, line_number):
        """Thread-safe highlighting of current executing line in the script editor"""
        try:
            if self.root.winfo_exists():
                callback_id = self.root.after(50, self._update_script_highlight, line_number)
                if len(self._pending_callbacks) < 1000:
                    self._pending_callbacks.append(callback_id)
        except:
            pass  # Root may have been destroyed
    
    def _update_script_highlight(self, line_number):
        """Internal method to update script highlight - runs on main thread"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Remove previous highlight
            self.script_text.tag_remove("current_line", "1.0", tk.END)
            
            if line_number > 0:
                # Highlight the current line (line_number is 1-indexed)
                line_start = f"{line_number}.0"
                line_end = f"{line_number}.end"
                self.script_text.tag_add("current_line", line_start, line_end)
                
                # Scroll to show the current line
                self.script_text.see(line_start)
        except:
            pass  # Widget may have been destroyed

    def validate_script(self, script_content):
        """
        Validate script before execution to catch errors early.
        
        Returns
        -------
        tuple (bool, list of str)
            (is_valid, list of error messages with line numbers)
        """
        errors = []
        lines = script_content.split('\n')
        
        # Valid command list
        valid_commands = [
            'test', 'initialize_data_file', 'set_helmholtz_field', 'scan_helmholtz_field', 'sweep_helmholtz_field',
            'set_dyna_temp', 'scan_dyna_temp', 'sweep_dyna_temp', 'wait_for', 'set_dyna_field', 'scan_dyna_field', 'sweep_dyna_field',
            'measure_hall_field', 'measure_lockin', 'continuous_measure_lockin', 'full_measure', 'close_channel', 'open_all_channels',
            'run_saved_script', 'set_ppms_field_and_fix_hall', 'scan_ppms_field_and_fix_hall',
            'set_lockin_time_constant', 'set_lockin_filter', 'set_lockin_frequency', 'set_lockin_current',
            'add_note', 'auto_gain', 'auto_phase', 'auto_reserve', 'configure_channel'
        ]
        
        # Valid choices for various parameters
        valid_temp_approaches = ['fast_settle', 'no_overshoot']
        valid_field_approaches = ['linear', 'no_overshoot', 'oscillate']
        valid_wait_events = ['temp', 'field', 'helmholtz', 'no_event', 'all']
        valid_channels = ['a', 'b']
        valid_voltage_ranges = ['auto', '10mV', '100mV', '1V', '10V']
        valid_lockin_params = ['X', 'Y', 'R', 'Theta']
        valid_filter_slopes = [6, 12, 18, 24]
        
        # Hardware limits - CONFIRMED VALUES
        # PPMS
        MAX_PPMS_FIELD = 140000  # Oe (±140,000 Oe)
        MAX_PPMS_TEMP = 400  # K
        MIN_PPMS_TEMP = 1.6  # K
        MIN_PPMS_TEMP_RATE = 0.01  # K/min
        MAX_PPMS_TEMP_RATE = 50.0  # K/min
        MIN_PPMS_FIELD_RATE = 0.01  # Oe/s
        MAX_PPMS_FIELD_RATE = 50.0  # Oe/s
        
        # Keithley 2600 (Model 2651A) - Helmholtz control
        MAX_HELMHOLTZ_CURRENT_PER_CHANNEL = 1.5  # A per channel
        MAX_HELMHOLTZ_CURRENT_TOTAL = 3.0  # A (both channels combined)
        MAX_K2600_COMPLIANCE_V = 20.0  # V
        MIN_HELMHOLTZ_CURRENT_RATE = 0.01  # mA/s (0.00001 A/s)
        MAX_HELMHOLTZ_CURRENT_RATE = 100.0  # mA/s (0.1 A/s)
        
        # Keithley 2450 - Hall bar measurements
        MAX_HALL_CURRENT = 10.0  # mA (0-10 mA range)
        MIN_HALL_COMPLIANCE_V = 0.001  # V (1 mV minimum)
        MAX_HALL_COMPLIANCE_V = 10.0  # V (10 V maximum)
        MIN_NPLC = 0.01
        MAX_NPLC = 10.0
        
        # Helmholtz coil calibration: 683.42 G/A
        HELMHOLTZ_CALIBRATION = 683.42  # G/A

        # SR830 output amplitude limit
        MAX_LOCKIN_SLVL = 5.0  # V rms
        
        # TAU_TABLE for valid time constants (in seconds)
        VALID_TAU_SECONDS = [
            0.00001, 0.00003, 0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03,
            0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0
        ]

        def require_connected(instrument_key, line_num, cmd_label):
            if not self.instrument_connected.get(instrument_key, False):
                errors.append(f"Line {line_num}: {cmd_label} requires {instrument_key} to be connected")
                return False
            return True
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Get command (first word)
            parts = line.split()
            if not parts:
                continue
                
            cmd = parts[0]
            
            # Check if command is valid
            if cmd not in valid_commands:
                errors.append(f"Line {line_num}: Unknown command '{cmd}'")
                continue
            
            # Check for multiple commands on the same line
            # After the first command, check if remaining text contains another command keyword
            remaining_text = ' '.join(parts[1:])
            for other_cmd in valid_commands:
                # Look for command keywords that appear as standalone words in the remaining text
                # Use word boundaries to avoid false positives (e.g., "phase" in "use_autophase")
                if ' ' + other_cmd + ' ' in ' ' + remaining_text + ' ':
                    errors.append(f"Line {line_num}: Multiple commands detected on same line ('{cmd}' and '{other_cmd}'). Each command must be on its own line.")
                    break
            
            # Command-specific validation
            try:
                # Helmholtz field commands - CHECK CURRENT LIMITS AND RATES
                if cmd == 'set_helmholtz_field':
                    if not require_connected("helmholtz", line_num, "set_helmholtz_field"):
                        continue
                    if len(parts) < 3:
                        errors.append(f"Line {line_num}: set_helmholtz_field requires <field_Oe> <rate_Oe/s>")
                    else:
                        field_Oe = float(parts[1])
                        rate_Oe_s = float(parts[2])
                        
                        # Convert to current: Field(Oe) ~= Field(G) for practical purposes
                        helmholtz_field_G = field_Oe
                        helmholtz_current_A = helmholtz_field_G / HELMHOLTZ_CALIBRATION
                        
                        # Convert rate: Oe/s -> G/s -> A/s -> mA/s
                        rate_G_s = rate_Oe_s
                        rate_A_s = rate_G_s / HELMHOLTZ_CALIBRATION
                        rate_mA_s = rate_A_s * 1000
                        
                        if abs(helmholtz_current_A) > MAX_HELMHOLTZ_CURRENT_TOTAL:
                            errors.append(f"Line {line_num}: Helmholtz field {field_Oe}Oe requires {abs(helmholtz_current_A):.2f}A (max {MAX_HELMHOLTZ_CURRENT_TOTAL}A)")
                        
                        if rate_mA_s < MIN_HELMHOLTZ_CURRENT_RATE or rate_mA_s > MAX_HELMHOLTZ_CURRENT_RATE:
                            errors.append(f"Line {line_num}: Helmholtz rate {rate_Oe_s}Oe/s = {rate_mA_s:.2f}mA/s out of range ({MIN_HELMHOLTZ_CURRENT_RATE}-{MAX_HELMHOLTZ_CURRENT_RATE}mA/s)")
                
                elif cmd == 'scan_helmholtz_field':
                    if not require_connected("helmholtz", line_num, "scan_helmholtz_field"):
                        continue
                    if len(parts) < 5:
                        errors.append(f"Line {line_num}: scan_helmholtz_field requires <start> <end> <step> <rate> <approach>")
                    else:
                        start_Oe, end_Oe = float(parts[1]), float(parts[2])
                        rate_Oe_s = float(parts[4])
                        
                        # Check field limits
                        for field_Oe in [start_Oe, end_Oe]:
                            helmholtz_field_G = field_Oe
                            helmholtz_current_A = helmholtz_field_G / HELMHOLTZ_CALIBRATION
                            if abs(helmholtz_current_A) > MAX_HELMHOLTZ_CURRENT_TOTAL:
                                errors.append(f"Line {line_num}: Helmholtz scan reaches {field_Oe}Oe = {abs(helmholtz_current_A):.2f}A (max {MAX_HELMHOLTZ_CURRENT_TOTAL}A)")
                                break
                        
                        # Check rate limits
                        rate_G_s = rate_Oe_s
                        rate_A_s = rate_G_s / HELMHOLTZ_CALIBRATION
                        rate_mA_s = rate_A_s * 1000
                        
                        if rate_mA_s < MIN_HELMHOLTZ_CURRENT_RATE or rate_mA_s > MAX_HELMHOLTZ_CURRENT_RATE:
                            errors.append(f"Line {line_num}: Helmholtz rate {rate_Oe_s}Oe/s = {rate_mA_s:.2f}mA/s out of range ({MIN_HELMHOLTZ_CURRENT_RATE}-{MAX_HELMHOLTZ_CURRENT_RATE}mA/s)")
                
                # Temperature commands - CHECK TEMP RANGE AND RATES
                elif cmd == 'set_dyna_temp':
                    if not require_connected("dyna", line_num, "set_dyna_temp"):
                        continue
                    if len(parts) < 4:
                        errors.append(f"Line {line_num}: set_dyna_temp requires <temp_K> <rate> <approach>")
                    else:
                        temp_K = float(parts[1])
                        rate_K_min = float(parts[2])
                        approach = parts[3]
                        
                        if temp_K < MIN_PPMS_TEMP or temp_K > MAX_PPMS_TEMP:
                            errors.append(f"Line {line_num}: Temperature {temp_K}K out of range ({MIN_PPMS_TEMP}-{MAX_PPMS_TEMP}K)")
                        
                        if rate_K_min < MIN_PPMS_TEMP_RATE or rate_K_min > MAX_PPMS_TEMP_RATE:
                            errors.append(f"Line {line_num}: Temperature rate {rate_K_min}K/min out of range ({MIN_PPMS_TEMP_RATE}-{MAX_PPMS_TEMP_RATE}K/min)")
                        
                        if approach not in valid_temp_approaches:
                            errors.append(f"Line {line_num}: Invalid approach '{approach}'. Valid: {valid_temp_approaches}")
                
                elif cmd == 'scan_dyna_temp':
                    if not require_connected("dyna", line_num, "scan_dyna_temp"):
                        continue
                    if len(parts) < 6:
                        errors.append(f"Line {line_num}: scan_dyna_temp requires <start> <end> <step> <rate> <approach>")
                    else:
                        start_K, end_K = float(parts[1]), float(parts[2])
                        rate_K_min = float(parts[4])
                        approach = parts[5]
                        
                        for temp_K in [start_K, end_K]:
                            if temp_K < MIN_PPMS_TEMP or temp_K > MAX_PPMS_TEMP:
                                errors.append(f"Line {line_num}: Temperature scan includes {temp_K}K (range: {MIN_PPMS_TEMP}-{MAX_PPMS_TEMP}K)")
                                break
                        
                        if rate_K_min < MIN_PPMS_TEMP_RATE or rate_K_min > MAX_PPMS_TEMP_RATE:
                            errors.append(f"Line {line_num}: Temperature rate {rate_K_min}K/min out of range ({MIN_PPMS_TEMP_RATE}-{MAX_PPMS_TEMP_RATE}K/min)")
                        
                        if approach not in valid_temp_approaches:
                            errors.append(f"Line {line_num}: Invalid approach '{approach}'. Valid: {valid_temp_approaches}")
                
                # PPMS Field commands - CHECK FIELD LIMITS AND RATES
                elif cmd == 'set_dyna_field':
                    if not require_connected("dyna", line_num, "set_dyna_field"):
                        continue
                    if len(parts) < 4:
                        errors.append(f"Line {line_num}: set_dyna_field requires <field_Oe> <rate> <approach>")
                    else:
                        field_Oe = float(parts[1])
                        rate_Oe_s = float(parts[2])
                        approach = parts[3]
                        
                        if abs(field_Oe) > MAX_PPMS_FIELD:
                            errors.append(f"Line {line_num}: PPMS field {field_Oe}Oe exceeds max ±{MAX_PPMS_FIELD}Oe")
                        
                        if rate_Oe_s < MIN_PPMS_FIELD_RATE or rate_Oe_s > MAX_PPMS_FIELD_RATE:
                            errors.append(f"Line {line_num}: PPMS field rate {rate_Oe_s}Oe/s out of range ({MIN_PPMS_FIELD_RATE}-{MAX_PPMS_FIELD_RATE}Oe/s)")
                        
                        if approach not in valid_field_approaches:
                            errors.append(f"Line {line_num}: Invalid approach '{approach}'. Valid: {valid_field_approaches}")
                
                elif cmd == 'scan_dyna_field':
                    if not require_connected("dyna", line_num, "scan_dyna_field"):
                        continue
                    if len(parts) < 6:
                        errors.append(f"Line {line_num}: scan_dyna_field requires <start> <end> <step> <rate> <approach>")
                    else:
                        start_Oe, end_Oe = float(parts[1]), float(parts[2])
                        rate_Oe_s = float(parts[4])
                        approach = parts[5]
                        
                        for field_Oe in [start_Oe, end_Oe]:
                            if abs(field_Oe) > MAX_PPMS_FIELD:
                                errors.append(f"Line {line_num}: PPMS field scan includes {field_Oe}Oe (max ±{MAX_PPMS_FIELD}Oe)")
                                break
                        
                        if rate_Oe_s < MIN_PPMS_FIELD_RATE or rate_Oe_s > MAX_PPMS_FIELD_RATE:
                            errors.append(f"Line {line_num}: PPMS field rate {rate_Oe_s}Oe/s out of range ({MIN_PPMS_FIELD_RATE}-{MAX_PPMS_FIELD_RATE}Oe/s)")
                        
                        if approach not in valid_field_approaches:
                            errors.append(f"Line {line_num}: Invalid approach '{approach}'. Valid: {valid_field_approaches}")
                
                # Wait command - CHECK VALID EVENTS
                elif cmd == 'wait_for':
                    if len(parts) < 3:
                        errors.append(f"Line {line_num}: wait_for requires <events...> <additional_time_s>")
                    else:
                        try:
                            additional_time = float(parts[-1])
                            events = parts[1:-1]
                            if not events:
                                errors.append(f"Line {line_num}: wait_for requires at least one event before duration")
                            else:
                                # Check each event (after expanding 'all')
                                events_to_check = ['temp', 'field', 'helmholtz'] if 'all' in events else events
                                for event in events_to_check:
                                    if event not in valid_wait_events:
                                        errors.append(f"Line {line_num}: Invalid event '{event}'. Valid: {valid_wait_events}")
                                if any(event in ['temp', 'field'] for event in events_to_check):
                                    require_connected("dyna", line_num, "wait_for")
                                if 'helmholtz' in events_to_check:
                                    require_connected("helmholtz", line_num, "wait_for")
                        except ValueError:
                            errors.append(f"Line {line_num}: wait_for duration must be a number")
                
                # Lock-in time constant - CHECK TAU_TABLE
                elif cmd == 'set_lockin_time_constant':
                    if not require_connected("lockin", line_num, "set_lockin_time_constant"):
                        continue
                    if len(parts) < 2:
                        errors.append(f"Line {line_num}: set_lockin_time_constant requires <seconds>")
                    else:
                        tau_seconds = float(parts[1])
                        closest_tau = min(VALID_TAU_SECONDS, key=lambda x: abs(x - tau_seconds))
                        diff_percent = abs(closest_tau - tau_seconds) / tau_seconds if tau_seconds != 0 else 1
                        if diff_percent > 0.1:  # >10% difference
                            errors.append(f"Line {line_num}: Time constant {tau_seconds}s not in TAU_TABLE (closest: {closest_tau}s)")
                
                # Lock-in filter slope - CHECK VALID SLOPES
                elif cmd == 'set_lockin_filter':
                    if not require_connected("lockin", line_num, "set_lockin_filter"):
                        continue
                    if len(parts) < 2:
                        errors.append(f"Line {line_num}: set_lockin_filter requires <db_octave>")
                    else:
                        db_oct = float(parts[1])
                        if db_oct not in valid_filter_slopes:
                            errors.append(f"Line {line_num}: Filter slope {db_oct} dB/oct invalid. Valid: {valid_filter_slopes}")
                
                # Channel commands - CHECK VALID CHANNELS
                elif cmd == 'close_channel':
                    if not require_connected("switch", line_num, "close_channel"):
                        continue
                    if len(parts) < 2:
                        errors.append(f"Line {line_num}: close_channel requires <channel>")
                    else:
                        channel = parts[1]
                        if channel not in valid_channels:
                            errors.append(f"Line {line_num}: Invalid channel '{channel}'. Valid: {valid_channels}")
                
                # Configure channel command - CHECK VALID CHANNELS AND ROUTING NUMBERS
                elif cmd == 'configure_channel':
                    if not require_connected("switch", line_num, "configure_channel"):
                        continue
                    if len(parts) < 6:
                        errors.append(f"Line {line_num}: configure_channel requires <channel> <I+> <V+> <V-> <I->")
                    else:
                        channel = parts[1]
                        if channel not in valid_channels:
                            errors.append(f"Line {line_num}: Invalid channel '{channel}'. Valid: {valid_channels}")
                        else:
                            try:
                                ip, vp, vm, im = map(int, parts[2:6])
                                routing_nums = [ip, vp, vm, im]
                                
                                # Check range 1-8
                                for num in routing_nums:
                                    if num < 1 or num > 8:
                                        errors.append(f"Line {line_num}: Routing number {num} out of range (1-8)")
                                        break
                                
                                # Check for duplicates within channel
                                if len(routing_nums) != len(set(routing_nums)):
                                    errors.append(f"Line {line_num}: Duplicate routing numbers in configure_channel: {routing_nums}")
                            except ValueError:
                                errors.append(f"Line {line_num}: Routing numbers must be integers 1-8")
                
                # Full measure command
                elif cmd == 'full_measure':
                    require_connected("hall", line_num, "full_measure")
                    require_connected("lockin", line_num, "full_measure")
                    require_connected("switch", line_num, "full_measure")
                    if len(parts) < 2:
                        errors.append(f"Line {line_num}: full_measure requires <channel>")
                    else:
                        channel = parts[1]
                        if channel not in valid_channels:
                            errors.append(f"Line {line_num}: Invalid channel '{channel}'. Valid: {valid_channels}")
                        
                        # Check optional parameters
                        for part in parts[2:]:
                            if '=' in part:
                                key, value = part.split('=', 1)
                                
                                # Hall parameters validation
                                if key == 'hall_current':
                                    curr_mA = float(value)
                                    if curr_mA < 0 or curr_mA > MAX_HALL_CURRENT:
                                        errors.append(f"Line {line_num}: hall_current {curr_mA}mA out of range (0-{MAX_HALL_CURRENT}mA)")
                                
                                elif key == 'hall_compliance':
                                    comp_V = float(value)
                                    if comp_V < MIN_HALL_COMPLIANCE_V or comp_V > MAX_HALL_COMPLIANCE_V:
                                        errors.append(f"Line {line_num}: hall_compliance {comp_V}V out of range ({MIN_HALL_COMPLIANCE_V}-{MAX_HALL_COMPLIANCE_V}V)")
                                
                                elif key == 'hall_nplc':
                                    nplc = float(value)
                                    if nplc < MIN_NPLC or nplc > MAX_NPLC:
                                        errors.append(f"Line {line_num}: hall_nplc {nplc} out of range ({MIN_NPLC}-{MAX_NPLC})")
                                
                                elif key == 'hall_voltage_range':
                                    if value not in valid_voltage_ranges:
                                        errors.append(f"Line {line_num}: Invalid voltage range '{value}'. Valid: {valid_voltage_ranges}")
                                
                                elif key == 'lockin_what':
                                    lockin_params = value.split(',')
                                    for param in lockin_params:
                                        if param not in valid_lockin_params:
                                            errors.append(f"Line {line_num}: Invalid lockin parameter '{param}'. Valid: {valid_lockin_params}")
                
                # Measure hall field - CHECK PARAMETERS
                elif cmd == 'measure_hall_field':
                    if not require_connected("hall", line_num, "measure_hall_field"):
                        continue
                    for part in parts[1:]:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            
                            if key == 'current':
                                curr_mA = float(value)
                                if curr_mA < 0 or curr_mA > MAX_HALL_CURRENT:
                                    errors.append(f"Line {line_num}: current {curr_mA}mA out of range (0-{MAX_HALL_CURRENT}mA)")
                            
                            elif key == 'compliance_v':
                                comp_V = float(value)
                                if comp_V < MIN_HALL_COMPLIANCE_V or comp_V > MAX_HALL_COMPLIANCE_V:
                                    errors.append(f"Line {line_num}: compliance_v {comp_V}V out of range ({MIN_HALL_COMPLIANCE_V}-{MAX_HALL_COMPLIANCE_V}V)")
                            
                            elif key == 'nplc':
                                nplc = float(value)
                                if nplc < MIN_NPLC or nplc > MAX_NPLC:
                                    errors.append(f"Line {line_num}: nplc {nplc} out of range ({MIN_NPLC}-{MAX_NPLC})")
                            
                            elif key == 'voltage_range':
                                if value not in valid_voltage_ranges:
                                    errors.append(f"Line {line_num}: Invalid voltage range '{value}'. Valid: {valid_voltage_ranges}")
                
                # Measure lockin - CHECK WHAT PARAMETER
                elif cmd == 'measure_lockin':
                    if not require_connected("lockin", line_num, "measure_lockin"):
                        continue
                    for part in parts[1:]:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            if key == 'what':
                                lockin_params = value.split(',')
                                for param in lockin_params:
                                    if param not in valid_lockin_params:
                                        errors.append(f"Line {line_num}: Invalid lockin parameter '{param}'. Valid: {valid_lockin_params}")

                elif cmd == 'continuous_measure_lockin':
                    if not require_connected("lockin", line_num, "continuous_measure_lockin"):
                        continue
                    for part in parts[1:]:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            if key == 'what':
                                lockin_params = value.split(',')
                                for param in lockin_params:
                                    if param not in valid_lockin_params:
                                        errors.append(f"Line {line_num}: Invalid lockin parameter '{param}'. Valid: {valid_lockin_params}")
                            elif key == 'avg':
                                if int(value) < 1:
                                    errors.append(f"Line {line_num}: avg must be >= 1")
                            elif key == 'sample_delay':
                                if float(value) < 0:
                                    errors.append(f"Line {line_num}: sample_delay must be >= 0")
                            elif key == 'excitation':
                                if value.lower() not in ['on', 'off', 'keep']:
                                    errors.append(f"Line {line_num}: excitation must be on, off, or keep")

                elif cmd == 'set_lockin_current':
                    if not require_connected("lockin", line_num, "set_lockin_current"):
                        continue
                    if len(parts) < 2:
                        errors.append(f"Line {line_num}: set_lockin_current requires <current_A> [series_resistance=R]")
                    else:
                        current_a = float(parts[1])
                        if current_a < 0:
                            errors.append(f"Line {line_num}: current {current_a}A must be >= 0")
                        series_resistance = None
                        for part in parts[2:]:
                            if '=' in part:
                                key, value = part.split('=', 1)
                                if key == 'series_resistance':
                                    series_resistance = float(value)
                        if series_resistance is not None:
                            if series_resistance <= 0:
                                errors.append(f"Line {line_num}: series_resistance must be > 0")
                            elif current_a * series_resistance > MAX_LOCKIN_SLVL:
                                errors.append(
                                    f"Line {line_num}: current {current_a}A with series_resistance {series_resistance}Ohm exceeds {MAX_LOCKIN_SLVL}V"
                                )
                
                # PPMS field correction commands
                elif cmd == 'set_ppms_field_and_fix_hall':
                    require_connected("dyna", line_num, "set_ppms_field_and_fix_hall")
                    require_connected("helmholtz", line_num, "set_ppms_field_and_fix_hall")
                    require_connected("hall", line_num, "set_ppms_field_and_fix_hall")
                    if len(parts) < 3:
                        errors.append(f"Line {line_num}: set_ppms_field_and_fix_hall requires <field_Oe> <target_hall_G>")
                    else:
                        field_Oe = float(parts[1])
                        if abs(field_Oe) > MAX_PPMS_FIELD:
                            errors.append(f"Line {line_num}: PPMS field {field_Oe}Oe exceeds max ±{MAX_PPMS_FIELD}Oe")
                
                elif cmd == 'scan_ppms_field_and_fix_hall':
                    require_connected("dyna", line_num, "scan_ppms_field_and_fix_hall")
                    require_connected("helmholtz", line_num, "scan_ppms_field_and_fix_hall")
                    require_connected("hall", line_num, "scan_ppms_field_and_fix_hall")
                    if len(parts) < 5:
                        errors.append(f"Line {line_num}: scan_ppms_field_and_fix_hall requires <start> <end> <step> <target_hall_G>")
                    else:
                        start_Oe, end_Oe = float(parts[1]), float(parts[2])
                        for field_Oe in [start_Oe, end_Oe]:
                            if abs(field_Oe) > MAX_PPMS_FIELD:
                                errors.append(f"Line {line_num}: PPMS field scan includes {field_Oe}Oe (max ±{MAX_PPMS_FIELD}Oe)")
                                break
                
                elif cmd == 'sweep_dyna_field':
                    if not require_connected("dyna", line_num, "sweep_dyna_field"):
                        continue
                    if len(parts) < 4:
                        errors.append(f"Line {line_num}: sweep_dyna_field requires <start> <end> <rate> [gap_time=SECONDS]")
                    else:
                        start_Oe, end_Oe = float(parts[1]), float(parts[2])
                        rate_Oe_s = float(parts[3])
                        
                        for field_Oe in [start_Oe, end_Oe]:
                            if abs(field_Oe) > MAX_PPMS_FIELD:
                                errors.append(f"Line {line_num}: PPMS field sweep includes {field_Oe}Oe (max ±{MAX_PPMS_FIELD}Oe)")
                                break
                        
                        if rate_Oe_s < MIN_PPMS_FIELD_RATE or rate_Oe_s > MAX_PPMS_FIELD_RATE:
                            errors.append(f"Line {line_num}: PPMS field rate {rate_Oe_s}Oe/s out of range ({MIN_PPMS_FIELD_RATE}-{MAX_PPMS_FIELD_RATE}Oe/s)")
                
                elif cmd == 'sweep_dyna_temp':
                    if not require_connected("dyna", line_num, "sweep_dyna_temp"):
                        continue
                    if len(parts) < 4:
                        errors.append(f"Line {line_num}: sweep_dyna_temp requires <start> <end> <rate> [gap_time=SECONDS]")
                    else:
                        start_K, end_K = float(parts[1]), float(parts[2])
                        rate_K_min = float(parts[3])
                        
                        for temp_K in [start_K, end_K]:
                            if temp_K < MIN_PPMS_TEMP or temp_K > MAX_PPMS_TEMP:
                                errors.append(f"Line {line_num}: Temperature {temp_K}K out of range ({MIN_PPMS_TEMP}-{MAX_PPMS_TEMP}K)")
                                break
                        
                        if rate_K_min < MIN_PPMS_TEMP_RATE or rate_K_min > MAX_PPMS_TEMP_RATE:
                            errors.append(f"Line {line_num}: Temperature rate {rate_K_min}K/min out of range ({MIN_PPMS_TEMP_RATE}-{MAX_PPMS_TEMP_RATE}K/min)")
                
                elif cmd == 'sweep_helmholtz_field':
                    if not require_connected("helmholtz", line_num, "sweep_helmholtz_field"):
                        continue
                    if len(parts) < 4:
                        errors.append(f"Line {line_num}: sweep_helmholtz_field requires <start> <end> <rate> [gap_time=SECONDS]")
                    else:
                        start_Oe = float(parts[1])
                        end_Oe = float(parts[2])
                        rate_Oe_s = float(parts[3])
                        
                        # Convert to amperes for validation (683.42 G/A)
                        for field_Oe in [start_Oe, end_Oe]:
                            field_G = field_Oe  # 1 Oe ≈ 1 G for practical purposes
                            current_A = field_G / HELMHOLTZ_CALIBRATION
                            if abs(current_A) > MAX_HELMHOLTZ_CURRENT_TOTAL:
                                errors.append(f"Line {line_num}: Helmholtz field {field_Oe}Oe requires {abs(current_A):.2f}A (max ±{MAX_HELMHOLTZ_CURRENT_TOTAL}A)")
                                break
                
                elif cmd == 'open_all_channels':
                    require_connected("switch", line_num, "open_all_channels")

                elif cmd in ['auto_gain', 'auto_phase', 'auto_reserve']:
                    require_connected("lockin", line_num, cmd)

            except ValueError as e:
                errors.append(f"Line {line_num}: Parameter type error - {str(e)}")
            except IndexError as e:
                errors.append(f"Line {line_num}: Missing required parameters")
        
        is_valid = len(errors) == 0
        return is_valid, errors

    # ------------------------------
    # Script execution and validation
    # ------------------------------
    def _on_script_modified(self, event=None):
        if self.script_text.edit_modified():
            self.script_dirty = True
            self.script_text.edit_modified(False)

    def _ask_save_or_save_as(self, title, message):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        choice = {"value": "cancel"}

        def set_choice(value):
            choice["value"] = value
            dialog.destroy()

        ttk.Label(dialog, text=message, wraplength=360, justify="left").grid(
            row=0, column=0, columnspan=3, padx=12, pady=(12, 8), sticky="w"
        )

        ttk.Button(dialog, text="Save", command=lambda: set_choice("save")).grid(
            row=1, column=0, padx=8, pady=(0, 12), sticky="ew"
        )
        ttk.Button(dialog, text="Save As", command=lambda: set_choice("save_as")).grid(
            row=1, column=1, padx=8, pady=(0, 12), sticky="ew"
        )
        ttk.Button(dialog, text="Cancel", command=lambda: set_choice("cancel")).grid(
            row=1, column=2, padx=8, pady=(0, 12), sticky="ew"
        )

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        parent_x = self.root.winfo_rootx()
        parent_y = self.root.winfo_rooty()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()
        x = int(parent_x + (parent_width - width) / 2)
        y = int(parent_y + (parent_height - height) / 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.protocol("WM_DELETE_WINDOW", lambda: set_choice("cancel"))
        self.root.wait_window(dialog)
        return choice["value"]

    def _prompt_save_script_if_needed(self):
        script_content = self.script_text.get("1.0", tk.END).strip()
        if not script_content:
            return True

        if not self.script_has_saved_path:
            response = messagebox.askyesnocancel(
                "Save Script",
                "This script is new. Save As before running?"
            )
            if response is None:
                return False
            if response:
                self.save_script_as()
                if not self.script_has_saved_path:
                    return False
        elif self.script_dirty:
            response = self._ask_save_or_save_as(
                "Save Script",
                "This script has unsaved changes. Choose an action."
            )
            if response == "cancel":
                return False
            if response == "save":
                self.save_script()
                if self.script_dirty:
                    return False
            elif response == "save_as":
                self.save_script_as()
                if not self.script_has_saved_path:
                    return False

        return True

    def run_script(self):
        if self.script_running:
            return
        script_content = self.script_text.get("1.0", tk.END).strip()
        if not script_content:
            self.log_message("No script to run")
            return
        if not self._prompt_save_script_if_needed():
            self.log_message("Script run canceled")
            return
        
        # Validate script before execution
        is_valid, errors = self.validate_script(script_content)
        if not is_valid:
            self.log_message("=" * 60)
            self.log_message("SCRIPT VALIDATION FAILED - Script will not run")
            self.log_message("=" * 60)
            for error in errors:
                self.log_message(f"ERROR: {error}")
            self.log_message("=" * 60)
            self.log_message(f"Please fix {len(errors)} error(s) above and try again.")
            return

        # Set measurement start time when script runs
        if self.measurement_start_time is None:
            self.measurement_start_time = time.time()
            self.log_message(f"Measurement start time set: {time.strftime('%H:%M:%S')}")

        line_count = len(script_content.splitlines())
        self.log_message(f"Script validation passed - starting execution with {line_count} lines")
        self.script_running = True
        self.script_paused = False
        self.current_script_line = 0
        self.update_script_status()

        # Run script in a separate thread
        self.script_thread = threading.Thread(target=self.execute_script, args=(script_content,))
        self.script_thread.daemon = True
        self.script_thread.start()

    def pause_script(self):
        if self.script_running:
            self.script_paused = not self.script_paused
            self.update_script_status()

    def abort_script(self):
        if self.script_running:
            self.script_running = False
            self.script_paused = False
            self.update_script_status()
            self.highlight_script_line(0)  # Clear line highlight
            # Emergency stop - set currents to zero
            self.device.disable_output()
            if keithley2450 is not None:
                keithley2450.source_current = 0
                keithley2450.disable_source()
            self.led_off("hall")  # Turn off Hall LED on abort
            if lockin is not None:
                lockin.sine_output_off()
            self.log_message("Script aborted - all currents set to zero")

    def load_script(self):
        from tkinter import filedialog
        filename = filedialog.askopenfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filename:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                    self.script_text.delete("1.0", tk.END)
                    self.script_text.insert("1.0", content)
                    self.script_filename.set(filename)
                    self.script_dirty = False
                    self.script_has_saved_path = True
                    self.script_text.edit_modified(False)
                    self.log_message(f"Script loaded from {filename}")
            except Exception as e:
                self.log_message(f"Error loading script: {e}")

    def save_script(self):
        if not self.script_has_saved_path:
            self.save_script_as()
            return
        filename = self.script_filename.get()
        if not filename:
            self.save_script_as()
            return
        try:
            content = self.script_text.get("1.0", tk.END)
            with open(filename, 'w') as f:
                f.write(content)
            self.script_dirty = False
            self.script_text.edit_modified(False)
            self.log_message(f"Script saved to {filename}")
        except Exception as e:
            self.log_message(f"Error saving script: {e}")

    def save_script_as(self):
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filename:
            try:
                content = self.script_text.get("1.0", tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                self.script_filename.set(filename)
                self.script_dirty = False
                self.script_has_saved_path = True
                self.script_text.edit_modified(False)
                self.log_message(f"Script saved to {filename}")
            except Exception as e:
                self.log_message(f"Error saving script: {e}")

    def run_saved_script(self, filename):
        """Load and execute a saved script file"""
        try:
            with open(filename, 'r') as f:
                content = f.read()
            self.log_message(f"Loading script from {filename}")
            # Execute the loaded script directly without trying to call run_script()
            # (which would fail if already in a running script)
            is_valid, errors = self.validate_script(content)
            if not is_valid:
                self.log_message(f"Script validation failed for {filename}:")
                for error in errors:
                    self.log_message(f"  ERROR: {error}")
                return
            self.log_message(f"Executing loaded script from {filename}")
            self.execute_script(content)
        except Exception as e:
            self.log_message(f"Error loading/running script {filename}: {e}")

    def update_script_status(self):
        """Thread-safe status update"""
        self.root.after(50, self._update_status_display)
    
    def _update_status_display(self):
        """Internal method to update status display - runs on main thread"""
        if not self.script_running:
            self.script_status.set("Status: Idle")
        elif self.script_paused:
            self.script_status.set(f"Status: Paused (Line {self.current_script_line})")
        else:
            self.script_status.set(f"Status: Running (Line {self.current_script_line})")

        if self.pause_button is not None:
            self.pause_button.config(text="Unpause" if self.script_paused else "Pause")

    def execute_script(self, script_content):
        lines = script_content.split('\n')
        i = 0
        self.log_message(f"Starting script execution with {len(lines)} lines")

        while i < len(lines):
            if not self.script_running:
                break

            self.current_script_line = i + 1
            self.update_script_status()
            self.highlight_script_line(self.current_script_line)

            line = lines[i]
            stripped = line.strip()
            self.log_message(f"Processing line {self.current_script_line}: '{stripped}'")

            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # Wait for pause
            while self.script_paused and self.script_running:
                time.sleep(0.1)

            if not self.script_running:
                break

            try:
                indent = len(line) - len(stripped)
                if indent == 0:  # top level command
                    if stripped.lower().startswith('scan_dyna_field'):
                        parts = stripped.split()
                        if len(parts) >= 6:
                            start, end, step, rate = map(float, parts[1:5])
                            approach = parts[5]
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.scan_dyna_field(start, end, step, rate, approach, loop_commands)
                        else:
                            raise ValueError(f"Invalid scan_dyna_field command: {stripped}")
                    elif stripped.lower().startswith('scan_dyna_temp'):
                        parts = stripped.split()
                        if len(parts) >= 6:
                            start, end, step, rate = map(float, parts[1:5])
                            approach = parts[5]
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.scan_dyna_temp(start, end, step, rate, approach, loop_commands)
                        else:
                            raise ValueError(f"Invalid scan_dyna_temp command: {stripped}")
                    elif stripped.lower().startswith('scan_helmholtz_field'):
                        parts = stripped.split()
                        if len(parts) >= 6:
                            start, end, step, rate = map(float, parts[1:5])
                            approach = parts[5]
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.scan_helmholtz_field(start, end, step, rate, approach, loop_commands)
                        else:
                            raise ValueError(f"Invalid scan_helmholtz_field command: {stripped}")
                    elif stripped.lower().startswith('scan_ppms_field_and_fix_hall'):
                        parts = stripped.split()
                        if len(parts) >= 5:
                            start, end, step = map(float, parts[1:4])
                            target_hall = float(parts[4])
                            rate = 10.0
                            if len(parts) >= 6 and '=' in parts[5]:
                                key, value = parts[5].split('=')
                                if key == 'rate':
                                    rate = float(value)
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.scan_ppms_field_and_fix_hall(start, end, step, target_hall, rate, loop_commands)
                        else:
                            raise ValueError(f"Invalid scan_ppms_field_and_fix_hall command: {stripped}")
                    elif stripped.lower().startswith('sweep_dyna_field'):
                        parts = stripped.split()
                        gap_time = 0
                        if len(parts) >= 4:
                            start, end, rate = map(float, parts[1:4])
                            if len(parts) >= 5 and '=' in parts[4]:
                                key, value = parts[4].split('=')
                                if key == 'gap_time':
                                    gap_time = float(value)
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.sweep_dyna_field(start, end, rate, gap_time, loop_commands)
                        else:
                            raise ValueError(f"Invalid sweep_dyna_field command: {stripped}")
                    elif stripped.lower().startswith('sweep_dyna_temp'):
                        parts = stripped.split()
                        gap_time = 0
                        if len(parts) >= 4:
                            start, end, rate = map(float, parts[1:4])
                            if len(parts) >= 5 and '=' in parts[4]:
                                key, value = parts[4].split('=')
                                if key == 'gap_time':
                                    gap_time = float(value)
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.sweep_dyna_temp(start, end, rate, gap_time, loop_commands)
                        else:
                            raise ValueError(f"Invalid sweep_dyna_temp command: {stripped}")
                    elif stripped.lower().startswith('sweep_helmholtz_field'):
                        parts = stripped.split()
                        gap_time = 0
                        if len(parts) >= 4:
                            start, end, rate = map(float, parts[1:4])
                            if len(parts) >= 5 and '=' in parts[4]:
                                key, value = parts[4].split('=')
                                if key == 'gap_time':
                                    gap_time = float(value)
                            loop_commands = []
                            j = i + 1
                            while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                # Store both command and line number (1-indexed for display)
                                loop_commands.append((lines[j].strip(), j + 1))
                                j += 1
                            i = j - 1
                            self.sweep_helmholtz_field(start, end, rate, gap_time, loop_commands)
                        else:
                            raise ValueError(f"Invalid sweep_helmholtz_field command: {stripped}")
                    else:
                        self.execute_script_command(stripped)
                        self.log_message(f"Line {self.current_script_line} executed successfully")
                else:
                    # Indented line without scan: treat as top-level to allow leading whitespace
                    self.execute_script_command(stripped)
                    self.log_message(f"Line {self.current_script_line} executed successfully")

            except Exception as e:
                self.log_message(f"Script error on line {self.current_script_line}: {e}")
                self.script_running = False
                break

            i += 1
            # Allow GUI to process events
            time.sleep(0.01)

        self.script_running = False
        self.update_script_status()
        self.highlight_script_line(0)  # Clear line highlight
        self.log_message("Script execution completed")

    def execute_script_command(self, command):
        cmd = command.lower().strip()
        self.log_message(f"Executing: {command}")

        if cmd == 'test':
            self.log_message("Test command executed successfully")
            return

        elif cmd.startswith('initialize_data_file'):
            # initialize_data_file [directory=DIR] [filename=FILE] [append=BOOL]
            parts = command.split()
            directory = None
            filename = None
            append = False
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'directory':
                        directory = value
                    elif key == 'filename':
                        filename = value
                    elif key == 'append':
                        append = value.lower() in ('true', '1', 'yes')
            self.initialize_data_file(directory=directory, filename=filename, append=append)
            return

        elif cmd.startswith('set_dyna_field'):
            # set_dyna_field field rate approach
            if not self._require_instrument("dyna", "set_dyna_field"):
                return
            parts = command.split()
            if len(parts) >= 4:
                field, rate = map(float, parts[1:3])
                approach = parts[3]
                self.set_dyna_field(field, rate, approach)
            else:
                raise ValueError(f"Invalid set_dyna_field command: {command}")

        elif cmd.startswith('set_dyna_temp'):
            # set_dyna_temp temp rate approach
            if not self._require_instrument("dyna", "set_dyna_temp"):
                return
            parts = command.split()
            if len(parts) >= 4:
                temp, rate = map(float, parts[1:3])
                approach = parts[3]
                self.set_dyna_temp(temp, rate, approach)
            else:
                raise ValueError(f"Invalid set_dyna_temp command: {command}")

        elif cmd.startswith('set_helmholtz_field'):
            # set_helmholtz_field field rate
            if not self._require_instrument("helmholtz", "set_helmholtz_field"):
                return
            parts = command.split()
            if len(parts) >= 3:
                field, rate = map(float, parts[1:3])
                self.set_helmholtz_field(field, rate)
            else:
                raise ValueError(f"Invalid set_helmholtz_field command: {command}")

        elif cmd.startswith('wait_for'):
            # wait_for <events...> <additional_time>
            # Examples: wait_for temp 10, wait_for temp field 10, wait_for all 10
            parts = command.split()
            if len(parts) >= 3:
                try:
                    additional_time = float(parts[-1])  # Last part is duration
                    events = parts[1:-1]  # Everything between wait_for and duration
                    
                    if not events:
                        raise ValueError("No events specified")
                    
                    # Expand 'all' to all three event types
                    if 'all' in events:
                        events = ['temp', 'field', 'helmholtz']

                    if any(event in ['temp', 'field'] for event in events):
                        if not self._require_instrument("dyna", "wait_for"):
                            return
                    if 'helmholtz' in events:
                        if not self._require_instrument("helmholtz", "wait_for"):
                            return
                    
                    self.wait_for_events(events, additional_time)
                except (ValueError, IndexError) as e:
                    raise ValueError(f"Invalid wait_for command: {command} - {e}")
            else:
                raise ValueError(f"Invalid wait_for command: {command}")

        elif cmd.startswith('run_saved_script'):
            # run_saved_script filename
            parts = command.split()
            if len(parts) >= 2:
                filename = ' '.join(parts[1:])
                self.run_saved_script(filename)
            else:
                raise ValueError(f"Invalid run_saved_script command: {command}")

        elif cmd.startswith('measure_hall_field'):
            # measure_hall_field [current=mA] [nplc=N] [compliance_v=V] [voltage_range=V|auto] [filter_count=N] [tbm=S]
            if not self._require_instrument("hall", "measure_hall_field"):
                return
            parts = command.split()
            kwargs = {}
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'current':
                        kwargs['current'] = float(value)
                    elif key == 'nplc':
                        kwargs['nplc'] = int(value)
                    elif key == 'compliance_v':
                        kwargs['compliance_v'] = float(value)
                    elif key == 'voltage_range':
                        kwargs['voltage_range'] = value
                    elif key == 'filter_count':
                        kwargs['filter_count'] = int(value)
                    elif key == 'tbm':
                        kwargs['tbm'] = float(value)
            self.measure_k2450(**kwargs)

        elif cmd.startswith('measure_lockin'):
            # measure_lockin [what=X,Y,R,Theta] [current=A] [series_resistance=Ω] [avg=N] [start_sens=IDX] [use_autorange=true|false] [use_autophase=true|false] [sample_delay=0.05]
            if not self._require_instrument("lockin", "measure_lockin"):
                return
            parts = command.split()
            kwargs = {}
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'what':
                        # Parse comma-separated channels
                        kwargs['what'] = tuple(ch.strip() for ch in value.split(','))
                    elif key == 'current':
                        kwargs['current'] = float(value)
                    elif key == 'series_resistance':
                        kwargs['series_resistance'] = float(value)
                    elif key == 'avg':
                        kwargs['avg'] = int(value)
                    elif key == 'start_sens':
                        kwargs['start_sens'] = int(value)
                    elif key == 'use_autorange':
                        kwargs['use_autorange'] = value.lower() == 'true'
                    elif key == 'use_autophase':
                        kwargs['use_autophase'] = value.lower() == 'true'
                    elif key == 'sample_delay':
                        kwargs['sample_delay'] = float(value)
            self.lockin_measure(**kwargs)

        elif cmd.startswith('continuous_measure_lockin'):
            # continuous_measure_lockin [what=X,Y,R,Theta] [avg=N] [sample_delay=0.05] [excitation=on|off|keep]
            if not self._require_instrument("lockin", "continuous_measure_lockin"):
                return
            parts = command.split()
            kwargs = {}
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'what':
                        kwargs['what'] = tuple(ch.strip() for ch in value.split(','))
                    elif key == 'avg':
                        kwargs['avg'] = int(value)
                    elif key == 'sample_delay':
                        kwargs['sample_delay'] = float(value)
                    elif key == 'excitation':
                        kwargs['excitation'] = value
            self.lockin_continuous_measure(**kwargs)

        elif cmd.startswith('full_measure'):
            # full_measure channel [time_between=S] [hall_*=...] [lockin_*=...]
            if not self._require_instrument("hall", "full_measure"):
                return
            if not self._require_instrument("lockin", "full_measure"):
                return
            if not self._require_instrument("switch", "full_measure"):
                return
            parts = command.split()
            if len(parts) >= 2:
                channel = parts[1]
                kwargs = {}
                for part in parts[2:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        # Hall parameters
                        if key == 'hall_current':
                            kwargs['hall_current'] = float(value)
                        elif key == 'hall_nplc':
                            kwargs['hall_nplc'] = int(value)
                        elif key == 'hall_compliance':
                            kwargs['hall_compliance'] = float(value)
                        elif key == 'hall_voltage_range':
                            kwargs['hall_voltage_range'] = value
                        elif key == 'hall_filter':
                            kwargs['hall_filter'] = int(value)
                        elif key == 'hall_tbm':
                            kwargs['hall_tbm'] = float(value)
                        # LockIn parameters
                        elif key == 'lockin_what':
                            kwargs['lockin_what'] = tuple(ch.strip() for ch in value.split(','))
                        elif key == 'lockin_current':
                            kwargs['lockin_current'] = float(value)
                        elif key == 'lockin_series_resistance':
                            kwargs['lockin_series_resistance'] = float(value)
                        elif key == 'lockin_avg':
                            kwargs['lockin_avg'] = int(value)
                        elif key == 'lockin_start_sens':
                            kwargs['lockin_start_sens'] = int(value)
                        elif key == 'lockin_use_autorange':
                            kwargs['lockin_use_autorange'] = value.lower() == 'true'
                        elif key == 'lockin_use_autophase':
                            kwargs['lockin_use_autophase'] = value.lower() == 'true'
                        elif key == 'lockin_sample_delay':
                            kwargs['lockin_sample_delay'] = float(value)
                        # Other parameters
                        elif key == 'time_between':
                            kwargs['time_between'] = float(value)
                        elif key == 'current':  # Backward compat
                            kwargs['current'] = float(value)
                        elif key == 'resistance':  # Backward compat
                            kwargs['resistance'] = float(value)
                self.full_measure(channel, **kwargs)
            else:
                raise ValueError(f"Invalid full_measure command: {command}")

        elif cmd.startswith('set_ppms_field_and_fix_hall'):
            # set_ppms_field_and_fix_hall field_Oe target_hall_G [helmholtz_rate=0.1]
            if not self._require_instrument("dyna", "set_ppms_field_and_fix_hall"):
                return
            if not self._require_instrument("helmholtz", "set_ppms_field_and_fix_hall"):
                return
            if not self._require_instrument("hall", "set_ppms_field_and_fix_hall"):
                return
            parts = command.split()
            if len(parts) >= 3:
                field_Oe = float(parts[1])
                target_hall_G = float(parts[2])
                helmholtz_rate = 0.1
                if len(parts) >= 4 and '=' in parts[3]:
                    key, value = parts[3].split('=')
                    if key == 'helmholtz_rate':
                        helmholtz_rate = float(value)
                self.set_ppms_field_and_fix_hall(field_Oe, target_hall_G, helmholtz_rate)
            else:
                raise ValueError(f"Invalid set_ppms_field_and_fix_hall command: {command}")

        elif cmd.startswith('scan_ppms_field_and_fix_hall'):
            # scan_ppms_field_and_fix_hall start end step target_hall_G [rate=10.0]
            if not self._require_instrument("dyna", "scan_ppms_field_and_fix_hall"):
                return
            if not self._require_instrument("helmholtz", "scan_ppms_field_and_fix_hall"):
                return
            if not self._require_instrument("hall", "scan_ppms_field_and_fix_hall"):
                return
            parts = command.split()
            if len(parts) >= 5:
                start = float(parts[1])
                end = float(parts[2])
                step = float(parts[3])
                target_hall = float(parts[4])
                rate = 10.0
                if len(parts) >= 6 and '=' in parts[5]:
                    key, value = parts[5].split('=')
                    if key == 'rate':
                        rate = float(value)
                self.scan_ppms_field_and_fix_hall(start, end, step, target_hall, rate)
            else:
                raise ValueError(f"Invalid scan_ppms_field_and_fix_hall command: {command}")

        elif cmd == 'auto_gain':
            if not self._require_instrument("lockin", "auto_gain"):
                return
            self.lockin_auto_gain()

        elif cmd == 'auto_phase':
            if not self._require_instrument("lockin", "auto_phase"):
                return
            self.lockin_auto_phase()

        elif cmd == 'auto_reserve':
            if not self._require_instrument("lockin", "auto_reserve"):
                return
            self.lockin_auto_reserve()

        elif cmd.startswith('set_lockin_time_constant'):
            # set_lockin_time_constant SECONDS
            if not self._require_instrument("lockin", "set_lockin_time_constant"):
                return
            parts = command.split()
            if len(parts) >= 2:
                tau_seconds = float(parts[1])
                tau_idx = self._seconds_to_tau_index(tau_seconds)
                lockin.set_time_constant(tau_idx)
                self.log_message(f"LockIn time constant set to {tau_seconds}s (index {tau_idx})")
            else:
                raise ValueError(f"Invalid set_lockin_time_constant command: {command}")

        elif cmd.startswith('set_lockin_filter'):
            # set_lockin_filter DB_OCT (6, 12, 18, or 24)
            if not self._require_instrument("lockin", "set_lockin_filter"):
                return
            parts = command.split()
            if len(parts) >= 2:
                db_oct = float(parts[1])
                filter_idx = self._db_to_filter_index(db_oct)
                lockin.set_filter_slope(filter_idx)
                self.log_message(f"LockIn filter set to {int(db_oct)} dB/oct (index {filter_idx})")
            else:
                raise ValueError(f"Invalid set_lockin_filter command: {command}")

        elif cmd.startswith('set_lockin_frequency'):
            # set_lockin_frequency FREQ_HZ
            if not self._require_instrument("lockin", "set_lockin_frequency"):
                return
            parts = command.split()
            if len(parts) >= 2:
                freq_hz = float(parts[1])
                lockin.set_frequency(freq_hz)
                self.lockin_frequency.set(freq_hz)
                self.log_message(f"LockIn frequency set to {freq_hz} Hz")
            else:
                raise ValueError(f"Invalid set_lockin_frequency command: {command}")

        elif cmd.startswith('set_lockin_current'):
            # set_lockin_current CURRENT_A [series_resistance=Ω]
            if not self._require_instrument("lockin", "set_lockin_current"):
                return
            parts = command.split()
            if len(parts) >= 2:
                current_a = float(parts[1])
                series_resistance = self.lockin_r_lockin.get()
                for part in parts[2:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        if key == 'series_resistance':
                            series_resistance = float(value)
                if series_resistance <= 0:
                    raise ValueError("series_resistance must be > 0")
                lockin.set_excitation_current(current_a, series_resistance)
                self.lockin_output_current.set(current_a)
                self.lockin_r_lockin.set(series_resistance)
                try:
                    output_voltage = lockin.get_reference_amplitude()
                except Exception:
                    output_voltage = current_a * series_resistance
                if current_a == 0:
                    self.log_message("LockIn excitation set to minimum 4 mV (current=0)")
                self.log_message(
                    f"LockIn excitation set: I={current_a} A, R={series_resistance} Ohm, V={output_voltage:.6f} V"
                )
            else:
                raise ValueError(f"Invalid set_lockin_current command: {command}")

        elif cmd.startswith('add_note'):
            # add_note TEXT
            note_text = command[len('add_note'):].strip()
            self._append_note(note_text)
            self.log_message(f"Note added for next measurement: {note_text}")

        elif cmd == 'open_all_channels':
            if not self._require_instrument("switch", "open_all_channels"):
                return
            self.open_all_channels()

        elif cmd.startswith('close_channel'):
            # close_channel channel
            if not self._require_instrument("switch", "close_channel"):
                return
            parts = command.split()
            if len(parts) >= 2:
                channel = parts[1]
                self.close_channel_var.set(channel)
                self.close_channel()
            else:
                raise ValueError(f"Invalid close_channel command: {command}")

        elif cmd.startswith('configure_channel'):
            # configure_channel <channel> <I+> <V+> <V-> <I->
            if not self._require_instrument("switch", "configure_channel"):
                return
            parts = command.split()
            if len(parts) >= 6:
                channel = parts[1]
                ip, vp, vm, im = map(int, parts[2:6])
                self.configure_channel_from_script(channel, ip, vp, vm, im)
            else:
                raise ValueError(f"Invalid configure_channel command: {command}")

        else:
            raise ValueError(f"Unrecognized command: {command}")

    # Script command implementations
    def scan_dyna_field(self, start, end, step, rate, approach, loop_commands=None):
        """
        Scan Dyna magnetic field from start to end with given step, rate, and approach.
        Usage example: scan_dyna_field -1000 1000 100 10 linear
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        self.log_message(f"Scanning Dyna field: {start} to {end} Oe, step {step}, rate {rate}, approach {approach}")

        # Convert approach string to IntEnum
        approach_enum = self._get_field_approach_enum(approach)

        # Determine scan direction and number of steps
        # Use linspace to ensure we never exceed the end value and handle floating-point precision
        import numpy as np
        # Calculate number of steps, accounting for floating-point precision
        num_steps = int(round(abs(int(end) - int(start)) / int(step))) + 1
        steps = np.linspace(int(start), int(end), num_steps)
        steps = [int(s) for s in steps]  # Convert to integers

        for field in steps:
            if not self.script_running:
                break
            # Check for pause
            while self.script_paused and self.script_running:
                self.update_script_status()
                time.sleep(0.1)
            if not self.script_running:
                break
            try:
                # Set the field using DynaClass
                self._dyna_call("set_field", field, rate, approach_enum)
                self.log_message(f"Set Dyna field to {field} Oe")

                # Update current field for data recording
                self.current_inplane_field = field

                # Wait for field to stabilize
                self.log_message(f"Waiting for field to stabilize at {field} Oe...")
                max_wait = 300  # 5 minutes timeout
                start_time = time.time()
                stable_count = 0
                
                while time.time() - start_time < max_wait and stable_count < 2:
                    # Check for pause
                    while self.script_paused and self.script_running:
                        self.update_script_status()
                        time.sleep(0.1)
                    if not self.script_running:
                        return
                    
                    try:
                        err, current_field, status_num = self._dyna_call("get_field")
                        status = int(status_num)
                        # Status 4 = Holding (driven), 1 = Stable - both are stable
                        if status == 4 or status == 1:
                            stable_count += 1
                            if stable_count >= 2:
                                self.log_message(f"Field stabilized at {field} Oe (status={status})")
                                break
                        else:
                            stable_count = 0  # Reset if not stable
                        time.sleep(1.0)
                    except Exception as e:
                        self.log_message(f"Warning: Could not check field stability: {e} - continuing")
                        break

                # Execute loop commands
                if loop_commands:
                    self.execute_commands(loop_commands)

                # Small delay between steps
                time.sleep(0.5)

            except Exception as e:
                self.log_message(f"Error setting Dyna field to {field}: {e}")
                break

    def scan_dyna_temp(self, start, end, step, rate, approach, loop_commands=None):
        """
        Scan Dyna temperature from start to end with given step, rate, and approach.
        Usage example: scan_dyna_temp 300 400 10 5 fast
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        self.log_message(f"Scanning Dyna temp: {start} to {end} K, step {step}, rate {rate}, approach {approach}")

        # Convert approach string to IntEnum
        approach_enum = self._get_temp_approach_enum(approach)

        # Determine scan direction and number of steps
        # Use linspace to ensure we never exceed the end value and handle floating-point precision
        import numpy as np
        from decimal import Decimal
        # Calculate number of steps, accounting for floating-point precision
        num_steps = int(round(abs(end - start) / step)) + 1
        temps = np.linspace(start, end, num_steps)
        temps = [float(t) for t in temps]  # Keep as floats for temperature
        step_decimals = max(0, -Decimal(str(step)).as_tuple().exponent)

        for temp in temps:
            if not self.script_running:
                break
            # Check for pause
            while self.script_paused and self.script_running:
                self.update_script_status()
                time.sleep(0.1)
            if not self.script_running:
                break
            try:
                # Set the temperature using DynaClass
                temp = round(temp, step_decimals)
                temp_display = f"{temp:.{step_decimals}f}" if step_decimals > 0 else f"{int(temp)}"
                self._dyna_call("set_temperature", temp, rate, approach_enum)
                self.log_message(f"Set Dyna temperature to {temp_display} K")

                # Update current temperature for data recording
                self.current_temp = temp

                # Wait for temperature to stabilize
                self.log_message(f"Waiting for temperature to stabilize at {temp_display} K...")
                max_wait = 300  # 5 minutes timeout
                start_time = time.time()
                stable_count = 0
                
                while time.time() - start_time < max_wait and stable_count < 2:
                    # Check for pause
                    while self.script_paused and self.script_running:
                        self.update_script_status()
                        time.sleep(0.1)
                    if not self.script_running:
                        return
                    
                    try:
                        err, current_temp, status_num, status_name = self._dyna_call("get_temperature")
                        status = int(status_num)
                        # Status 1 = Stable
                        if status == 1:
                            stable_count += 1
                            if stable_count >= 2:
                                self.log_message(f"Temperature stabilized at {current_temp} K (status={status})")
                                break
                        else:
                            stable_count = 0  # Reset if not stable
                        time.sleep(2.0)
                    except Exception as e:
                        self.log_message(f"Warning: Could not check temperature stability: {e} - continuing")
                        break

                # Execute loop commands
                if loop_commands:
                    self.execute_commands(loop_commands)

                # Small delay between steps
                time.sleep(1.0)  # Longer delay for temperature changes

            except Exception as e:
                self.log_message(f"Error setting Dyna temperature to {temp}: {e}")
                break

    def scan_helmholtz_field(self, start, end, step, rate, approach, loop_commands=None):
        """
        Scan Helmholtz coil field from start to end with given step, rate, and approach.
        Waits for field to stabilize before executing loop commands at each step.
        Usage example: scan_helmholtz_field 0 1000 50 5 linear
        """
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        self.log_message(f"Scanning Helmholtz field: {start} to {end} Oe, step {step}, rate {rate}, approach {approach}")

        # Determine scan direction and number of steps
        # Use linspace to ensure we never exceed the end value and handle floating-point precision
        import numpy as np
        # Calculate number of steps, accounting for floating-point precision
        num_steps = int(round(abs(int(end) - int(start)) / int(step))) + 1
        fields = np.linspace(int(start), int(end), num_steps)
        fields = [int(f) for f in fields]  # Convert to integers

        for field in fields:
            if not self.script_running:
                break
            # Check for pause
            while self.script_paused and self.script_running:
                self.update_script_status()
                time.sleep(0.1)
            if not self.script_running:
                break
            try:
                # Calculate current needed for this field (using coil calibration 341.71 G/A)
                # Conversion: 1 Oe = 1 G, so current = field(Oe) * 1 G/Oe / 341.71 G/A = field / 341.71 A/Oe
                current_per_oe = 1.0 / 341.71  # A/Oe - coil calibration factor
                target_current = field * current_per_oe

                # Ramp to the target current
                self.ramp_helmholtz_current(target_current, rate)
                self.log_message(f"Ramping Helmholtz field to {field} Oe (current: {target_current:.6f} A)...")

                # Wait for helmholtz field to stabilize by comparing actual vs target current
                max_wait = 300  # 5 minutes timeout
                max_checks = 150  # Maximum number of stability checks
                start_time = time.time()
                stable_count = 0
                check_count = 0
                
                while time.time() - start_time < max_wait and check_count < max_checks and stable_count < 2:
                    # Check for pause
                    while self.script_paused and self.script_running:
                        self.update_script_status()
                        time.sleep(0.1)
                    if not self.script_running:
                        return
                    
                    try:
                        # Get actual current and compare with target
                        self.device.update_current()  # Manually update to track ramping state
                        
                        # Get sum of both channels (target is also the sum)
                        actual_current = self.device.actual_current_a + self.device.actual_current_b
                        
                        # Consider stable if actual current is within 1% of target or 1 mA, whichever is larger
                        tolerance = max(abs(target_current) * 0.01, 0.001)
                        is_stable = abs(actual_current - target_current) < tolerance
                        
                        check_count += 1
                        
                        if is_stable:
                            # Current has reached target
                            stable_count += 1
                            self.log_message(f"  Stability check {stable_count}/2: Helmholtz at target ({actual_current:.6f}A ≈ {target_current:.6f}A)")
                            if stable_count >= 2:
                                self.log_message(f"Helmholtz field stabilized at {field} Oe (current: {target_current:.6f} A) after {check_count} checks")
                                break
                        else:
                            # Still ramping toward target
                            stable_count = 0
                            if check_count % 5 == 0:  # Log every 5 checks to avoid spam
                                self.log_message(f"  [...] Ramping to {field}Oe (check {check_count}/150): {actual_current:.6f}A → {target_current:.6f}A (delta={abs(actual_current-target_current):.6f}A)")
                        
                        time.sleep(1.0)
                    except Exception as e:
                        self.log_message(f"Warning: Could not check helmholtz stability: {e} - continuing")
                        break
                
                if check_count >= max_checks:
                    self.log_message(f"Warning: Helmholtz field at {field} Oe did not stabilize after {max_checks} checks ({max_wait}s timeout) - continuing anyway")
                elif time.time() - start_time >= max_wait:
                    self.log_message(f"Warning: Helmholtz field at {field} Oe did not stabilize within {max_wait}s - continuing anyway")

                # Update current field for data recording
                self.current_helmholtz_field = field

                # Execute loop commands
                if loop_commands:
                    self.execute_commands(loop_commands)

                # Small delay between steps
                time.sleep(0.5)

            except Exception as e:
                self.log_message(f"Error setting Helmholtz field to {field}: {e}")
                break

    def set_dyna_field(self, field, rate, approach):
        """
        Set Dyna magnetic field to a specific value.
        Usage example: set_dyna_field 500 10 linear
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        self.log_message(f"Setting Dyna field: {field} Oe, rate {rate}, approach {approach}")

        try:
            # Convert approach string to IntEnum
            approach_enum = self._get_field_approach_enum(approach)

            # Set the field using DynaClass
            self._dyna_call("set_field", field, rate, approach_enum)
            self.log_message(f"Dyna field set to {field} Oe")

            # Update current field for data recording
            self.current_inplane_field = field

            # Wait for field to stabilize
            time.sleep(2.0)

        except Exception as e:
            self.log_message(f"Error setting Dyna field: {e}")

    def set_dyna_temp(self, temp, rate, approach):
        """
        Set Dyna temperature to a specific value.
        Usage example: set_dyna_temp 350 2 fast
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        self.log_message(f"Setting Dyna temp: {temp} K, rate {rate}, approach {approach}")

        try:
            # Convert approach string to IntEnum
            approach_enum = self._get_temp_approach_enum(approach)

            # Set the temperature using DynaClass
            self._dyna_call("set_temperature", temp, rate, approach_enum)
            self.log_message(f"Dyna temperature set to {temp} K")

            # Update current temperature for data recording
            self.current_temp = temp

            # Wait for temperature to stabilize (longer wait for temp changes)
            time.sleep(5.0)

        except Exception as e:
            self.log_message(f"Error setting Dyna temperature: {e}")

    def set_helmholtz_field(self, field, rate):
        """
        Set Helmholtz coil field to a specific value.
        Usage example: set_helmholtz_field 200 5
        """
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        self.log_message(f"Setting Helmholtz field: {field} Oe, rate {rate}")

        try:
            # Calculate current needed for this field
            current_per_oe = 1.0/341.71  # A/Oe - adjust based on your coil calibration
            target_current = field * current_per_oe

            # Ramp to the target current
            self.ramp_helmholtz_current(target_current, rate)
            self.log_message(f"Helmholtz field set to {field} Oe (current: {target_current} A)")

            # Update current field for data recording
            self.current_helmholtz_field = field

            # Wait for field to stabilize
            time.sleep(1.0)

        except Exception as e:
            self.log_message(f"Error setting Helmholtz field: {e}")

    def ramp_helmholtz_current(self, target_current, rate):
        """
        Ramp the Helmholtz current to target_current with given rate.
        Enables output after setting parameters.
        """
        self.set_current.set(target_current)
        self.ramp_rate.set(rate)
        self.set_values()  # Set current, compliance, ramp_rate
        self.enable_output()  # Enable output after parameters are set

    def wait_for_events(self, events, additional_time):
        """
        Wait for one or more events in sequence, then wait additional time with countdown.
        
        Supported event names:
          - temp: Wait for PPMS temperature subsystem to stabilize (PPMS only)
          - field: Wait for PPMS field to stabilize (PPMS only)
          - helmholtz: Wait for Helmholtz current to stabilize (no PPMS polling)
          - no_event: Simple time delay without PPMS polling
          - all: Expands to [temp, field, helmholtz]
        
        Execution order: Events execute in the order specified, then final countdown.
        Examples:
          wait_for temp 10 → temp stability, then 10s countdown
          wait_for temp field 10 → temp, then field, then 10s countdown
          wait_for all 10 → temp, field, helmholtz, then 10s countdown
          wait_for no_event 10 → just 10s countdown (no stability checks)
        """
        self.log_message(f"Waiting for events: {', '.join(events)}, then {additional_time}s")
        
        def countdown_wait(duration, respect_script=True):
            """Wait with countdown in 1-second intervals, respecting pause"""
            remaining = int(duration)
            while remaining > 0:
                # Check for pause
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                if respect_script and not self.script_running:
                    return
                self.log_message(f"Countdown: {remaining}s remaining...")
                time.sleep(1.0)
                remaining -= 1
            # Handle any fractional seconds
            fractional = duration - int(duration)
            if fractional > 0:
                time.sleep(fractional)
        
        # Special case: no_event (just countdown, no waiting)
        if events == ['no_event']:
            countdown_wait(additional_time, respect_script=False)
            return
        
        # Execute each event in order
        for event in events:
            try:
                if event.lower() == 'temp':
                    self._wait_for_temp_stable()
                elif event.lower() == 'field':
                    self._wait_for_field_stable()
                elif event.lower() == 'helmholtz':
                    self._wait_for_helmholtz_field()
            except Exception as e:
                self.log_message(f"Error waiting for event '{event}': {e}")
        
        # Final countdown
        if additional_time > 0:
            self.log_message(f"Waiting additional {additional_time}s...")
            countdown_wait(additional_time)
        
        self.log_message(f"All events completed")

    def _wait_for_temp_stable(self):
        """Wait for PPMS temperature to stabilize (helper for wait_for_events)"""
        self.log_message("Waiting for temperature stabilization...")
        max_wait = 18000  # 5 hours timeout (for high temp changes)
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < max_wait and stable_count < 2:
            try:
                err, temp, status_num, status_name = self._dyna_call("get_temperature")
                temp_str = str(temp).strip().lower()
                
                # Check if temp value is 'nan' - indicates unknown state
                if temp_str == 'nan':
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    note_msg = f"PPMS temp state unknown (temp=nan) at {timestamp}"
                    self._append_note(note_msg)
                    self.log_message(f"WARNING: {note_msg} - treating as stable and continuing")
                    break
                
                status = int(status_num)
                # Status 1 = Stable
                if status == 1:
                    stable_count += 1
                    if stable_count >= 2:
                        self.log_message(f"Temperature stable at {temp}K")
                        break
                else:
                    stable_count = 0  # Reset if not stable
                
                time.sleep(2.0)
            except Exception as e:
                # Communication error - treat as unknown
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                note_msg = f"PPMS temp communication error at {timestamp}"
                self._append_note(note_msg)
                self.log_message(f"WARNING: {note_msg} - treating as stable and continuing")
                break

    def _wait_for_field_stable(self):
        """Wait for PPMS field to stabilize (helper for wait_for_events)"""
        self.log_message("Waiting for field stabilization...")
        max_wait = 18000  # 5 hours timeout (for high field changes)
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < max_wait and stable_count < 2:
            try:
                err, field, status_num = self._dyna_call("get_field")
                field_str = str(field).strip().lower()
                
                # Check if field value is 'nan' - indicates unknown state
                if field_str == 'nan':
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    note_msg = f"PPMS field state unknown (field=nan) at {timestamp}"
                    self._append_note(note_msg)
                    self.log_message(f"WARNING: {note_msg} - treating as stable and continuing")
                    break
                
                status = int(status_num)
                # Status 4 = Holding (driven), 1 = Stable - both are stable
                if status == 4 or status == 1:
                    stable_count += 1
                    if stable_count >= 2:
                        self.log_message(f"Field stable at {field}Oe (status={status})")
                        break
                else:
                    stable_count = 0  # Reset if not stable
                
                time.sleep(2.0)
            except Exception as e:
                # Communication error - treat as unknown
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                note_msg = f"PPMS field communication error at {timestamp}"
                self._append_note(note_msg)
                self.log_message(f"WARNING: {note_msg} - treating as stable and continuing")
                break
        
        self.log_message("Field stabilization completed!")

    def _wait_for_helmholtz_field(self):
        """Wait for Helmholtz current to stabilize (helper for wait_for_events)"""
        self.log_message("Waiting for helmholtz current to stabilize...")
        max_wait = 300  # 5 minutes timeout
        max_checks = 150  # Maximum number of stability checks
        start_time = time.time()
        stable_count = 0
        check_count = 0
        
        while time.time() - start_time < max_wait and check_count < max_checks and stable_count < 2:
            # Check for pause
            while self.script_paused and self.script_running:
                self.update_script_status()
                time.sleep(0.1)
            if not self.script_running:
                return
            
            try:
                # Get target and actual currents (need to update manually during script execution)
                self.device.update_current()  # Manually update to track ramping state
                target_current = self.set_current.get()
                
                # Get sum of both channels (target is also the sum)
                actual_current = self.device.actual_current_a + self.device.actual_current_b
                
                # Consider stable if actual current is within 1% of target or 1 mA, whichever is larger
                tolerance = max(abs(target_current) * 0.01, 0.001)
                is_stable = abs(actual_current - target_current) < tolerance
                
                check_count += 1
                
                if is_stable:
                    # Current has reached target
                    stable_count += 1
                    self.log_message(f"  Stability check {stable_count}/2: Helmholtz at target ({actual_current:.6f}A ≈ {target_current:.6f}A)")
                    if stable_count >= 2:
                        self.log_message(f"Helmholtz current stable at target after {check_count} checks")
                        break
                else:
                    # Still ramping toward target
                    stable_count = 0
                    if check_count % 5 == 0:  # Log every 5 checks to avoid spam
                        self.log_message(f"  [...] Ramping (check {check_count}/150): {actual_current:.6f}A → {target_current:.6f}A (delta={abs(actual_current-target_current):.6f}A)")
                
                time.sleep(1.0)
            except Exception as e:
                self.log_message(f"Warning: Could not check helmholtz stability: {e} - continuing")
                break
        
        if check_count >= max_checks:
            self.log_message(f"Warning: Helmholtz did not stabilize after {max_checks} checks ({max_wait}s timeout) - continuing anyway")
        elif time.time() - start_time >= max_wait:
            self.log_message(f"Warning: Helmholtz field did not stabilize within {max_wait}s - continuing anyway")
        
        self.log_message("Helmholtz field stability check completed!")

    def wait_for_event(self, event, additional_time):
        """
        DEPRECATED: Use wait_for_events instead.
        Wait for a specific event to occur, then wait additional time with countdown.
        
        Supported events:
          - temp_stable: Wait for PPMS temperature subsystem to stabilize
          - field_stable: Wait for PPMS field to hold AND verify helmholtz current is stable
          - dyna_ready: Wait for BOTH PPMS temp AND field, AND verify helmholtz current is stable
          - helmholtz_field: Wait for Helmholtz current to stabilize (no PPMS polling)
          - no_event: Simple time delay without PPMS polling
        
        Helmholtz stability check: For field_stable, dyna_ready, and helmholtz_field events,
        we verify helmholtz current is not drifting (sample before/after 1-second interval).
        This ensures measurement stability since PPMS and helmholtz are independent systems.
        
        Usage example: wait_for field_stable 10
        """
        pass  # Deprecated - use wait_for_events instead

    def execute_commands(self, commands):
        """Execute a list of script commands
        
        Parameters
        ----------
        commands : list
            List of command strings (old format) or tuples of (command, line_number) (new format for loop bodies)
        """
        for item in commands:
            if not self.script_running:
                break
            # Check for pause
            while self.script_paused and self.script_running:
                self.update_script_status()
                time.sleep(0.1)
            if not self.script_running:
                break
            
            # Handle both old format (string) and new format (tuple with line number)
            if isinstance(item, tuple):
                cmd, line_number = item
                # Highlight the loop body line in red
                self.highlight_loop_body_line(line_number)
            else:
                cmd = item
            
            self.execute_script_command(cmd)
            time.sleep(0.1)  # Small delay between commands
        
        # Clear loop body highlight when done
        self.clear_loop_body_highlight()
    
    def highlight_loop_body_line(self, line_number):
        """Highlight a loop body line in red"""
        try:
            if self.root.winfo_exists():
                callback_id = self.root.after(50, self._update_loop_body_highlight, line_number)
                if len(self._pending_callbacks) < 1000:
                    self._pending_callbacks.append(callback_id)
        except:
            pass  # Root may have been destroyed
    
    def _update_loop_body_highlight(self, line_number):
        """Internal method to update loop body highlight - runs on main thread"""
        try:
            if not self.root.winfo_exists():
                return
            
            # Remove previous loop body highlight
            self.script_text.tag_remove("loop_body_line", "1.0", tk.END)
            
            if line_number > 0:
                # Highlight the loop body line (line_number is 1-indexed)
                line_start = f"{line_number}.0"
                line_end = f"{line_number}.end"
                self.script_text.tag_add("loop_body_line", line_start, line_end)
        except:
            pass  # Widget may have been destroyed
    
    def clear_loop_body_highlight(self):
        """Clear the loop body highlight"""
        try:
            if self.root.winfo_exists():
                self.script_text.tag_remove("loop_body_line", "1.0", tk.END)
        except:
            pass  # Widget may have been destroyed

    def _get_field_approach_enum(self, approach_str):
        """Convert approach string to DynaClass Field_mode IntEnum"""
        approach_map = {
            'linear': dyna.Field_mode.linear,
            'no_overshoot': dyna.Field_mode.no_overshoot,
            'oscillate': dyna.Field_mode.oscillate
        }
        return approach_map.get(approach_str.lower(), dyna.Field_mode.linear)

    def _get_temp_approach_enum(self, approach_str):
        """Convert approach string to DynaClass Temp_mode IntEnum"""
        approach_map = {
            'fast_settle': dyna.Temp_mode.fast_settle,
            'no_overshoot': dyna.Temp_mode.no_overshoot,
            'fast': dyna.Temp_mode.fast_settle  # alias
        }
        return approach_map.get(approach_str.lower(), dyna.Temp_mode.no_overshoot)

    # ------------------------------
    # UI: Switch tab
    # ------------------------------
    # UI: Switch tab with Photo Annotation
    # ------------------------------
    def create_switch_widgets(self):
        self._create_connection_header(self.switch_tab, "Switch", "switch", columnspan=2)

        # Left frame: Channel controls
        self.switch_left_frame = ttk.Frame(self.switch_tab, padding=10)
        self.switch_left_frame.grid(row=1, column=0, sticky="ns")

        # Right frame: Photo annotation
        self.switch_right_frame = ttk.Frame(self.switch_tab, padding=10)
        self.switch_right_frame.grid(row=1, column=1, sticky="nsew")

        # ============ LEFT FRAME: Channel Controls ============
        self.channel_frames = {}
        self.channel_labels = {}

        for ch in self.channels:
            # Channel frame with border
            channel_frame = ttk.LabelFrame(self.switch_left_frame, text=f"Channel {ch}", padding=5)
            channel_frame.pack(pady=5, fill="x")

            # Grid for entries: 2 rows (labels, entries), 4 columns
            for i, line in enumerate(["I+", "V+", "V-", "I-"]):
                ttk.Label(channel_frame, text=line).grid(row=0, column=i, padx=2, pady=2)
                entry = ttk.Entry(channel_frame, textvariable=self.channel_configs[ch][line], width=5)
                entry.grid(row=1, column=i, padx=2, pady=2)
                self._register_tab_control("switch", entry)

            self.channel_frames[ch] = channel_frame

        # Status labels below channels
        for ch in self.channels:
            label = ttk.Label(self.switch_left_frame, text=f"Channel {ch}: Open")
            label.pack(pady=2)
            self.channel_labels[ch] = label

        # Controls on the left side
        open_all_button = ttk.Button(self.switch_left_frame, text="Open All", command=self.open_all_channels)
        open_all_button.pack(pady=10)
        self._register_tab_control("switch", open_all_button)

        ttk.Label(self.switch_left_frame, text="Close Channel:").pack(anchor='w', pady=(10, 2))
        self.close_channel_var = tk.StringVar(value="a")
        close_frame = ttk.Frame(self.switch_left_frame)
        close_frame.pack(fill="x", pady=2)
        close_combo = ttk.Combobox(close_frame, textvariable=self.close_channel_var, values=self.channels, state="readonly", width=8)
        close_combo.pack(side="left", padx=(0, 5))
        self._register_tab_control("switch", close_combo, enabled_state="readonly")
        close_button = ttk.Button(close_frame, text="Close", command=self.close_channel)
        close_button.pack(side="left")
        self._register_tab_control("switch", close_button)

        # ============ RIGHT FRAME: Photo Annotation ============
        ttk.Label(self.switch_right_frame, text="Device Photo Annotation", font=("Arial", 11, "bold")).pack(pady=(0, 10))

        # Photo control buttons
        photo_btn_frame = ttk.Frame(self.switch_right_frame)
        photo_btn_frame.pack(fill="x", pady=5)
        ttk.Button(photo_btn_frame, text="Load Photo", command=self._load_device_photo).pack(side="left", padx=2)
        ttk.Button(photo_btn_frame, text="Export Annotated", command=self._export_annotated_photo).pack(side="left", padx=2)

        # Label control frame
        label_ctrl_frame = ttk.LabelFrame(self.switch_right_frame, text="Label Controls", padding=5)
        label_ctrl_frame.pack(fill="x", pady=5)

        # Color selector
        ttk.Label(label_ctrl_frame, text="Label Color:").grid(row=0, column=0, sticky='w', padx=2, pady=2)
        color_combo = ttk.Combobox(label_ctrl_frame, textvariable=self.label_color, 
                                   values=["black", "white", "red", "yellow", "green", "blue"], 
                                   state="readonly", width=12)
        color_combo.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        color_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw_photo_canvas())

        # Text size
        ttk.Label(label_ctrl_frame, text="Text Size:").grid(row=1, column=0, sticky='w', padx=2, pady=2)
        size_spinbox = ttk.Spinbox(label_ctrl_frame, from_=8, to=100, textvariable=self.label_text_size, width=15)
        size_spinbox.grid(row=1, column=1, sticky='ew', padx=2, pady=2)
        size_spinbox.bind("<FocusOut>", lambda e: self._redraw_photo_canvas())

        # Label buttons (1-8)
        label_btn_frame = ttk.Frame(label_ctrl_frame)
        label_btn_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(label_btn_frame, text="Place Label:").pack(side="left", padx=2)
        for num in range(1, 9):
            btn = ttk.Button(label_btn_frame, text=str(num), width=3,
                      command=lambda n=num: self._prepare_label_placement(n))
            btn.pack(side="left", padx=1)
            self.label_buttons[num] = btn

        # Delete selected label button
        ttk.Button(label_ctrl_frame, text="Delete Selected Label", 
                  command=self._delete_selected_label).grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)

        label_ctrl_frame.columnconfigure(1, weight=1)

        # Canvas for photo display
        canvas_frame = ttk.LabelFrame(self.switch_right_frame, text="Photo Preview", padding=5)
        canvas_frame.pack(fill="both", expand=True, pady=5)

        self.photo_canvas = tk.Canvas(canvas_frame, bg="gray20", height=400, width=400)
        self.photo_canvas.pack(fill="both", expand=True)
        self.photo_canvas.bind("<Button-1>", self._on_canvas_click)
        self.photo_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.photo_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.photo_canvas.bind("<Button-3>", self._on_canvas_right_click)

        self.update_switch_status()

    def _load_device_photo(self):
        """Load a device photo from file"""
        file_path = filedialog.askopenfilename(
            title="Select Device Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            self.device_photo_path = Path(file_path)
            self.photo_image = Image.open(self.device_photo_path)
            
            # Resize to fit canvas (~400x400)
            self.photo_image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Load existing annotations for this photo
            self._load_annotations()
            
            # Draw canvas
            self._redraw_photo_canvas()
            
            self.log_message(f"Photo loaded: {self.device_photo_path.name}")
        except Exception as e:
            messagebox.showerror("Photo Load Error", f"Failed to load photo: {e}")

    def _redraw_photo_canvas(self):
        """Redraw canvas with photo and labels"""
        if self.photo_canvas is None or self.photo_image is None:
            return
        
        try:
            # Convert PIL image to PhotoImage for tkinter
            from PIL import ImageTk
            img_copy = self.photo_image.copy()
            draw = ImageDraw.Draw(img_copy)
            
            # Draw labels on image
            for label_num, label_data in self.photo_labels.items():
                x = label_data["x"]
                y = label_data["y"]
                color = label_data["color"]
                size = self.label_text_size.get()
                
                # Convert color name to tuple
                color_map = {
                    "black": (0, 0, 0),
                    "white": (255, 255, 255),
                    "red": (255, 0, 0),
                    "yellow": (255, 255, 0),
                    "green": (0, 255, 0),
                    "blue": (0, 0, 255)
                }
                rgb_color = color_map.get(color, (255, 255, 255))
                
                # Try to use a nice font, fallback to default
                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except:
                    font = ImageFont.load_default()
                
                # Draw circle background for label
                circle_radius = size // 2 + 5
                draw.ellipse(
                    [(x - circle_radius, y - circle_radius), 
                     (x + circle_radius, y + circle_radius)],
                    fill=rgb_color,
                    outline=rgb_color
                )
                
                # Draw text (opposite color for contrast)
                text_color = (255, 255, 255) if color != "white" else (0, 0, 0)
                draw.text((x, y), str(label_num), fill=text_color, font=font, anchor="mm")
            
            # Convert to PhotoImage
            photo_tk = ImageTk.PhotoImage(img_copy)
            
            # Update canvas
            self.photo_canvas.delete("all")
            self.photo_canvas.create_image(0, 0, image=photo_tk, anchor="nw")
            self.photo_canvas.image = photo_tk  # Keep a reference!
            
        except Exception as e:
            print(f"Error redrawing canvas: {e}")

    def _prepare_label_placement(self, label_num):
        """Prepare to place a label (or update existing) with non-blocking window"""
        if self.photo_image is None:
            messagebox.showinfo("No Photo", "Please load a photo first")
            return
        
        # Close any existing placement window
        self._close_label_placement_window()
        
        # Set selected label
        self.selected_label = label_num
        
        # Create non-blocking Toplevel window
        self.label_placement_window = tk.Toplevel(self.root)
        self.label_placement_window.title(f"Place Label {label_num}")
        self.label_placement_window.geometry("300x100")
        self.label_placement_window.attributes("-topmost", True)  # Stay on top
        
        # Determine if editing or creating
        is_editing = label_num in self.photo_labels
        
        # Create message label
        message = f"Click on canvas to {'reposition' if is_editing else 'place'} label {label_num}"
        ttk.Label(self.label_placement_window, text=message, wraplength=280).pack(pady=20)
        
        # Add instructions
        ttk.Label(self.label_placement_window, text="Window will close automatically after placement", 
                 font=("Arial", 8), foreground="gray").pack()

    def _close_label_placement_window(self):
        """Close the label placement popup window"""
        if self.label_placement_window is not None:
            try:
                self.label_placement_window.destroy()
            except:
                pass
            self.label_placement_window = None

    def _on_canvas_click(self, event):
        """Handle canvas click for placing/selecting labels"""
        if self.photo_image is None:
            return
        
        # Check if clicking on existing label
        for label_num, label_data in self.photo_labels.items():
            x, y = label_data["x"], label_data["y"]
            distance = ((event.x - x) ** 2 + (event.y - y) ** 2) ** 0.5
            if distance < 20:  # Click near label
                self.selected_label = label_num
                self.dragging_label = label_num
                self.drag_offset = (event.x - x, event.y - y)
                return
        
        # If a label is being prepared, place it
        if self.selected_label is not None and self.selected_label not in self.photo_labels:
            self.photo_labels[self.selected_label] = {
                "x": event.x,
                "y": event.y,
                "color": self.label_color.get()
            }
            self._save_annotations()
            self._redraw_photo_canvas()
            self._update_label_button_states()  # Gray out used labels
            self._close_label_placement_window()  # Auto-close after placement
            self.selected_label = None  # Clear selection

    def _on_canvas_drag(self, event):
        """Handle label dragging"""
        if self.dragging_label is not None and self.dragging_label in self.photo_labels:
            label_data = self.photo_labels[self.dragging_label]
            label_data["x"] = event.x - self.drag_offset[0]
            label_data["y"] = event.y - self.drag_offset[1]
            self._redraw_photo_canvas()

    def _on_canvas_release(self, event):
        """Handle drag release"""
        if self.dragging_label is not None:
            self._save_annotations()
            self.dragging_label = None
            self._redraw_photo_canvas()
            self._close_label_placement_window()  # Close window after repositioning
            self.selected_label = None  # Clear selection

    def _on_canvas_right_click(self, event):
        """Handle right-click to delete label"""
        if self.photo_image is None:
            return
        
        for label_num, label_data in self.photo_labels.items():
            x, y = label_data["x"], label_data["y"]
            distance = ((event.x - x) ** 2 + (event.y - y) ** 2) ** 0.5
            if distance < 20:
                del self.photo_labels[label_num]
                self.selected_label = None
                self._save_annotations()
                self._redraw_photo_canvas()
                self._update_label_button_states()  # Re-enable deleted label button
                return

    def _delete_selected_label(self):
        """Delete currently selected label"""
        if self.selected_label is not None and self.selected_label in self.photo_labels:
            del self.photo_labels[self.selected_label]
            self.selected_label = None
            self._update_label_button_states()  # Re-enable deleted label button
            self._save_annotations()
            self._redraw_photo_canvas()

    def _update_label_button_states(self):
        """Gray out buttons for labels that are already placed"""
        for num in range(1, 9):
            if num in self.label_buttons:
                if num in self.photo_labels:
                    self.label_buttons[num].config(state="disabled")
                else:
                    self.label_buttons[num].config(state="normal")

    def _save_annotations(self):
        """Save annotations to JSON file"""
        if self.device_photo_path is None:
            return
        
        try:
            # Create annotation data with photo path reference
            anno_data = {
                "photo_path": str(self.device_photo_path),
                "labels": self.photo_labels
            }
            
            with open(self.annotations_file, 'w') as f:
                json.dump(anno_data, f, indent=2)
        except Exception as e:
            print(f"Error saving annotations: {e}")

    def _load_annotations(self):
        """Load annotations from JSON file"""
        if not self.annotations_file.exists():
            self.photo_labels = {}
            return
        
        try:
            with open(self.annotations_file, 'r') as f:
                anno_data = json.load(f)
            
            # Check if annotations match current photo
            if anno_data.get("photo_path") == str(self.device_photo_path):
                self.photo_labels = anno_data.get("labels", {})
                # Convert string keys to int
                self.photo_labels = {int(k): v for k, v in self.photo_labels.items()}
            else:
                self.photo_labels = {}
        except Exception as e:
            print(f"Error loading annotations: {e}")
            self.photo_labels = {}
        
        self._update_label_button_states()  # Update button states after loading

    def _export_annotated_photo(self):
        """Export photo with annotations burned in"""
        if self.photo_image is None:
            messagebox.showinfo("No Photo", "Please load a photo first")
            return
        
        # Ask user where to save
        file_path = filedialog.asksaveasfilename(
            title="Save Annotated Photo",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPG files", "*.jpg"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            # Create a copy of the photo to export
            export_img = self.photo_image.copy()
            draw = ImageDraw.Draw(export_img)
            
            # Draw all labels
            for label_num, label_data in self.photo_labels.items():
                x = label_data["x"]
                y = label_data["y"]
                color = label_data["color"]
                size = self.label_text_size.get()
                
                color_map = {
                    "black": (0, 0, 0),
                    "white": (255, 255, 255),
                    "red": (255, 0, 0),
                    "yellow": (255, 255, 0),
                    "green": (0, 255, 0),
                    "blue": (0, 0, 255)
                }
                rgb_color = color_map.get(color, (255, 255, 255))
                
                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except:
                    font = ImageFont.load_default()
                
                # Draw circle background
                circle_radius = size // 2 + 5
                draw.ellipse(
                    [(x - circle_radius, y - circle_radius), 
                     (x + circle_radius, y + circle_radius)],
                    fill=rgb_color,
                    outline=rgb_color
                )
                
                # Draw text
                text_color = (255, 255, 255) if color != "white" else (0, 0, 0)
                draw.text((x, y), str(label_num), fill=text_color, font=font, anchor="mm")
            
            # Save the exported image
            export_img.save(file_path)
            messagebox.showinfo("Export Successful", f"Photo saved to:\n{file_path}")
            self.log_message(f"Annotated photo exported: {Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export photo: {e}")

    def update_switch_ui(self):
        # Since channels are fixed to 'a' and 'b', just update status
        self.update_switch_status()

    def open_all_channels(self):
        if not self.instrument_connected.get("switch", False) or switch is None:
            self.log_message("ERROR: Switch not connected")
            return
        # Start switch LED blink
        self.led_blink("switch", 100)
        switch.open_all()
        self.active_channel = None
        self.update_switch_status()
        # Stop switch LED blink after operation
        self.root.after(500, self.led_off, "switch")

    def close_channel(self):
        if not self.instrument_connected.get("switch", False) or switch is None:
            self.log_message("ERROR: Switch not connected")
            return
        # Start switch LED blink
        self.led_blink("switch", 100)
        ch = self.close_channel_var.get().strip()
        if ch in self.channel_configs:
            self.active_channel = ch
            config = self.channel_configs[ch]
            switch.close_list(config['I+'].get(), config['V+'].get(), config['V-'].get(), config['I-'].get())
            self.update_switch_status()
        # Stop switch LED blink after operation
        self.root.after(500, self.led_off, "switch")

    def update_switch_status(self):
        if not self.instrument_connected.get("switch", False) or switch is None:
            return  # Skip status update if switch not connected
        for ch, label in self.channel_labels.items():
            config = self.channel_configs[ch]
            is_closed = any(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"])
            status = "Closed" if is_closed else "Open"
            label.config(text=f"Channel {ch}: {status}")
        if hasattr(self, "results_switch_status"):
            self.results_switch_status.config(text=self._get_switch_state_summary())

    def _get_switch_state_summary(self):
        if not self.instrument_connected.get("switch", False) or switch is None:
            return "Switch: Disconnected"
        states = []
        for ch in self.channels:
            config = self.channel_configs[ch]
            is_closed = any(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"])
            state = "Closed" if is_closed else "Open"
            states.append(f"{ch}:{state}")
        return "Switch: " + ", ".join(states)
    
    def configure_channel_from_script(self, channel, ip, vp, vm, im):
        """
        Reconfigure a channel's routing numbers from a script command.
        Opens all channels, updates configuration, syncs GUI, and logs to data file.
        
        Args:
            channel: Channel name ('a' or 'b')
            ip: I+ routing number (1-8)
            vp: V+ routing number (1-8)
            vm: V- routing number (1-8)
            im: I- routing number (1-8)
        """
        if channel not in self.channel_configs:
            raise ValueError(f"Invalid channel '{channel}'. Valid: {list(self.channel_configs.keys())}")
        
        # Validate routing numbers are in range 1-8
        routing_nums = [ip, vp, vm, im]
        for num in routing_nums:
            if num < 1 or num > 8:
                raise ValueError(f"Routing number {num} out of range (1-8)")
        
        # Check for duplicates within channel
        if len(routing_nums) != len(set(routing_nums)):
            raise ValueError(f"Duplicate routing numbers: {routing_nums}")
        
        # Check for conflicts with other channels (warning only)
        conflict_warning = self._validate_routing_uniqueness(channel, ip, vp, vm, im)
        if conflict_warning:
            self.log_message(f"WARNING: {conflict_warning}")
        
        # Open all channels before reconfiguration
        if switch is not None:
            self.open_all_channels()
        
        # Update configuration in channel_configs dictionary
        self.channel_configs[channel]['I+'].set(ip)
        self.channel_configs[channel]['V+'].set(vp)
        self.channel_configs[channel]['V-'].set(vm)
        self.channel_configs[channel]['I-'].set(im)
        
        # Update GUI display (spinboxes automatically reflect IntVar changes)
        self.update_switch_status()

        # Ensure channels stay open after reconfiguration
        if switch is not None:
            self.open_all_channels()
        
        # Create note for data file
        note = f"Reconfigured channel {channel}: I+={ip}, V+={vp}, V-={vm}, I-={im}"
        self._append_note(note)
        self.log_message(note)
    
    def _validate_routing_uniqueness(self, channel, ip, vp, vm, im):
        """
        Check if routing numbers conflict with other channels.
        Returns warning message if conflicts found, None otherwise.
        """
        new_routing = {ip, vp, vm, im}
        
        for ch, config in self.channel_configs.items():
            if ch == channel:
                continue  # Skip the channel being configured
            
            existing_routing = {
                config['I+'].get(),
                config['V+'].get(),
                config['V-'].get(),
                config['I-'].get()
            }
            
            overlap = new_routing & existing_routing
            if overlap:
                return f"Channel {channel} routing overlaps with channel {ch}: {sorted(overlap)}"
        
        return None

    def _append_note(self, note_text):
        if not note_text:
            return
        if self.current_note:
            self.current_note = f"{self.current_note}; {note_text}"
        else:
            self.current_note = note_text

    # ------------------------------
    # UI: LockIn tab
    # ------------------------------
    def create_lockin_widgets(self):
        self._create_connection_header(self.lockin_tab, "LockIn SR830", "lockin", columnspan=3)

        self.lockin_frame = ttk.Frame(self.lockin_tab, padding=10)
        self.lockin_frame.grid(row=1, column=0, sticky="ns")

        # LockIn parameters based on LockIn_RB_RT_2
        self.lockin_frequency = tk.DoubleVar(value=173.0)
        self.lockin_time_constant_idx = tk.IntVar(value=9)  # Use index for time constant (9 = ~300ms)
        self.lockin_filter_slope = tk.StringVar(value="24")  # String for dropdown
        self.lockin_sensitivity_idx = tk.IntVar(value=10)  # Use index for sensitivity
        self.lockin_output_current = tk.DoubleVar(value=100e-9)  # A
        self.lockin_r_lockin = tk.DoubleVar(value=0.996e6)  # ohms
        self.lockin_averaging = tk.IntVar(value=10)  # Number of averages

        def row(label, var, unit):
            l = ttk.Label(self.lockin_frame, text=label)
            l.grid(column=0, row=row.i, sticky='w', pady=5)
            e = ttk.Entry(self.lockin_frame, textvariable=var, width=15)
            e.grid(column=1, row=row.i)
            u = ttk.Label(self.lockin_frame, text=unit)
            u.grid(column=2, row=row.i, sticky='w')
            self._register_tab_control("lockin", e)
            row.i += 1

        row.i = 0

        lockin_source = lockin if lockin is not None else LockInSR830

        row("Frequency", self.lockin_frequency, "Hz")
        
        # Time Constant dropdown
        ttk.Label(self.lockin_frame, text="Time Constant").grid(column=0, row=row.i, sticky='w', pady=5)
        tau_options = [f"{tau:.3g}s" for tau in lockin_source.TAU_TABLE]
        tau_combo = ttk.Combobox(self.lockin_frame, textvariable=self.lockin_time_constant_idx, 
                                  values=list(range(len(lockin_source.TAU_TABLE))), width=13, state="readonly")
        tau_combo.grid(column=1, row=row.i)
        self._register_tab_control("lockin", tau_combo, enabled_state="readonly")
        tau_label = ttk.Label(self.lockin_frame, text="")
        tau_label.grid(column=2, row=row.i, sticky='w')
        def update_tau_label(var, index, mode):
            idx = self.lockin_time_constant_idx.get()
            tau_label.config(text=f"{lockin_source.TAU_TABLE[idx]:.3g}s")
        self.lockin_time_constant_idx.trace_add('write', update_tau_label)
        update_tau_label(None, None, None)
        row.i += 1
        
        # Filter Slope dropdown
        ttk.Label(self.lockin_frame, text="Filter Slope").grid(column=0, row=row.i, sticky='w', pady=5)
        filter_options = ["6", "12", "18", "24"]
        filter_combo = ttk.Combobox(self.lockin_frame, textvariable=self.lockin_filter_slope, 
                                     values=filter_options, width=13, state="readonly")
        filter_combo.grid(column=1, row=row.i)
        self._register_tab_control("lockin", filter_combo, enabled_state="readonly")
        ttk.Label(self.lockin_frame, text="dB/oct").grid(column=2, row=row.i, sticky='w')
        row.i += 1
        
        # Sensitivity dropdown
        ttk.Label(self.lockin_frame, text="Sensitivity").grid(column=0, row=row.i, sticky='w', pady=5)
        sens_options = [f"{sens:.2e}" for sens in lockin_source.SENS_TABLE]
        sens_combo = ttk.Combobox(self.lockin_frame, textvariable=self.lockin_sensitivity_idx, 
                                   values=list(range(len(lockin_source.SENS_TABLE))), width=13, state="readonly")
        sens_combo.grid(column=1, row=row.i)
        self._register_tab_control("lockin", sens_combo, enabled_state="readonly")
        sens_label = ttk.Label(self.lockin_frame, text="")
        sens_label.grid(column=2, row=row.i, sticky='w')
        def update_sens_label(var, index, mode):
            idx = self.lockin_sensitivity_idx.get()
            sens_label.config(text=f"{lockin_source.SENS_TABLE[idx]:.2e} V")
        self.lockin_sensitivity_idx.trace_add('write', update_sens_label)
        update_sens_label(None, None, None)
        row.i += 1
        
        row("Output Current", self.lockin_output_current, "A")
        
        # R_lockin resistor box dropdown with calibrated values
        resistor_values = {
            "50 Ω": 50.38,
            "1 kΩ": 1000.37,
            "10 kΩ": 10064,
            "100 kΩ": 99619,
            "1 MΩ": 996470,
            "10 MΩ": 10000000
        }
        self.lockin_r_lockin_idx = tk.StringVar(value="1 MΩ")
        
        l = ttk.Label(self.lockin_frame, text="R_lockin")
        l.grid(column=0, row=row.i, sticky='w', pady=5)
        r_combo = ttk.Combobox(self.lockin_frame, textvariable=self.lockin_r_lockin_idx, 
                               values=list(resistor_values.keys()), width=13, state="readonly")
        r_combo.grid(column=1, row=row.i)
        self._register_tab_control("lockin", r_combo, enabled_state="readonly")
        r_unit = ttk.Label(self.lockin_frame, text="")
        r_unit.grid(column=2, row=row.i, sticky='w')
        
        def update_r_lockin(var, index, mode):
            display_label = self.lockin_r_lockin_idx.get()
            actual_value = resistor_values.get(display_label, 0.996e6)
            self.lockin_r_lockin.set(actual_value)
            r_unit.config(text="Ω")
        
        self.lockin_r_lockin_idx.trace_add('write', update_r_lockin)
        update_r_lockin(None, None, None)
        row.i += 1
        
        row("Averaging", self.lockin_averaging, "samples")

        # Set voltage based on current * R_lockin
        def update_voltage():
            current = self.lockin_output_current.get()
            r_lockin = self.lockin_r_lockin.get()
            voltage = current * r_lockin
            # Set excitation current using new API
            lockin.set_excitation_current(current, r_lockin)
            self.log_message(f"LockIn voltage set to {voltage:.6f} V")

        apply_button = ttk.Button(self.lockin_frame, text="Apply Settings", command=lambda: self.apply_lockin_settings(update_voltage))
        apply_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("lockin", apply_button)

        auto_gain_button = ttk.Button(self.lockin_frame, text="Auto Gain", command=self.lockin_auto_gain)
        auto_gain_button.grid(column=1, row=row.i, pady=10)
        self._register_tab_control("lockin", auto_gain_button)

        auto_phase_button = ttk.Button(self.lockin_frame, text="Auto Phase", command=self.lockin_auto_phase)
        auto_phase_button.grid(column=2, row=row.i, pady=10)
        self._register_tab_control("lockin", auto_phase_button)
        row.i += 1

        auto_reserve_button = ttk.Button(self.lockin_frame, text="Auto Reserve", command=self.lockin_auto_reserve)
        auto_reserve_button.grid(column=0, row=row.i, pady=5)
        self._register_tab_control("lockin", auto_reserve_button)

        measure_button = ttk.Button(self.lockin_frame, text="Measure", command=self.start_lockin_measure)
        measure_button.grid(column=1, row=row.i, pady=5)
        self._register_tab_control("lockin", measure_button)
        row.i += 1

        # Measurement results displays
        ttk.Label(self.lockin_frame, text="Measurements:", font=("Arial", 10, "bold")).grid(column=0, row=row.i, columnspan=3, sticky='w', pady=10)
        row.i += 1

        # X and Y displays
        ttk.Label(self.lockin_frame, text="X:").grid(column=0, row=row.i, sticky='w', pady=2)
        self.lockin_x_display = ttk.Label(self.lockin_frame, text="-- V", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_x_display.grid(column=1, row=row.i, padx=5, pady=2)

        ttk.Label(self.lockin_frame, text="Y:").grid(column=0, row=row.i+1, sticky='w', pady=2)
        self.lockin_y_display = ttk.Label(self.lockin_frame, text="-- V", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_y_display.grid(column=1, row=row.i+1, padx=5, pady=2)

        # R and Phase displays
        ttk.Label(self.lockin_frame, text="R:").grid(column=0, row=row.i+2, sticky='w', pady=2)
        self.lockin_r_display = ttk.Label(self.lockin_frame, text="-- V", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_r_display.grid(column=1, row=row.i+2, padx=5, pady=2)

        ttk.Label(self.lockin_frame, text="Phase:").grid(column=0, row=row.i+3, sticky='w', pady=2)
        self.lockin_phase_display = ttk.Label(self.lockin_frame, text="-- °", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_phase_display.grid(column=1, row=row.i+3, padx=5, pady=2)

        row.i += 4

        # Sample Resistance and Switch Channel indicators
        ttk.Label(self.lockin_frame, text="Sample Resistance:").grid(column=0, row=row.i, sticky='w', pady=5)
        self.lockin_sample_resistance_display = ttk.Label(self.lockin_frame, text="-- Ω", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_sample_resistance_display.grid(column=1, row=row.i, padx=5, pady=5)
        row.i += 1

        ttk.Label(self.lockin_frame, text="Switch Channel:").grid(column=0, row=row.i, sticky='w', pady=5)
        self.lockin_switch_channel_display = ttk.Label(self.lockin_frame, text="-- ", font=("Courier", 10), background="#f0f0f0", relief="sunken", width=15)
        self.lockin_switch_channel_display.grid(column=1, row=row.i, padx=5, pady=5)
        row.i += 1

        # Status display - fixed size text box
        ttk.Label(self.lockin_frame, text="Status:", font=("Arial", 10, "bold")).grid(column=0, row=row.i, columnspan=3, sticky='w', pady=(10, 5))
        row.i += 1
        self.lockin_status = tk.Text(self.lockin_frame, height=3, width=45, font=("Courier", 9), background="#f0f0f0", relief="sunken")
        self.lockin_status.grid(column=0, row=row.i, columnspan=3, pady=5, sticky='nsew')
        self.lockin_status.insert("1.0", "LockIn: Ready")
        self.lockin_status.config(state="disabled")  # Make read-only

    def apply_lockin_settings(self, update_voltage_func):
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected")
            return
        lockin.set_frequency(self.lockin_frequency.get())
        # Set time constant from dropdown index
        tau_idx = self.lockin_time_constant_idx.get()
        lockin.set_time_constant(tau_idx)
        # Filter slope: convert dB/oct string to index (6→0, 12→1, 18→2, 24→3)
        db_oct = int(self.lockin_filter_slope.get())
        filter_idx = self._db_to_filter_index(db_oct)
        lockin.set_filter_slope(filter_idx)
        # Sensitivity: use dropdown index
        sens_idx = self.lockin_sensitivity_idx.get()
        lockin.set_sensitivity(sens_idx)
        update_voltage_func()
        tau_val = lockin.TAU_TABLE[tau_idx]
        self._update_lockin_status(f"LockIn: Settings applied - Freq: {lockin.get_frequency():.1f}Hz, τ: {tau_val:.3g}s, Filter: {db_oct}dB/oct")

    def _update_lockin_status(self, message):
        """Thread-safe update of LockIn status text box"""
        self.root.after(50, self._do_update_lockin_status, message)
    
    def _do_update_lockin_status(self, message):
        """Internal method to update status - runs on main thread"""
        self.lockin_status.config(state="normal")
        self.lockin_status.delete("1.0", tk.END)
        self.lockin_status.insert("1.0", message)
        self.lockin_status.config(state="disabled")

    def _set_lockin_idle(self):
        self._update_lockin_status("LockIn: Idle")

    def lockin_auto_gain(self):
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected")
            return
        lockin.quick_autorange()
        sens_idx = lockin.get_sensitivity()
        self.lockin_sensitivity_idx.set(sens_idx)
        self._update_lockin_status(f"LockIn: Auto gain completed - Sensitivity: {lockin.SENS_TABLE[sens_idx]:.2e} V")

    def lockin_auto_phase(self):
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected")
            return
        lockin.safe_auto_phase()
        self._update_lockin_status("LockIn: Auto phase completed")

    def lockin_auto_reserve(self):
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected")
            return
        lockin.safe_auto_reserve()
        self._update_lockin_status("LockIn: Auto reserve completed")

    def start_lockin_measure(self):
        """Run lock-in measurement in a background thread to keep UI responsive."""
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected - cannot measure")
            return
        thread = threading.Thread(target=self.lockin_measure)
        thread.daemon = True
        thread.start()

    def lockin_measure(self, what=None, current=None, series_resistance=None, avg=None, start_sens=None, use_autorange=True, use_autophase=True, sample_delay=None, skip_write=False):
        """
        Measure lock-in signal (X, Y, R, Theta) with optional parameters.
        
        Parameters
        ----------
        what : tuple of str, optional
            Channels to read: "X", "Y", "R", "Theta". Default: all four.
        current : float, optional
            Excitation current (A). If None, uses GUI value (lockin_output_current).
        series_resistance : float, optional
            Series resistance (Ω). If None, uses GUI value (lockin_r_lockin).
        avg : int, optional
            Number of readings to average. Default: 10.
        start_sens : int, optional
            Starting sensitivity index (0-26). Default: 10.
        use_autorange : bool, optional
            Enable autorange. Default: True.
        use_autophase : bool, optional
            Enable autophase. Default: True.
        sample_delay : float, optional
            Delay between samples (s). Default: 0.05.
        skip_write : bool, optional
            If True, don't write data row to CSV (used by full_measure to combine with Hall data).
        
        Returns
        -------
        dict or None
            Measurement results if successful, None otherwise
        """
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected - cannot measure")
            return None
        
        try:
            # Capture START values of PPMS and Helmholtz parameters
            start_temp = self.current_temp
            start_field = self.current_inplane_field
            start_helmholtz_current = self.current_helmholtz_current
            start_helmholtz_field = self.current_helmholtz_field
            
            self._update_lockin_status("LockIn: Measuring...")
            # Resolve parameters with GUI defaults
            if what is None:
                what = ("X", "Y", "R", "Theta")
            
            if current is None:
                current = self.lockin_output_current.get()
            
            if series_resistance is None:
                series_resistance = self.lockin_r_lockin.get()
            
            if avg is None:
                avg = self.lockin_averaging.get()
            
            if start_sens is None:
                start_sens = 10
                       
            if sample_delay is None:
                sample_delay = 0.05
            
            # Set time constant and filter from GUI dropdown values
            tau_idx = self.lockin_time_constant_idx.get()
            lockin.set_time_constant(tau_idx)
            
            db_oct = int(self.lockin_filter_slope.get())
            filter_idx = self._db_to_filter_index(db_oct)
            lockin.set_filter_slope(filter_idx)
            
            # Turn on LockIn LED
            self.root.after(50, lambda: self.led_on("lockin"))
            
            # Use New_LockIn.measure() function for full measurement
            result = lockin.measure(
                what=what,
                current=current,
                series_resistance=series_resistance,
                avg=avg,
                start_sens=start_sens,
                use_autorange=use_autorange,
                use_autophase=use_autophase,
                sample_delay=sample_delay
            )
            
            # Turn off LockIn LED
            self.root.after(50, lambda: self.led_off("lockin"))
            
            # Capture END values of PPMS and Helmholtz parameters
            end_temp = self.current_temp
            end_field = self.current_inplane_field
            end_helmholtz_current = self.current_helmholtz_current
            end_helmholtz_field = self.current_helmholtz_field
            
            # Calculate averaged values
            avg_temp = (start_temp + end_temp) / 2.0 if (start_temp is not None and end_temp is not None) else np.nan
            avg_field = (start_field + end_field) / 2.0 if (start_field is not None and end_field is not None) else np.nan
            avg_helmholtz_current = (start_helmholtz_current + end_helmholtz_current) / 2.0 if (start_helmholtz_current is not None and end_helmholtz_current is not None) else np.nan
            avg_helmholtz_field = (start_helmholtz_field + end_helmholtz_field) / 2.0 if (start_helmholtz_field is not None and end_helmholtz_field is not None) else np.nan
            
            # Extract mean values (use NaN for values not measured)
            x = result.get("X", {}).get("mean", np.nan)
            y = result.get("Y", {}).get("mean", np.nan)
            r = result.get("R", {}).get("mean", np.nan)
            phase = result.get("Theta", {}).get("mean", np.nan)
            sens_idx = result.get("sens_idx", 10)

            # Sync GUI sensitivity with the actual lock-in setting
            self.root.after(50, lambda idx=sens_idx: self.lockin_sensitivity_idx.set(idx))
            
            # Update displays (only for measured values)
            if "X" in result:
                self.root.after(50, lambda val=x: self.lockin_x_display.config(text=f"{val:.6e} V"))
            if "Y" in result:
                self.root.after(50, lambda val=y: self.lockin_y_display.config(text=f"{val:.6e} V"))
            if "R" in result:
                self.root.after(50, lambda val=r: self.lockin_r_display.config(text=f"{val:.6e} V"))
            if "Theta" in result:
                self.root.after(50, lambda val=phase: self.lockin_phase_display.config(text=f"{val:.2f} °"))
            
            self._update_lockin_status("LockIn: Measurement completed")
            self.root.after(1000, self._set_lockin_idle)
            
            # Extract error/std values from result dict
            x_std = result.get("X", {}).get("std", np.nan)
            y_std = result.get("Y", {}).get("std", np.nan)
            r_std = result.get("R", {}).get("std", np.nan)
            theta_std = result.get("Theta", {}).get("std", np.nan)
            
            # Calculate output voltage and sample resistance for the active channel
            output_voltage = current * series_resistance
            if not np.isnan(r) and current != 0:
                sample_resistance = r / current
                # Error propagation: R_sample = R / I, so error = R_error / I
                sample_resistance_std = r_std / current if not np.isnan(r_std) else np.nan
                self.root.after(50, lambda val=sample_resistance: self.lockin_sample_resistance_display.config(text=f"{val:.3e} Ω"))
            else:
                sample_resistance = np.nan
                sample_resistance_std = np.nan
                self.root.after(50, lambda: self.lockin_sample_resistance_display.config(text="-- Ω"))
            
            # Set measurement start time if not set
            if self.measurement_start_time is None:
                self.measurement_start_time = time.time()
            
            # Calculate relative time with offset for appended files
            relative_time = (time.time() - self.measurement_start_time) + self.time_offset
            
            # Determine which channel is active based on closed channels
            active_channel = None
            if self.active_channel in self.channel_configs:
                config = self.channel_configs[self.active_channel]
                if all(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"]):
                    active_channel = self.active_channel
            if active_channel is None:
                for ch in self.channels:
                    config = self.channel_configs[ch]
                    if all(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"]):
                        active_channel = ch
                        break
            
            # Update switch channel display
            if active_channel:
                self.root.after(50, lambda ch=active_channel: self.lockin_switch_channel_display.config(text=f"Channel {ch.upper()}"))
            else:
                self.root.after(50, lambda: self.lockin_switch_channel_display.config(text="No channel active"))
            
            # Initialize sample resistance keys
            sample_a_resistance = np.nan
            sample_a_resistance_error = np.nan
            sample_b_resistance = np.nan
            sample_b_resistance_error = np.nan
            
            # Assign sample resistance to the correct channel
            if active_channel == 'a':
                sample_a_resistance = sample_resistance
                sample_a_resistance_error = sample_resistance_std
            elif active_channel == 'b':
                sample_b_resistance = sample_resistance
                sample_b_resistance_error = sample_resistance_std
            
            # Record data with all lock-in parameters and settings
            tau_idx = self.lockin_time_constant_idx.get()
            tau_value = lockin.TAU_TABLE[tau_idx]
            
            # Create channel-specific keys for Lock-in data and error values
            # Store data under either LockIn_X_a/Y_a/R_a/Theta_a or LockIn_X_b/Y_b/R_b/Theta_b
            if active_channel == 'a':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_a", "LockIn_Y_a", "LockIn_R_a", "LockIn_Theta_a"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_a_Error", "LockIn_Y_a_Error", "LockIn_R_a_Error", "LockIn_Theta_a_Error"
            elif active_channel == 'b':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_b", "LockIn_Y_b", "LockIn_R_b", "LockIn_Theta_b"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_b_Error", "LockIn_Y_b_Error", "LockIn_R_b_Error", "LockIn_Theta_b_Error"
            else:
                # No active channel detected - store as neither
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = None, None, None, None
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = None, None, None, None
            
            data_point = {
                "Time": relative_time,
                "LockIn_Frequency": self.lockin_frequency.get(),
                "LockIn_Sensitivity": lockin.SENS_TABLE[sens_idx],
                "LockIn_R_lockin": series_resistance,
                "LockIn_Output_Voltage": output_voltage,
                "LockIn_Output_Current": current,
                "LockIn_Time_Constant": tau_value,
                "Sample_a_Resistance": sample_a_resistance,
                "Sample_a_Resistance_Error": sample_a_resistance_error,
                "Sample_b_Resistance": sample_b_resistance,
                "Sample_b_Resistance_Error": sample_b_resistance_error,
                "Helmholtz_Current": avg_helmholtz_current,
                "Helmholtz_Field": avg_helmholtz_field,
                "Temp": avg_temp,
                "In-plane_Field": avg_field,
            }
            
            # Add channel-specific Lock-in data and error values if a channel is active
            if lockin_x_key:
                data_point[lockin_x_key] = x
                data_point[lockin_y_key] = y
                data_point[lockin_r_key] = r
                data_point[lockin_theta_key] = phase
                data_point[lockin_x_err_key] = x_std
                data_point[lockin_y_err_key] = y_std
                data_point[lockin_r_err_key] = r_std
                data_point[lockin_theta_err_key] = theta_std
            
            self.results_data.append(data_point)
            # CRITICAL FIX: Trim unbounded list to prevent memory leak (keep last 5000 entries)
            if len(self.results_data) > 5000:
                self.results_data = self.results_data[-5000:]
            
            if not skip_write:
                self.write_data_row(data_point, measurement_type="LockIn")
            self.log_message(f"[{time.strftime('%H:%M:%S')}] LockIn measurement saved to results")
            
            return result
        except Exception as e:
            self._update_lockin_status(f"LockIn: Measurement error - {e}")
            self.log_message(f"Error in lockin_measure: {e}")
            return None

    def lockin_continuous_measure(self, what=None, avg=None, sample_delay=None, excitation=None, skip_write=False):
        """
        Continuous lock-in measurement without settling or auto adjustments.

        Does not change sensitivity or excitation current. Optionally toggles
        excitation on/off without changing amplitude.

        Parameters
        ----------
        what : tuple of str, optional
            Channels to read: "X", "Y", "R", "Theta". Default: all four.
        avg : int, optional
            Number of readings to average. Default: GUI value.
        sample_delay : float, optional
            Delay between samples (s). Default: 0.05.
        excitation : str, optional
            One of "on", "off", or "keep". Default: keep.
        skip_write : bool, optional
            If True, don't write data row to CSV.

        Returns
        -------
        dict or None
            Measurement results if successful, None otherwise
        """
        if not self.instrument_connected.get("lockin", False) or lockin is None:
            self.log_message("ERROR: Lock-in SR830 not connected - cannot measure")
            return None

        try:
            # Capture START values of PPMS and Helmholtz parameters
            start_temp = self.current_temp
            start_field = self.current_inplane_field
            start_helmholtz_current = self.current_helmholtz_current
            start_helmholtz_field = self.current_helmholtz_field

            self._update_lockin_status("LockIn: Measuring (continuous)...")

            if what is None:
                what = ("X", "Y", "R", "Theta")

            if avg is None:
                avg = self.lockin_averaging.get()

            if sample_delay is None:
                sample_delay = 0.05

            if avg < 1:
                raise ValueError("avg must be >= 1")

            if excitation is not None:
                exc = excitation.lower()
                if exc == "on":
                    try:
                        amplitude = lockin.get_reference_amplitude()
                    except Exception:
                        amplitude = self.lockin_output_current.get() * self.lockin_r_lockin.get()
                    lockin.sine_output_on(amplitude)
                elif exc == "off":
                    lockin.sine_output_off()
                elif exc == "keep":
                    pass
                else:
                    raise ValueError("excitation must be on, off, or keep")

            # Turn on LockIn LED
            self.root.after(0, lambda: self.led_on("lockin"))

            ch_map = {"X": 1, "Y": 2, "R": 3, "Theta": 4}
            for key in what:
                if key not in ch_map:
                    raise ValueError(f"Unknown channel '{key}'. Valid: {list(ch_map.keys())}")

            data = {k: [] for k in what}
            for _ in range(avg):
                vals = lockin.snap(*[ch_map[k] for k in what])
                for k, v in zip(what, vals):
                    data[k].append(v)
                if sample_delay > 0:
                    time.sleep(sample_delay)

            # Turn off LockIn LED
            self.root.after(50, lambda: self.led_off("lockin"))

            # Capture END values of PPMS and Helmholtz parameters
            end_temp = self.current_temp
            end_field = self.current_inplane_field
            end_helmholtz_current = self.current_helmholtz_current
            end_helmholtz_field = self.current_helmholtz_field

            # Calculate averaged values
            avg_temp = (start_temp + end_temp) / 2.0 if (start_temp is not None and end_temp is not None) else np.nan
            avg_field = (start_field + end_field) / 2.0 if (start_field is not None and end_field is not None) else np.nan
            avg_helmholtz_current = (start_helmholtz_current + end_helmholtz_current) / 2.0 if (start_helmholtz_current is not None and end_helmholtz_current is not None) else np.nan
            avg_helmholtz_field = (start_helmholtz_field + end_helmholtz_field) / 2.0 if (start_helmholtz_field is not None and end_helmholtz_field is not None) else np.nan

            x = float(np.mean(data.get("X", [np.nan])))
            y = float(np.mean(data.get("Y", [np.nan])))
            r = float(np.mean(data.get("R", [np.nan])))
            phase = float(np.mean(data.get("Theta", [np.nan])))

            x_std = float(np.std(data.get("X", [np.nan])))
            y_std = float(np.std(data.get("Y", [np.nan])))
            r_std = float(np.std(data.get("R", [np.nan])))
            theta_std = float(np.std(data.get("Theta", [np.nan])))

            sens_idx = lockin.get_sensitivity()
            self.root.after(50, lambda idx=sens_idx: self.lockin_sensitivity_idx.set(idx))

            # Update displays (only for measured values)
            if "X" in data:
                self.root.after(50, lambda val=x: self.lockin_x_display.config(text=f"{val:.6e} V"))
            if "Y" in data:
                self.root.after(50, lambda val=y: self.lockin_y_display.config(text=f"{val:.6e} V"))
            if "R" in data:
                self.root.after(50, lambda val=r: self.lockin_r_display.config(text=f"{val:.6e} V"))
            if "Theta" in data:
                self.root.after(0, lambda val=phase: self.lockin_phase_display.config(text=f"{val:.2f} °"))

            self._update_lockin_status("LockIn: Continuous measurement completed")
            self.root.after(1000, self._set_lockin_idle)

            series_resistance = self.lockin_r_lockin.get()
            try:
                output_voltage = lockin.get_reference_amplitude()
            except Exception:
                output_voltage = self.lockin_output_current.get() * series_resistance
            output_current = output_voltage / series_resistance if series_resistance > 0 else np.nan

            if not np.isnan(r) and not np.isnan(output_current) and output_current != 0:
                sample_resistance = r / output_current
                sample_resistance_std = r_std / output_current
                if not np.isnan(sample_resistance):
                    self.root.after(0, lambda val=sample_resistance: self.lockin_sample_resistance_display.config(text=f"{val:.3e} Ω"))
            else:
                sample_resistance = np.nan
                sample_resistance_std = np.nan
                self.root.after(0, lambda: self.lockin_sample_resistance_display.config(text="-- Ω"))

            if self.measurement_start_time is None:
                self.measurement_start_time = time.time()

            relative_time = (time.time() - self.measurement_start_time) + self.time_offset

            active_channel = None
            if self.active_channel in self.channel_configs:
                config = self.channel_configs[self.active_channel]
                if all(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"]):
                    active_channel = self.active_channel
            if active_channel is None:
                for ch in self.channels:
                    config = self.channel_configs[ch]
                    if all(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"]):
                        active_channel = ch
                        break

            if active_channel:
                self.root.after(0, lambda ch=active_channel: self.lockin_switch_channel_display.config(text=f"Channel {ch.upper()}"))
            else:
                self.root.after(0, lambda: self.lockin_switch_channel_display.config(text="No channel active"))

            sample_a_resistance = np.nan
            sample_a_resistance_error = np.nan
            sample_b_resistance = np.nan
            sample_b_resistance_error = np.nan

            if active_channel == 'a':
                sample_a_resistance = sample_resistance
                sample_a_resistance_error = sample_resistance_std
            elif active_channel == 'b':
                sample_b_resistance = sample_resistance
                sample_b_resistance_error = sample_resistance_std

            tau_idx = self.lockin_time_constant_idx.get()
            tau_value = lockin.TAU_TABLE[tau_idx]

            if active_channel == 'a':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_a", "LockIn_Y_a", "LockIn_R_a", "LockIn_Theta_a"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_a_Error", "LockIn_Y_a_Error", "LockIn_R_a_Error", "LockIn_Theta_a_Error"
            elif active_channel == 'b':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_b", "LockIn_Y_b", "LockIn_R_b", "LockIn_Theta_b"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_b_Error", "LockIn_Y_b_Error", "LockIn_R_b_Error", "LockIn_Theta_b_Error"
            else:
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = None, None, None, None
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = None, None, None, None

            data_point = {
                "Time": relative_time,
                "LockIn_Frequency": self.lockin_frequency.get(),
                "LockIn_Sensitivity": lockin.SENS_TABLE[sens_idx],
                "LockIn_R_lockin": series_resistance,
                "LockIn_Output_Voltage": output_voltage,
                "LockIn_Output_Current": output_current,
                "LockIn_Time_Constant": tau_value,
                "Sample_a_Resistance": sample_a_resistance,
                "Sample_a_Resistance_Error": sample_a_resistance_error,
                "Sample_b_Resistance": sample_b_resistance,
                "Sample_b_Resistance_Error": sample_b_resistance_error,
                "Helmholtz_Current": avg_helmholtz_current,
                "Helmholtz_Field": avg_helmholtz_field,
                "Temp": avg_temp,
                "In-plane_Field": avg_field,
            }

            if lockin_x_key:
                data_point[lockin_x_key] = x
                data_point[lockin_y_key] = y
                data_point[lockin_r_key] = r
                data_point[lockin_theta_key] = phase
                data_point[lockin_x_err_key] = x_std
                data_point[lockin_y_err_key] = y_std
                data_point[lockin_r_err_key] = r_std
                data_point[lockin_theta_err_key] = theta_std

            self.results_data.append(data_point)
            # CRITICAL FIX: Trim unbounded list to prevent memory leak (keep last 5000 entries)
            if len(self.results_data) > 5000:
                self.results_data = self.results_data[-5000:]
            
            if not skip_write:
                self.write_data_row(data_point, measurement_type="LockIn - Continuous")
            self.log_message(f"[{time.strftime('%H:%M:%S')}] LockIn continuous measurement saved to results")

            return {
                k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
                for k, v in data.items()
            } | {"sens_idx": sens_idx}
        except Exception as e:
            self._update_lockin_status(f"LockIn: Measurement error - {e}")
            self.log_message(f"Error in lockin_continuous_measure: {e}")
            return None

    # ------------------------------
    # UI: Hall bar tab (Keithley 2450)
    # ------------------------------
    def create_keithley2450_widgets(self):
        self._create_connection_header(self.keithley2450_tab, "Hall Bar (K2450)", "hall", columnspan=3)

        self.keithley2450_frame = ttk.Frame(self.keithley2450_tab, padding=10)
        self.keithley2450_frame.grid(row=1, column=0, columnspan=3, sticky="nsew")

        def row(frame, label, var, unit):
            l = ttk.Label(frame, text=label)
            l.grid(column=0, row=row.i, sticky='w', pady=5)
            e = ttk.Entry(frame, textvariable=var, width=10)
            e.grid(column=1, row=row.i)
            u = ttk.Label(frame, text=unit)
            u.grid(column=2, row=row.i, sticky='w')
            self._register_tab_control("hall", e)
            row.i += 1
        row.i = 0

        self.k2450_current = tk.DoubleVar(value=2.0)  # mA
        self.k2450_nplc = tk.IntVar(value=5)
        self.k2450_compliance_v = tk.DoubleVar(value=2)  # V
        self.k2450_voltage_range = tk.StringVar(value="auto")  # or number
        self.k2450_filter_count = tk.IntVar(value=10)
        self.k2450_tbm = tk.DoubleVar(value=0.05)  # s - time before measurement (sleep after enable)
        self.k2450_hall_offset = tk.DoubleVar(value=0.0)  # V
        self.k2450_hall_v2gauss = tk.DoubleVar(value=10000/215)  # G/V

        row(self.keithley2450_frame, "Current", self.k2450_current, "mA")
        row(self.keithley2450_frame, "NPLC", self.k2450_nplc, "")
        row(self.keithley2450_frame, "Compliance V", self.k2450_compliance_v, "V")

        ttk.Label(self.keithley2450_frame, text="Voltage Range").grid(column=0, row=row.i, sticky='w', pady=5)
        range_entry = ttk.Entry(self.keithley2450_frame, textvariable=self.k2450_voltage_range, width=10)
        range_entry.grid(column=1, row=row.i)
        self._register_tab_control("hall", range_entry)
        ttk.Label(self.keithley2450_frame, text="(V or 'auto')").grid(column=2, row=row.i, sticky='w')
        row.i += 1

        row(self.keithley2450_frame, "Filter Count", self.k2450_filter_count, "")
        row(self.keithley2450_frame, "Time Before Meas", self.k2450_tbm, "s")

        ttk.Separator(self.keithley2450_frame, orient='horizontal').grid(column=0, row=row.i, columnspan=3, sticky='ew', pady=10)
        row.i += 1

        row(self.keithley2450_frame, "Hall Offset", self.k2450_hall_offset, "V")
        row(self.keithley2450_frame, "Hall V2Gauss", self.k2450_hall_v2gauss, "G/V")

        measure_button = ttk.Button(self.keithley2450_frame, text="Measure", command=self.start_measure_k2450)
        measure_button.grid(column=0, row=row.i, pady=10)
        self._register_tab_control("hall", measure_button)
        row.i += 1

        self.k2450_result = tk.Label(self.keithley2450_frame, text="Voltage: -- V, Field: -- G", font=("Courier", 14), fg="#00FF00", bg="#000000")
        self.k2450_result.grid(column=0, row=row.i, columnspan=3, pady=5, sticky="w")
        row.i += 1

    def start_measure_k2450(self):
        """Run Hall measurement in a background thread to keep UI responsive."""
        if not self.instrument_connected.get("hall", False) or keithley2450 is None:
            self.log_message("ERROR: Keithley 2450 not connected - cannot measure")
            return
        thread = threading.Thread(target=self.measure_k2450)
        thread.daemon = True
        thread.start()

    # ------------------------------
    # Measurements and instrument actions
    # ------------------------------
    def measure_k2450(self, current=None, nplc=None, compliance_v=None, voltage_range=None, filter_count=None, tbm=None, skip_write=False):
        """
        Measure Hall voltage using Keithley 2450 with software averaging.
        
        Parameters
        ----------
        current : float, optional
            Source current in mA. If None, uses GUI value (self.k2450_current).
        nplc : int, optional
            Number of power line cycles. If None, uses GUI value.
        compliance_v : float, optional
            Compliance voltage in V. If None, uses GUI value.
        voltage_range : str or float, optional
            Voltage range: "auto", or float value. If None, uses GUI value.
        filter_count : int, optional
            Number of measurement repetitions for software averaging. If None, uses GUI value.
        tbm : float, optional
            Time before measurement in seconds (sleep after enabling source). If None, uses GUI value.
        skip_write : bool, optional
            If True, don't write data row to CSV (used by full_measure to combine with LockIn data).
        
        Returns
        -------
        tuple or None
            (voltage, hall_field, voltage_std, hall_field_std) if successful, None otherwise
        """
        if not self.instrument_connected.get("hall", False) or keithley2450 is None:
            self.log_message("ERROR: Keithley 2450 not connected - cannot measure")
            return None
        
        try:
            # Capture START values of PPMS and Helmholtz parameters
            start_temp = self.current_temp
            start_field = self.current_inplane_field
            start_helmholtz_current = self.current_helmholtz_current
            start_helmholtz_field = self.current_helmholtz_field
            
            # Resolve parameters: use provided values or fall back to GUI defaults
            if current is None:
                current_ma = self.k2450_current.get()  # GUI value is in mA
            else:
                current_ma = current  # Expect mA from caller
            
            if nplc is None:
                nplc = self.k2450_nplc.get()
            
            if compliance_v is None:
                compliance_v = self.k2450_compliance_v.get()
            
            if voltage_range is None:
                voltage_range_str = self.k2450_voltage_range.get()
            else:
                voltage_range_str = str(voltage_range)
            
            if filter_count is None:
                filter_count = self.k2450_filter_count.get()
            
            if tbm is None:
                tbm = self.k2450_tbm.get()
            
            # Parse voltage range
            if voltage_range_str.lower() == "auto":
                voltage_range = None
                auto_range = True
            else:
                try:
                    voltage_range = float(voltage_range_str)
                    auto_range = False
                except ValueError:
                    voltage_range = None
                    auto_range = True
            
            hall_offset = self.k2450_hall_offset.get()
            hall_v2gauss = self.k2450_hall_v2gauss.get()

            # Turn on Hall LED
            self.root.after(0, lambda: self.led_on("hall"))
            
            keithley2450.source_current = current_ma
            keithley2450.apply_current(compliance_voltage=compliance_v)
            # Don't use hardware filter, use filter_count for number of repetitions
            keithley2450.voltage_filter_count(1)  # Disable hardware filter
            keithley2450.enable_source()
            # Sleep for tbm seconds before measurement to allow settling
            if tbm > 0:
                self.log_message(f"Waiting {tbm}s before Hall measurement (TBM)")
                time.sleep(tbm)
            # Measure with software averaging
            voltage, voltage_std = keithley2450.measure_voltage(nplc=nplc, voltage=voltage_range if not auto_range else 21.0, auto_range=auto_range, repetitions=filter_count)
            self.root.after(0, lambda: self.led_off("hall"))
            keithley2450.disable_source()
            
            hall_field = (voltage - hall_offset) * hall_v2gauss
            # Calculate field error from voltage error using error propagation
            hall_field_std = voltage_std * hall_v2gauss
            self.root.after(
                0,
                lambda v=voltage, vstd=voltage_std, hf=hall_field, hfstd=hall_field_std: self.k2450_result.config(
                    text=f"Voltage: {v:.6f}±{vstd:.6f} V, Field: {hf:.2f}±{hfstd:.2f} G"
                )
            )
            
            # Capture END values of PPMS and Helmholtz parameters
            end_temp = self.current_temp
            end_field = self.current_inplane_field
            end_helmholtz_current = self.current_helmholtz_current
            end_helmholtz_field = self.current_helmholtz_field
            
            # Calculate averaged values
            avg_temp = (start_temp + end_temp) / 2.0 if (start_temp is not None and end_temp is not None) else np.nan
            avg_field = (start_field + end_field) / 2.0 if (start_field is not None and end_field is not None) else np.nan
            avg_helmholtz_current = (start_helmholtz_current + end_helmholtz_current) / 2.0 if (start_helmholtz_current is not None and end_helmholtz_current is not None) else np.nan
            avg_helmholtz_field = (start_helmholtz_field + end_helmholtz_field) / 2.0 if (start_helmholtz_field is not None and end_helmholtz_field is not None) else np.nan
            
            # Set measurement start time if not set
            if self.measurement_start_time is None:
                self.measurement_start_time = time.time()
            
            # Calculate relative time with offset for appended files
            relative_time = (time.time() - self.measurement_start_time) + self.time_offset
            
            # Record data
            # Determine which channel is active based on closed channels
            active_channel = None
            if switch is not None and self.instrument_connected.get("switch", False):
                for ch in self.channels:
                    config = self.channel_configs[ch]
                    if any(str(config[line].get()) in switch.closed_channels for line in ["I+", "V+", "V-", "I-"]):
                        active_channel = ch
                        break
            
            data_point = {
                "Time": relative_time,
                "Hall Voltage": voltage,
                "Hall Voltage Error": voltage_std,
                "Hall Field": hall_field,
                "Hall Field Error": hall_field_std,
                "Meas Current": current_ma,
                "Helmholtz_Current": avg_helmholtz_current,
                "Helmholtz_Field": avg_helmholtz_field,
                "Temp": avg_temp,
                "In-plane_Field": avg_field
            }
            self.results_data.append(data_point)
            # CRITICAL FIX: Trim unbounded list to prevent memory leak (keep last 5000 entries)
            if len(self.results_data) > 5000:
                self.results_data = self.results_data[-5000:]
            
            if not skip_write:
                self.write_data_row(data_point, measurement_type="Hall Bar")
            
            return (voltage, hall_field, voltage_std, hall_field_std)
        except Exception as e:
            self.root.after(50, lambda err=e: self.k2450_result.config(text=f"Error: {err}"))
            self.log_message(f"Error in measure_k2450: {e}")
            return None

    # ------------------------------
    # Data file management
    # ------------------------------

    def initialize_data_file(self, directory=None, filename=None, append=False):
        """
        Create a new data file. By default uses auto-increment in Data_Route directory.
        
        Parameters
        ----------
        directory : str, optional
            Override default Data_Route directory. If None, uses self.data_file_dir.
            Updates self.data_file_dir for future calls.
        filename : str, optional
            Override auto-generated filename. If None, uses auto-increment logic.
            If specified and file exists, behavior depends on append parameter.
        append : bool, optional
            If True and filename exists, append to existing file.
            If False (default) and filename exists, create numbered variant.
        """
        try:
            # Ensure target_dir is a Path object
            if directory is not None:
                target_dir = Path(directory)
                self.data_file_dir = target_dir  # Update default for future calls
            else:
                target_dir = Path(self.data_file_dir)
            
            # Create directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine the filepath to use
            if filename is None:
                # Auto-increment: Data_YYYYMMDD_###.csv
                today = datetime.now().strftime("%Y%m%d")
                base_prefix = f"Data_{today}"
                counter = 0
                filepath = None
                while filepath is None:
                    counter += 1
                    candidate = target_dir / f"{base_prefix}_{counter:03d}.csv"
                    if not candidate.exists():
                        filepath = candidate
            else:
                # Use specified filename (ensure .csv extension)
                if not filename.lower().endswith(".csv"):
                    filename = filename + ".csv"
                filepath = target_dir / filename
                
                # If file exists, handle based on append flag
                if filepath.exists():
                    if append:
                        # Read last time value from existing file for time offset
                        last_time = 0.0
                        try:
                            with open(filepath, 'r', newline='', encoding='utf-8') as read_file:
                                reader = csv.DictReader(read_file)
                                rows = list(reader)
                                if rows:  # If file has data rows
                                    last_row = rows[-1]
                                    if "Time(s)" in last_row and last_row["Time(s)"]:
                                        try:
                                            last_time = float(last_row["Time(s)"])
                                            self.log_message(f"Last time entry: {last_time:.2f}s - continuing from this point")
                                        except (ValueError, TypeError):
                                            last_time = 0.0
                        except Exception as e:
                            self.log_message(f"Warning: Could not read last time value: {e}")
                            last_time = 0.0
                        
                        self.time_offset = last_time
                        
                        # Open existing file in append mode and return
                        self.data_filename = filepath
                        self.data_file = open(filepath, 'a', newline='', encoding='utf-8')
                        self.csv_writer = csv.DictWriter(self.data_file, fieldnames=[
                            "Time(s)", "Temp(K)", "Field(Oe)", 
                            "Helmholtz_Current(A)", "Helmholtz_Field(G)",
                            "Hall_Voltage(V)", "Hall_Voltage_Error(V)", "Hall_Field(G)", "Hall_Field_Error(G)",
                            "X_a(V)", "X_a_Error(V)", "Y_a(V)", "Y_a_Error(V)", "R_a(V)", "R_a_Error(V)", "Theta_a(deg)", "Theta_a_Error(deg)",
                            "X_b(V)", "X_b_Error(V)", "Y_b(V)", "Y_b_Error(V)", "R_b(V)", "R_b_Error(V)", "Theta_b(deg)", "Theta_b_Error(deg)",
                            "Frequency(Hz)", "Sensitivity(V)", "Resistor(Ohm)", 
                            "Output_Voltage(V)", "Output_Current(A)",
                            "Time_Constant(s)", "Sample_a_Resistance(Ohm)", "Sample_a_Resistance_Error(Ohm)", "Sample_b_Resistance(Ohm)", "Sample_b_Resistance_Error(Ohm)",
                            "Measurement_Type", "Notes"
                        ])
                        self.log_message(f"Appending to: {filepath}")
                        return filepath
                    else:
                        # Create numbered variant
                        base_name = filepath.stem
                        extension = filepath.suffix
                        counter = 0
                        while True:
                            counter += 1
                            new_filepath = target_dir / f"{base_name}_{counter:03d}{extension}"
                            if not new_filepath.exists():
                                filepath = new_filepath
                                break
            
            # Create new CSV file with header
            self.time_offset = 0.0  # Reset time offset for new files
            self.data_filename = filepath
            self.data_file = open(filepath, 'w', newline='', encoding='utf-8')
            
            fieldnames = [
                "Time(s)", "Temp(K)", "Field(Oe)", 
                "Helmholtz_Current(A)", "Helmholtz_Field(G)",
                "Hall_Voltage(V)", "Hall_Voltage_Error(V)", "Hall_Field(G)", "Hall_Field_Error(G)",
                "X_a(V)", "X_a_Error(V)", "Y_a(V)", "Y_a_Error(V)", "R_a(V)", "R_a_Error(V)", "Theta_a(deg)", "Theta_a_Error(deg)",
                "X_b(V)", "X_b_Error(V)", "Y_b(V)", "Y_b_Error(V)", "R_b(V)", "R_b_Error(V)", "Theta_b(deg)", "Theta_b_Error(deg)",
                "Frequency(Hz)", "Sensitivity(V)", "Resistor(Ohm)", 
                "Output_Voltage(V)", "Output_Current(A)",
                "Time_Constant(s)", "Sample_a_Resistance(Ohm)", "Sample_a_Resistance_Error(Ohm)", "Sample_b_Resistance(Ohm)", "Sample_b_Resistance_Error(Ohm)",
                "Measurement_Type", "Notes"
            ]
            
            with self._csv_lock:
                self.csv_writer = csv.DictWriter(self.data_file, fieldnames=fieldnames)
                self.csv_writer.writeheader()
                self.data_file.flush()
            
            # Reset Results tab graphs
            self.ax1.clear()
            self.ax2.clear()
            self.canvas.draw()
            
            self.log_message(f"Data file initialized: {filepath}")
            return filepath
        except Exception as e:
            self.log_message(f"Error initializing data file: {e}")
            return None

    def write_data_row(self, data_point, measurement_type="Full"):
        """
        Write a row of data to the CSV file. Handles NaN values appropriately.
        
        Parameters
        ----------
        data_point : dict
            Dictionary with measurement data
        measurement_type : str
            One of "Hall", "LockIn", or "Full"
        """
        if self.csv_writer is None:
            self.initialize_data_file()
        
        if self.csv_writer is None:
            return
        
        try:
            # Prepare row with NaN for missing values
            # Initialize all columns to NaN
            row = {
                "Time(s)": data_point.get("Time", np.nan),
                "Temp(K)": data_point.get("Temp", np.nan),
                "Field(Oe)": data_point.get("In-plane_Field", np.nan),
                "Helmholtz_Current(A)": data_point.get("Helmholtz_Current", np.nan),
                "Helmholtz_Field(G)": data_point.get("Helmholtz_Field", np.nan),
                "Hall_Voltage(V)": data_point.get("Hall Voltage", np.nan),
                "Hall_Voltage_Error(V)": data_point.get("Hall Voltage Error", np.nan),
                "Hall_Field(G)": data_point.get("Hall Field", np.nan),
                "Hall_Field_Error(G)": data_point.get("Hall Field Error", np.nan),
                # Channel A Lock-in data
                "X_a(V)": data_point.get("LockIn_X_a", np.nan),
                "X_a_Error(V)": data_point.get("LockIn_X_a_Error", np.nan),
                "Y_a(V)": data_point.get("LockIn_Y_a", np.nan),
                "Y_a_Error(V)": data_point.get("LockIn_Y_a_Error", np.nan),
                "R_a(V)": data_point.get("LockIn_R_a", np.nan),
                "R_a_Error(V)": data_point.get("LockIn_R_a_Error", np.nan),
                "Theta_a(deg)": data_point.get("LockIn_Theta_a", np.nan),
                "Theta_a_Error(deg)": data_point.get("LockIn_Theta_a_Error", np.nan),
                # Channel B Lock-in data
                "X_b(V)": data_point.get("LockIn_X_b", np.nan),
                "X_b_Error(V)": data_point.get("LockIn_X_b_Error", np.nan),
                "Y_b(V)": data_point.get("LockIn_Y_b", np.nan),
                "Y_b_Error(V)": data_point.get("LockIn_Y_b_Error", np.nan),
                "R_b(V)": data_point.get("LockIn_R_b", np.nan),
                "R_b_Error(V)": data_point.get("LockIn_R_b_Error", np.nan),
                "Theta_b(deg)": data_point.get("LockIn_Theta_b", np.nan),
                "Theta_b_Error(deg)": data_point.get("LockIn_Theta_b_Error", np.nan),
                # Settings (shared)
                "Frequency(Hz)": data_point.get("LockIn_Frequency", np.nan),
                "Sensitivity(V)": data_point.get("LockIn_Sensitivity", np.nan),
                "Resistor(Ohm)": data_point.get("LockIn_R_lockin", np.nan),
                "Output_Voltage(V)": data_point.get("LockIn_Output_Voltage", np.nan),
                "Output_Current(A)": data_point.get("LockIn_Output_Current", np.nan),
                "Time_Constant(s)": data_point.get("LockIn_Time_Constant", np.nan),
                "Sample_a_Resistance(Ohm)": data_point.get("Sample_a_Resistance", np.nan),
                "Sample_a_Resistance_Error(Ohm)": data_point.get("Sample_a_Resistance_Error", np.nan),
                "Sample_b_Resistance(Ohm)": data_point.get("Sample_b_Resistance", np.nan),
                "Sample_b_Resistance_Error(Ohm)": data_point.get("Sample_b_Resistance_Error", np.nan),
                "Measurement_Type": measurement_type,
                "Notes": self.current_note
            }
            
            # Use lock to protect CSV write operations
            with self._csv_lock:
                if self.csv_writer is not None and self.data_file is not None:
                    self.csv_writer.writerow(row)
                    self.data_file.flush()
            self.current_note = ""  # Clear note after writing
            
            # Auto-update Results tab graphs
            self._schedule_results_plot_update()
        except Exception as e:
            self.log_message(f"Error writing data row: {e}")


    def correct_hall_field(self, target_G, tolerance=0.01, max_iter=10):
        """
        Iteratively correct Helmholtz current to achieve target Hall field.
        
        Parameters
        ----------
        target_G : float
            Target Hall field in Gauss
        tolerance : float
            Tolerance as fraction of target (default 0.01 = 1%)
        max_iter : int
            Maximum number of iterations (default 10)
            
        Returns
        -------
        bool
            True if target achieved, False if max iterations reached
        """
        helmholtz_cal = 2 * 341.71  # 2 coils × 341.71 G/A = 683.42 G/A
        
        for iteration in range(max_iter):
            # Measure current Hall field
            try:
                current_ma = self.k2450_current.get()  # GUI value is in mA
                compliance_v = self.k2450_compliance_v.get()
                nplc = self.k2450_nplc.get()
                filter_count = self.k2450_filter_count.get()
                hall_offset = self.k2450_hall_offset.get()
                hall_v2gauss = self.k2450_hall_v2gauss.get()
                
                keithley2450.source_current = current_ma
                keithley2450.apply_current(compliance_voltage=compliance_v)
                # Don't use hardware filter, use filter_count for number of repetitions
                keithley2450.voltage_filter_count(1)  # Disable hardware filter
                keithley2450.enable_source()
                self.led_on("hall")  # Turn on Hall LED when source is enabled
                voltage, voltage_std = keithley2450.measure_voltage(nplc=nplc, voltage=21.0, auto_range=True, repetitions=filter_count)
                self.led_off("hall")  # Turn off Hall LED when measurement done
                keithley2450.disable_source()
                
                measured_hall_field = (voltage - hall_offset) * hall_v2gauss
                measured_hall_field_std = voltage_std * hall_v2gauss
                
                self.log_message(f"Hall field correction - Iteration {iteration+1}: Measured={measured_hall_field:.2f}±{measured_hall_field_std:.2f}G, Target={target_G:.2f}G")
                
                # Check if within tolerance
                error = abs(measured_hall_field - target_G)
                if error <= tolerance * abs(target_G):
                    self.log_message(f"Hall field correction SUCCESS: Achieved {measured_hall_field:.2f}G within tolerance")
                    return True
                
                # Calculate correction
                current_helmholtz = self.current_helmholtz_current
                correction_current = (target_G - measured_hall_field) / helmholtz_cal
                new_helmholtz_current = current_helmholtz + correction_current
                
                # Apply correction
                self.set_current.set(new_helmholtz_current)
                self.set_values()
                self.enable_output()
                
                # Wait for stabilization
                time.sleep(1.0)
                
            except Exception as e:
                self.log_message(f"Hall field correction error at iteration {iteration+1}: {e}")
                return False
        
        self.log_message(f"Hall field correction FAILED: Max iterations ({max_iter}) reached")
        return False

    def full_measure(self, channel, current=None, resistance=None, time_between=0.05, 
                     hall_current=None, hall_nplc=None, hall_compliance=None, hall_voltage_range=None, hall_filter=None, hall_tbm=None,
                     lockin_what=None, lockin_current=None, lockin_series_resistance=None, 
                     lockin_avg=None, lockin_start_sens=None, lockin_use_autorange=True, 
                     lockin_use_autophase=True, lockin_sample_delay=None):
        """
        Perform a full Hall + LockIn measurement in one operation.
        
        Steps:
        1. Measure Hall field with optional parameters
        2. Close specified channel
        3. Wait time_between
        4. Run LockIn measurement with optional parameters
        5. Open all channels
        6. Write single row with all data
        
        Parameters
        ----------
        channel : str
            Channel to close (a or b)
        current : float, optional
            Shortcut for lockin_current (backward compatibility). A rms.
        resistance : float, optional
            Shortcut for lockin_series_resistance (backward compatibility). Ω.
        time_between : float, optional
            Wait time between Hall and LockIn measurements (s). Default: 0.05.
        
        Hall measurement optional parameters (pass to measure_k2450):
        hall_current : float, optional
            Hall measurement current (mA). If None, uses GUI value.
        hall_nplc : int, optional
            Hall measurement NPLC. If None, uses GUI value.
        hall_compliance : float, optional
            Hall measurement compliance voltage (V). If None, uses GUI value.
        hall_voltage_range : str or float, optional
            Hall measurement voltage range. If None, uses GUI value.
        hall_filter : int, optional
            Hall measurement filter count. If None, uses GUI value.
        hall_tbm : float, optional
            Hall measurement time before measurement (s). Sleep between enabling current and measuring. If None, uses GUI value.
        
        LockIn measurement optional parameters (pass to lockin_measure):
        lockin_what : tuple of str, optional
            Channels to measure. Default: ("X", "Y", "R", "Theta").
        lockin_current : float, optional
            LockIn excitation current (A). If None, uses GUI value.
        lockin_series_resistance : float, optional
            LockIn series resistance (Ω). If None, uses GUI value.
        lockin_avg : int, optional
            Number of averages. Default: 10.
        lockin_start_sens : int, optional
            Starting sensitivity index. Default: 10.
        lockin_use_autorange : bool, optional
            Enable autorange. Default: True.
        lockin_use_autophase : bool, optional
            Enable autophase. Default: True.
        lockin_sample_delay : float, optional
            Delay between samples (s). Default: 0.02.
        """
        if self.measurement_start_time is None:
            self.measurement_start_time = time.time()
        
        try:
            # Calculate relative time with offset for appended files
            relative_time = (time.time() - self.measurement_start_time) + self.time_offset
            
            # Capture START values of PPMS and Helmholtz parameters
            start_temp = self.current_temp
            start_field = self.current_inplane_field
            start_helmholtz_current = self.current_helmholtz_current
            start_helmholtz_field = self.current_helmholtz_field
            
            # Handle backward compatibility: current/resistance map to lockin_current/lockin_series_resistance
            if lockin_current is None and current is not None:
                lockin_current = current
            if lockin_series_resistance is None and resistance is not None:
                lockin_series_resistance = resistance
            
            # 1. Measure Hall field (with optional parameters, skip writing to CSV)
            self.log_message(f"full_measure: Step 1 - Measuring Hall field")
            hall_result = self.measure_k2450(
                current=hall_current,
                nplc=hall_nplc,
                compliance_v=hall_compliance,
                voltage_range=hall_voltage_range,
                filter_count=hall_filter,
                tbm=hall_tbm,
                skip_write=True  # Don't write Hall data separately
            )
            
            if hall_result is None:
                self.log_message("full_measure ERROR: Hall measurement failed")
                return
            
            hall_voltage, hall_field, hall_voltage_std, hall_field_std = hall_result
            self.log_message(f"full_measure: Hall field = {hall_field:.2f}±{hall_field_std:.2f}G")
            
            # 2. Close channel
            self.log_message(f"full_measure: Step 2 - Closing channel {channel}")
            self.close_channel_var.set(channel)
            self.close_channel()
            
            # 3. Wait
            self.log_message(f"full_measure: Step 3 - Waiting {time_between}s")
            time.sleep(time_between)
            
            # 4. Run LockIn measurement (with optional parameters, skip writing to CSV)
            self.log_message(f"full_measure: Step 4 - Running LockIn measurement")
            result = self.lockin_measure(
                what=lockin_what,
                current=lockin_current,
                series_resistance=lockin_series_resistance,
                avg=lockin_avg,
                start_sens=lockin_start_sens,
                use_autorange=lockin_use_autorange,
                use_autophase=lockin_use_autophase,
                sample_delay=lockin_sample_delay,
                skip_write=True  # Don't write LockIn data separately
            )
            
            if result is None:
                self.log_message("full_measure ERROR: LockIn measurement failed")
                return
            
            # Extract values safely (use NaN for missing values)
            x_mean = result.get("X", {}).get("mean", np.nan)
            y_mean = result.get("Y", {}).get("mean", np.nan)
            r_mean = result.get("R", {}).get("mean", np.nan)
            theta_mean = result.get("Theta", {}).get("mean", np.nan)
            x_std = result.get("X", {}).get("std", np.nan)
            y_std = result.get("Y", {}).get("std", np.nan)
            r_std = result.get("R", {}).get("std", np.nan)
            theta_std = result.get("Theta", {}).get("std", np.nan)
            sens_idx = result.get("sens_idx", 10)
            
            # Resolve lockin parameters for data recording
            if lockin_current is None:
                lockin_current = self.lockin_output_current.get()
            if lockin_series_resistance is None:
                lockin_series_resistance = self.lockin_r_lockin.get()
            
            # 5. Open all channels
            self.log_message(f"full_measure: Step 5 - Opening all channels")
            self.open_all_channels()
            
            # Capture END values of PPMS and Helmholtz parameters
            end_temp = self.current_temp
            end_field = self.current_inplane_field
            end_helmholtz_current = self.current_helmholtz_current
            end_helmholtz_field = self.current_helmholtz_field
            
            # Calculate averaged values
            avg_temp = (start_temp + end_temp) / 2.0 if (start_temp is not None and end_temp is not None) else np.nan
            avg_field = (start_field + end_field) / 2.0 if (start_field is not None and end_field is not None) else np.nan
            avg_helmholtz_current = (start_helmholtz_current + end_helmholtz_current) / 2.0 if (start_helmholtz_current is not None and end_helmholtz_current is not None) else np.nan
            avg_helmholtz_field = (start_helmholtz_field + end_helmholtz_field) / 2.0 if (start_helmholtz_field is not None and end_helmholtz_field is not None) else np.nan
            
            # Calculate sample resistance (handle NaN case)
            if not np.isnan(r_mean) and lockin_current != 0:
                sample_resistance = r_mean / lockin_current
                # Error propagation: R_sample = R / I, so error = R_error / I
                sample_resistance_std = r_std / lockin_current if not np.isnan(r_std) else np.nan
            else:
                sample_resistance = np.nan
                sample_resistance_std = np.nan
            output_voltage = lockin_current * lockin_series_resistance
            
            # 6. Write single combined row with all Hall + LockIn data (channel-specific)
            # Create channel-specific keys for Lock-in data and error values
            if channel == 'a':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_a", "LockIn_Y_a", "LockIn_R_a", "LockIn_Theta_a"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_a_Error", "LockIn_Y_a_Error", "LockIn_R_a_Error", "LockIn_Theta_a_Error"
                sample_a_resistance = sample_resistance
                sample_a_resistance_error = sample_resistance_std
                sample_b_resistance = np.nan
                sample_b_resistance_error = np.nan
            elif channel == 'b':
                lockin_x_key, lockin_y_key, lockin_r_key, lockin_theta_key = "LockIn_X_b", "LockIn_Y_b", "LockIn_R_b", "LockIn_Theta_b"
                lockin_x_err_key, lockin_y_err_key, lockin_r_err_key, lockin_theta_err_key = "LockIn_X_b_Error", "LockIn_Y_b_Error", "LockIn_R_b_Error", "LockIn_Theta_b_Error"
                sample_a_resistance = np.nan
                sample_a_resistance_error = np.nan
                sample_b_resistance = sample_resistance
                sample_b_resistance_error = sample_resistance_std
            else:
                raise ValueError(f"Invalid channel: {channel}, must be 'a' or 'b'")
            
            data_point = {
                "Time": relative_time,
                "Hall Voltage": hall_voltage,
                "Hall Voltage Error": hall_voltage_std,
                "Hall Field": hall_field,
                "Hall Field Error": hall_field_std,
                "Meas Current": hall_current if hall_current is not None else self.k2450_current.get() * 1e-3,
                "Helmholtz_Current": avg_helmholtz_current,
                "Helmholtz_Field": avg_helmholtz_field,
                "Temp": avg_temp,
                "In-plane_Field": avg_field,
                lockin_x_key: x_mean,
                lockin_y_key: y_mean,
                lockin_r_key: r_mean,
                lockin_theta_key: theta_mean,
                lockin_x_err_key: x_std,
                lockin_y_err_key: y_std,
                lockin_r_err_key: r_std,
                lockin_theta_err_key: theta_std,
                "LockIn_Frequency": self.lockin_frequency.get(),
                "LockIn_Sensitivity": lockin.SENS_TABLE[sens_idx],
                "LockIn_R_lockin": lockin_series_resistance,
                "LockIn_Output_Voltage": output_voltage,
                "LockIn_Output_Current": lockin_current,
                "LockIn_Time_Constant": lockin.TAU_TABLE[self.lockin_time_constant_idx.get()],
                "Sample_a_Resistance": sample_a_resistance,
                "Sample_a_Resistance_Error": sample_a_resistance_error,
                "Sample_b_Resistance": sample_b_resistance,
                "Sample_b_Resistance_Error": sample_b_resistance_error
            }
            
            # Add combined data to results and write single row
            self.results_data.append(data_point)
            # CRITICAL FIX: Trim unbounded list to prevent memory leak (keep last 5000 entries)
            if len(self.results_data) > 5000:
                self.results_data = self.results_data[-5000:]
            
            self.write_data_row(data_point, measurement_type="Full Measure")
            
            self.log_message(f"full_measure: COMPLETE - Full measurement recorded (1 row with Hall + LockIn data)")
            
        except Exception as e:
            self.log_message(f"full_measure ERROR: {e}")

    def set_ppms_field_and_fix_hall(self, field_Oe, target_hall_G, helmholtz_rate=0.1):
        """
        Set PPMS field and automatically correct Helmholtz to fix Hall field.
        
        Steps:
        1. Use dyna.set_field() to set in-plane field
        2. Wait for PPMS status = "holding" (stable)
        3. Call correct_hall_field() to fix Hall field
        
        Parameters
        ----------
        field_Oe : float
            Target in-plane field in Oersteds
        target_hall_G : float
            Target Hall field in Gauss
        helmholtz_rate : float
            Helmholtz field ramp rate (G/s, default 0.1)
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("set_ppms_field_and_fix_hall ERROR: Dyna not connected")
            return
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("set_ppms_field_and_fix_hall ERROR: Helmholtz not connected")
            return
        if not self.instrument_connected.get("hall", False):
            self.log_message("set_ppms_field_and_fix_hall ERROR: Keithley 2450 not connected")
            return
        try:
            self.log_message(f"set_ppms_field_and_fix_hall: Setting PPMS field to {field_Oe}Oe")
            
            # Set PPMS field
            rate = 10.0  # Oe/s
            approach = dyna.Field_mode.no_overshoot
            self._dyna_call("set_field", field_Oe, rate, approach)
            
            # Wait for PPMS to stabilize
            self.log_message(f"set_ppms_field_and_fix_hall: Waiting for PPMS field to stabilize...")
            time.sleep(5.0)
            
            # Check PPMS status
            max_wait = 60  # seconds
            start_time = time.time()
            while time.time() - start_time < max_wait:
                try:
                    err, field, status_num = self._dyna_call("get_field")
                    # Status: 0=stable (holding), 1=warming, 2=cooling, etc.
                    if status_num == 0:
                        self.log_message(f"set_ppms_field_and_fix_hall: PPMS field stabilized at {field}Oe (status={status_num})")
                        break
                except:
                    pass
                time.sleep(1.0)
            
            # Now correct Hall field with Helmholtz
            self.log_message(f"set_ppms_field_and_fix_hall: Correcting Hall field to {target_hall_G}G")
            success = self.correct_hall_field(target_hall_G, tolerance=0.01, max_iter=10)
            
            if success:
                self.log_message(f"set_ppms_field_and_fix_hall: SUCCESS")
            else:
                self.log_message(f"set_ppms_field_and_fix_hall: PARTIAL (Hall field not fully corrected)")
                
        except Exception as e:
            self.log_message(f"set_ppms_field_and_fix_hall ERROR: {e}")

    def scan_ppms_field_and_fix_hall(self, start_Oe, end_Oe, step_Oe, target_hall_G, rate_Oes=10.0, loop_commands=None):
        """
        Scan PPMS field from start to end, correcting Hall field at each point.
        Optionally executes commands at each field point (e.g., measurements).
        
        Parameters
        ----------
        start_Oe : float
            Starting in-plane field (Oe)
        end_Oe : float
            Ending in-plane field (Oe)
        step_Oe : float
            Step size (Oe)
        target_hall_G : float
            Target Hall field at each step (G)
        rate_Oes : float
            PPMS field ramp rate (Oe/s). Default: 10.0
        loop_commands : list of str, optional
            List of script commands to execute at each field point.
            If None or empty, loop runs without executing commands at each step.
            Example: ["full_measure a", "full_measure b"]
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("scan_ppms_field_and_fix_hall ERROR: Dyna not connected")
            return
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("scan_ppms_field_and_fix_hall ERROR: Helmholtz not connected")
            return
        if not self.instrument_connected.get("hall", False):
            self.log_message("scan_ppms_field_and_fix_hall ERROR: Keithley 2450 not connected")
            return
        try:
            self.log_message(f"scan_ppms_field_and_fix_hall: Scanning {start_Oe} to {end_Oe}Oe, step {step_Oe}Oe")
            
            # Generate field points
            if start_Oe <= end_Oe:
                fields = np.arange(start_Oe, end_Oe + step_Oe/2, step_Oe)
            else:
                fields = np.arange(start_Oe, end_Oe - step_Oe/2, -step_Oe)
            
            for field_point in fields:
                if not self.script_running:
                    break
                
                self.log_message(f"scan_ppms_field_and_fix_hall: Stepping to {field_point}Oe")
                self.set_ppms_field_and_fix_hall(field_point, target_hall_G, rate_Oes)
                
                # Small stabilization delay
                time.sleep(0.5)
                
                # Execute loop commands if provided
                if loop_commands:
                    self.log_message(f"scan_ppms_field_and_fix_hall: Executing {len(loop_commands)} command(s) at {field_point}Oe")
                    self.execute_commands(loop_commands)
            
            self.log_message(f"scan_ppms_field_and_fix_hall: Complete")
            
        except Exception as e:
            self.log_message(f"scan_ppms_field_and_fix_hall ERROR: {e}")

    def sweep_dyna_field(self, start, end, rate, gap_time=0, loop_commands=None):
        """
        Sweep PPMS in-plane field continuously from start to end, executing loop commands repeatedly.
        
        Execution pattern:
        1. Set field to start and wait for stability
        2. Execute loop_commands ONCE (initial execution)
        3. Begin ramp to end at rate
        4. While ramping: Execute loop_commands repeatedly, wait gap_time between executions
        5. When stable at end: Execute loop_commands ONCE more (final execution)
        
        Parameters
        ----------
        start : float
            Starting field in Oersteds (float)
        end : float
            Ending field in Oersteds (float)
        rate : float
            Field ramp rate in Oe/s (float)
        gap_time : float, optional
            Wait time between loop executions in seconds (default: 0, no delay)
        loop_commands : list of str, optional
            List of script commands to execute during sweep
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        
        self.log_message(f"Sweeping Dyna field: {start} to {end} Oe at {rate} Oe/s, gap_time={gap_time}s")
        
        try:
            # Step 1: Set to start and wait for stability
            self.log_message(f"Setting field to start value {start} Oe")
            approach_enum = self._get_field_approach_enum("linear")
            self._dyna_call("set_field", start, rate, approach_enum)
            self.current_inplane_field = start
            
            # Wait for start to stabilize
            max_wait = 300
            start_time = time.time()
            stable_count = 0
            
            while time.time() - start_time < max_wait and stable_count < 2:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                try:
                    err, current_field, status_num = self._dyna_call("get_field")
                    status = int(status_num)
                    if status == 4 or status == 1:
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"Start value {start} Oe stabilized")
                            break
                    else:
                        stable_count = 0
                    time.sleep(1.0)
                except Exception as e:
                    self.log_message(f"Warning: Could not check field stability: {e}")
                    break
            
            # Step 2: Execute commands ONCE after initial stabilization
            if loop_commands:
                self.log_message(f"Initial execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            # Step 3: Begin ramp to end
            self.log_message(f"Beginning ramp to end value {end} Oe")
            self._dyna_call("set_field", end, rate, approach_enum)
            
            # Step 4: Execute commands repeatedly during ramp
            ramp_start = time.time()
            last_exec = ramp_start
            stable_count = 0
            
            while True:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                # Check stability
                try:
                    err, current_field, status_num = self._dyna_call("get_field")
                    status = int(status_num)
                    self.current_inplane_field = float(current_field)
                    
                    if status == 4 or status == 1:
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"End value {end} Oe stabilized")
                            break
                    else:
                        stable_count = 0
                except Exception as e:
                    self.log_message(f"Warning: Could not check field stability: {e}")
                    break
                
                # Execute commands periodically
                now = time.time()
                if gap_time == 0:
                    # Execute as fast as possible
                    if loop_commands:
                        self.execute_commands(loop_commands)
                    last_exec = now
                else:
                    # Execute every gap_time seconds
                    if now - last_exec >= gap_time and loop_commands:
                        self.execute_commands(loop_commands)
                        last_exec = now
                
                time.sleep(0.5)
            
            # Step 5: Execute commands ONCE after final stabilization
            if loop_commands:
                self.log_message(f"Final execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            self.log_message(f"Sweep complete")
            
        except Exception as e:
            self.log_message(f"sweep_dyna_field ERROR: {e}")

    def sweep_dyna_temp(self, start, end, rate, gap_time=0, loop_commands=None):
        """
        Sweep PPMS temperature continuously from start to end, executing loop commands repeatedly.
        
        Execution pattern:
        1. Set temp to start and wait for stability
        2. Execute loop_commands ONCE (initial execution)
        3. Begin ramp to end at rate
        4. While ramping: Execute loop_commands repeatedly, wait gap_time between executions
        5. When stable at end: Execute loop_commands ONCE more (final execution)
        
        Parameters
        ----------
        start : float
            Starting temperature in Kelvin (float)
        end : float
            Ending temperature in Kelvin (float)
        rate : float
            Temperature ramp rate in K/min (float)
        gap_time : float, optional
            Wait time between loop executions in seconds (default: 0, no delay)
        loop_commands : list of str, optional
            List of script commands to execute during sweep
        """
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_message("ERROR: Dyna not connected")
            return
        
        self.log_message(f"Sweeping Dyna temperature: {start} to {end} K at {rate} K/min, gap_time={gap_time}s")
        
        try:
            # Step 1: Set to start and wait for stability
            self.log_message(f"Setting temperature to start value {start} K")
            approach_enum = self._get_temp_approach_enum("fast_settle")
            self._dyna_call("set_temperature", start, rate, approach_enum)
            self.current_temp = start
            
            # Wait for start to stabilize
            max_wait = 300
            start_time = time.time()
            stable_count = 0
            
            while time.time() - start_time < max_wait and stable_count < 2:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                try:
                    err, current_temp, status_num, status_name = self._dyna_call("get_temperature")
                    status = int(status_num)
                    if status == 1:  # Stable
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"Start value {start} K stabilized")
                            break
                    else:
                        stable_count = 0
                    time.sleep(2.0)
                except Exception as e:
                    self.log_message(f"Warning: Could not check temperature stability: {e}")
                    break
            
            # Step 2: Execute commands ONCE after initial stabilization
            if loop_commands:
                self.log_message(f"Initial execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            # Step 3: Begin ramp to end
            self.log_message(f"Beginning ramp to end value {end} K")
            self._dyna_call("set_temperature", end, rate, approach_enum)
            
            # Step 4: Execute commands repeatedly during ramp
            ramp_start = time.time()
            last_exec = ramp_start
            stable_count = 0
            
            while True:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                # Check stability
                try:
                    err, current_temp, status_num, status_name = self._dyna_call("get_temperature")
                    status = int(status_num)
                    self.current_temp = float(current_temp)
                    
                    if status == 1:  # Stable
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"End value {end} K stabilized")
                            break
                    else:
                        stable_count = 0
                except Exception as e:
                    self.log_message(f"Warning: Could not check temperature stability: {e}")
                    break
                
                # Execute commands periodically
                now = time.time()
                if gap_time == 0:
                    # Execute as fast as possible
                    if loop_commands:
                        self.execute_commands(loop_commands)
                    last_exec = now
                else:
                    # Execute every gap_time seconds
                    if now - last_exec >= gap_time and loop_commands:
                        self.execute_commands(loop_commands)
                        last_exec = now
                
                time.sleep(0.5)
            
            # Step 5: Execute commands ONCE after final stabilization
            if loop_commands:
                self.log_message(f"Final execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            self.log_message(f"Sweep complete")
            
        except Exception as e:
            self.log_message(f"sweep_dyna_temp ERROR: {e}")

    def sweep_helmholtz_field(self, start, end, rate, gap_time=0, loop_commands=None):
        """
        Sweep Helmholtz field continuously from start to end, executing loop commands repeatedly.
        
        Execution pattern:
        1. Set field to start and wait for stability
        2. Execute loop_commands ONCE (initial execution)
        3. Begin ramp to end at rate
        4. While ramping: Execute loop_commands repeatedly, wait gap_time between executions
        5. When stable at end: Execute loop_commands ONCE more (final execution)
        
        Parameters
        ----------
        start : float
            Starting field in Oersteds (float)
        end : float
            Ending field in Oersteds (float)
        rate : float
            Ramp rate in Oe/s (float)
        gap_time : float, optional
            Wait time between loop executions in seconds (default: 0, no delay)
        loop_commands : list of str, optional
            List of script commands to execute during sweep
        """
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        
        self.log_message(f"Sweeping Helmholtz field: {start} to {end} Oe at {rate} Oe/s, gap_time={gap_time}s")
        
        try:
            # Convert Oe to Amperes (341.71 G/A = 341.71 Oe/A)
            current_per_oe = 1.0 / 341.71
            start_current = start * current_per_oe
            end_current = end * current_per_oe
            
            # Step 1: Set to start and wait for stability
            self.log_message(f"Setting Helmholtz field to start value {start} Oe ({start_current:.6f} A)")
            self.ramp_helmholtz_current(start_current, rate)
            self.current_helmholtz_current = start_current
            self.current_helmholtz_field = start
            
            # Wait for start to stabilize
            max_wait = 60
            start_time = time.time()
            stable_count = 0
            tolerance = max(abs(start_current) * 0.01, 0.001)
            
            while time.time() - start_time < max_wait and stable_count < 2:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                try:
                    self.device.update_current()
                    actual_current = self.device.actual_current_a + self.device.actual_current_b
                    is_stable = abs(actual_current - start_current) < tolerance
                    
                    if is_stable:
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"Start value {start} Oe stabilized")
                            break
                    else:
                        stable_count = 0
                    time.sleep(1.0)
                except Exception as e:
                    self.log_message(f"Warning: Could not check Helmholtz stability: {e}")
                    break
            
            # Step 2: Execute commands ONCE after initial stabilization
            if loop_commands:
                self.log_message(f"Initial execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            # Step 3: Begin ramp to end
            self.log_message(f"Beginning ramp to end value {end} Oe ({end_current:.6f} A)")
            self.ramp_helmholtz_current(end_current, rate)
            
            # Step 4: Execute commands repeatedly during ramp
            ramp_start = time.time()
            last_exec = ramp_start
            stable_count = 0
            tolerance = max(abs(end_current) * 0.01, 0.001)
            
            while True:
                if not self.script_running:
                    return
                while self.script_paused and self.script_running:
                    self.update_script_status()
                    time.sleep(0.1)
                
                # Check stability
                try:
                    self.device.update_current()
                    actual_current = self.device.actual_current_a + self.device.actual_current_b
                    self.current_helmholtz_current = actual_current
                    self.current_helmholtz_field = actual_current / current_per_oe
                    
                    is_stable = abs(actual_current - end_current) < tolerance
                    
                    if is_stable:
                        stable_count += 1
                        if stable_count >= 2:
                            self.log_message(f"End value {end} Oe stabilized")
                            break
                    else:
                        stable_count = 0
                except Exception as e:
                    self.log_message(f"Warning: Could not check Helmholtz stability: {e}")
                    break
                
                # Execute commands periodically
                now = time.time()
                if gap_time == 0:
                    # Execute as fast as possible
                    if loop_commands:
                        self.execute_commands(loop_commands)
                    last_exec = now
                else:
                    # Execute every gap_time seconds
                    if now - last_exec >= gap_time and loop_commands:
                        self.execute_commands(loop_commands)
                        last_exec = now
                
                time.sleep(0.5)
            
            # Step 5: Execute commands ONCE after final stabilization
            if loop_commands:
                self.log_message(f"Final execution of {len(loop_commands)} command(s)")
                self.execute_commands(loop_commands)
            
            self.log_message(f"Sweep complete")
            
        except Exception as e:
            self.log_message(f"sweep_helmholtz_field ERROR: {e}")

    def set_temperature(self):
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: Dyna not connected")
            return
        try:
            set_point = self.set_temp.get()
            rate = self.temp_rate.get()
            mode_str = self.temp_mode.get()
            mode = getattr(dyna.Temp_mode, mode_str)
            result = self._dyna_call("set_temperature", set_point, rate, mode)
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] {result}")
        except Exception as e:
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: {e}")

    def set_field_cmd(self):
        if not self.instrument_connected.get("dyna", False) or dyna is None:
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: Dyna not connected")
            return
        try:
            set_point = self.set_field.get()
            rate = self.field_rate.get()
            if rate > 50:
                rate = 50
                self.field_rate.set(50)
                self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] Field rate capped to 50 Oe/s (maximum allowed)")
            mode_str = self.field_mode.get()
            mode = getattr(dyna.Field_mode, mode_str)
            result = self._dyna_call("set_field", set_point, rate, mode)
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] {result}")
        except Exception as e:
            self.log_dyna_message(f"[{time.strftime('%H:%M:%S')}] ERROR: {e}")

    def _seconds_to_tau_index(self, seconds):
        """
        Convert time constant from seconds to TAU_TABLE index (0-19).
        Finds the closest match in New_LockIn.LockInSR830.TAU_TABLE.
        
        Parameters
        ----------
        seconds : float
            Time constant in seconds
            
        Returns
        -------
        int
            Index into TAU_TABLE (0-19)
        """
        if not hasattr(lockin, 'TAU_TABLE'):
            self.log_message("Warning: lockin.TAU_TABLE not available, using default index 9")
            return 9
        
        tau_table = lockin.TAU_TABLE
        # Find closest match
        closest_idx = min(range(len(tau_table)), key=lambda i: abs(tau_table[i] - seconds))
        returned_tau = tau_table[closest_idx]
        
        # Warn if match is far off
        if abs(returned_tau - seconds) / seconds > 0.1:  # >10% difference
            self.log_message(f"Warning: Requested tau={seconds}s, using closest TAU_TABLE[{closest_idx}]={returned_tau}s")
        
        return closest_idx

    def _db_to_filter_index(self, db_oct):
        """
        Convert filter slope from dB/octave to filter index (0-3).
        
        Parameters
        ----------
        db_oct : float or int
            Filter slope in dB/octave. Valid values: 6, 12, 18, 24
            
        Returns
        -------
        int
            Filter slope index (0=6, 1=12, 2=18, 3=24 dB/oct)
        """
        db_to_idx = {6: 0, 12: 1, 18: 2, 24: 3}
        idx = db_to_idx.get(int(db_oct), None)
        
        if idx is None:
            # Find closest match
            valid_dbs = [6, 12, 18, 24]
            closest_db = min(valid_dbs, key=lambda x: abs(x - db_oct))
            idx = db_to_idx[closest_db]
            self.log_message(f"Warning: Invalid filter slope {db_oct} dB/oct, using nearest {closest_db} dB/oct (index {idx})")
        
        return idx

    # ------------------------------
    # Device control (Helmholtz output)
    # ------------------------------
    def set_values(self):
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        try:
            current = self.set_current.get()
            self.device.set_current(current)
            self.device.set_compliance(self.compliance_voltage.get())
            self.device.set_ramp_rate(self.ramp_rate.get())
            self.log_message(f"[{time.strftime('%H:%M:%S')}] Values set: {current} A, {self.compliance_voltage.get()} V")
        except ValueError as e:
            self.log_message(f"[{time.strftime('%H:%M:%S')}] ERROR: {e}")
            self.device.disable_output()

    def enable_output(self):
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        self.device.enable_output()
        self.log_message(f"[{time.strftime('%H:%M:%S')}] Output enabled")

    def disable_output(self):
        if not self.instrument_connected.get("helmholtz", False):
            self.log_message("ERROR: Helmholtz not connected")
            return
        self.device.disable_output()
        self.log_message(f"[{time.strftime('%H:%M:%S')}] Output disabled")

    # ------------------------------
    # App lifecycle
    # ------------------------------
    def _start_dyna_poller(self):
        if self._dyna_poller_thread is not None and self._dyna_poller_thread.is_alive():
            return

        # Add network timeout to prevent hangs on PPMS communication
        if dyna is not None and not USE_MOCKUP:
            try:
                import socket
                if hasattr(dyna, 'socket'):
                    dyna.socket.settimeout(30.0)  # 30 second timeout on network calls
                    self.log_message("PPMS network timeout set to 30 seconds")
            except Exception as e:
                self.log_message(f"Warning: Could not set PPMS network timeout: {e}")

        self._dyna_poller_stop.clear()
        self._dyna_poller_thread = threading.Thread(target=self._dyna_poll_loop, daemon=True)
        self._dyna_poller_thread.start()

    def _set_dyna_snapshot(self, temp_val, field_val, temp_text, field_text):
        with self._dyna_snapshot_lock:
            self._dyna_snapshot = {
                "temp_val": temp_val,
                "field_val": field_val,
                "temp_text": temp_text,
                "field_text": field_text
            }

    def _get_dyna_snapshot(self):
        with self._dyna_snapshot_lock:
            return dict(self._dyna_snapshot)

    def _dyna_poll_loop(self):
        while not self._dyna_poller_stop.is_set():
            try:
                if not self.instrument_connected.get("dyna", False) or dyna is None:
                    self._set_dyna_snapshot(
                        temp_val=None,
                        field_val=None,
                        temp_text="Temp: Disconnected",
                        field_text="PPMS Field: Disconnected"
                    )
                    time.sleep(0.3)
                    continue

                temp_val = None
                temp_text = "Temp: Unknown"
                field_val = None
                field_text = "PPMS Field: Unknown"

                try:
                    err, temp, status_num, status_name = self._dyna_call("get_temperature")
                    temp_str = str(temp).strip().lower()
                    if temp_str != 'nan':
                        parsed_temp = float(temp)
                        if -5.0 <= parsed_temp <= 450.0:
                            temp_val = parsed_temp
                            temp_text = f"Temp: {parsed_temp:.2f} K {status_name}"
                except Exception as e:
                    # Silently continue - dyna may be busy
                    pass

                try:
                    err, field, status_num = self._dyna_call("get_field")
                    field_str = str(field).strip().lower()
                    if field_str != 'nan':
                        parsed_field = float(field)
                        field_state = dyna.Field__state_dictionary.get(int(float(status_num)), str(status_num))
                        field_val = parsed_field
                        field_text = f"PPMS Field: {parsed_field:.1f} Oe {field_state}"
                except Exception as e:
                    # Silently continue - dyna may be busy
                    pass

                self._set_dyna_snapshot(
                    temp_val=temp_val,
                    field_val=field_val,
                    temp_text=temp_text,
                    field_text=field_text
                )
                time.sleep(0.25)
            except Exception as e:
                # Log but don't crash - thread should keep running
                try:
                    self.log_message(f"Warning: Dyna poller exception: {e}")
                except:
                    pass
                time.sleep(1.0)  # Wait before retrying

    def update_ui(self):
        try:
            if not self.root.winfo_exists():
                return  # Root has been destroyed
            
            if self.instrument_connected.get("helmholtz", False):
                error = self.device.update_current()
                if error:
                    self.log_message(error)

                res_a = self.device.measure_resistance(ch='a')
                res_b = self.device.measure_resistance(ch='b')

                self.readout_a.config(text=f"Ch A: {self.device.actual_current_a:.3f} A / {f'{res_a:.3f}' if res_a is not None else '--'} Ω")
                self.readout_b.config(text=f"Ch B: {self.device.actual_current_b:.3f} A / {f'{res_b:.3f}' if res_b is not None else '--'} Ω")

                field_gauss = self.device.actual_current_a * 2 * 341.71  # 2 coils
                self.current_helmholtz_current = self.device.actual_current_a
                self.current_helmholtz_field = field_gauss
                self.field_display.config(text=f"Helmholtz Field: {field_gauss:.1f} G")
            else:
                res_a = None
                res_b = None
                self.current_helmholtz_current = 0.0
                self.current_helmholtz_field = 0.0
                self.readout_a.config(text="Ch A: Disconnected")
                self.readout_b.config(text="Ch B: Disconnected")
                self.field_display.config(text="Helmholtz Field: Disconnected")

            now = time.time()
            try:
                plot_interval_s = float(self.plot_interval.get())
            except:
                plot_interval_s = 1.0

            if self.instrument_connected.get("helmholtz", False) and self.device.enabled and plot_interval_s > 0 and (now - self.last_plot_time) >= plot_interval_s:
                if res_a is not None and res_b is not None:
                    elapsed_s = round(now - self.start_time, 1)
                    self.time_data.append(elapsed_s)
                    self.resistance_a.append(res_a)
                    self.resistance_b.append(res_b)
                    
                    # Limit plot data to prevent memory growth
                    if len(self.time_data) > self._max_plot_points:
                        excess = len(self.time_data) - self._max_plot_points
                        self.time_data = self.time_data[excess:]
                        self.resistance_a = self.resistance_a[excess:]
                        self.resistance_b = self.resistance_b[excess:]
                    
                    self.update_plot()
                    self.last_plot_time = now

            # Update Dyna from background-poll snapshot (keeps UI thread responsive)
            dyna_snapshot = self._get_dyna_snapshot()
            temp_val = dyna_snapshot["temp_val"]
            field_val = dyna_snapshot["field_val"]
            self.current_temp = temp_val
            self.current_inplane_field = field_val
            self.temp_display.config(text=dyna_snapshot["temp_text"])
            self.field_display_dyna.config(text=dyna_snapshot["field_text"])

            # Plot dyna data every dyna interval
            try:
                dyna_interval = float(self.dyna_plot_interval.get())
            except:
                dyna_interval = 1.0
            if self.instrument_connected.get("dyna", False) and dyna_interval > 0 and (now - self.last_plot_time_dyna) >= dyna_interval:
                if temp_val is not None and field_val is not None:
                    t_dyna = round(now - self.start_time_dyna, 1)
                    self.time_data_dyna.append(t_dyna)
                    self.temp_data.append(temp_val)
                    self.field_data.append(field_val)
                    
                    # Limit plot data to prevent memory growth
                    if len(self.time_data_dyna) > self._max_plot_points:
                        excess = len(self.time_data_dyna) - self._max_plot_points
                        self.time_data_dyna = self.time_data_dyna[excess:]
                        self.temp_data = self.temp_data[excess:]
                        self.field_data = self.field_data[excess:]
                    
                    self.update_dyna_plot()
                    self.last_plot_time_dyna = now
                    
                    # Write to auto-log if enabled
                    if self.auto_log_enabled.get():
                        self._write_auto_log()

            # Update Results tab system status displays
            # Sync Helmholtz displays
            self.results_helmholtz_field.config(text=self.field_display.cget("text"))
            self.results_helmholtz_ch_a.config(text=self.readout_a.cget("text"))
            self.results_helmholtz_ch_b.config(text=self.readout_b.cget("text"))
            
            # Sync PPMS/Dyna displays
            self.results_dyna_temp.config(text=self.temp_display.cget("text"))
            self.results_dyna_field.config(text=self.field_display_dyna.cget("text"))
            
            # Sync Hall Bar displays (from k2450_result label)
            try:
                hall_text = self.k2450_result.cget("text")
                # Extract voltage and field from the format "Voltage: X V, Field: Y G"
                if "Voltage:" in hall_text and "Field:" in hall_text:
                    parts = hall_text.split(",")
                    voltage_part = parts[0].strip()  # "Voltage: X V"
                    field_part = parts[1].strip()    # "Field: Y G"
                    self.results_hall_voltage.config(text=voltage_part)
                    self.results_hall_field.config(text=field_part)
                else:
                    self.results_hall_voltage.config(text="Voltage: -- V")
                    self.results_hall_field.config(text="Field: -- G")
            except:
                self.results_hall_voltage.config(text="Voltage: -- V")
                self.results_hall_field.config(text="Field: -- G")
            
            # Sync LockIn displays
            try:
                self.results_lockin_x.config(text=f"X: {self.lockin_x_display.cget('text')}")
                self.results_lockin_y.config(text=f"Y: {self.lockin_y_display.cget('text')}")
                self.results_lockin_r.config(text=f"R: {self.lockin_r_display.cget('text')}")
                self.results_lockin_phase.config(text=f"Phase: {self.lockin_phase_display.cget('text')}")
            except:
                self.results_lockin_x.config(text="X: -- V")
                self.results_lockin_y.config(text="Y: -- V")
                self.results_lockin_r.config(text="R: -- V")
                self.results_lockin_phase.config(text="Phase: -- °")

            if hasattr(self, "results_switch_status"):
                self.results_switch_status.config(text=self._get_switch_state_summary())

            # Schedule next update (keep only ONE callback at a time to prevent infinite queue)
            if self.root.winfo_exists():
                self._update_ui_callback_id = self.root.after(100, self.update_ui)
        except Exception as e:
            try:
                self.log_message(f"Error in update_ui: {e}")
            except:
                pass

    def on_close(self):
        # Set flag to stop background threads
        self._dyna_poller_stop.set()
        self.script_running = False
        self.led_switch_blinking = False  # Stop LED blinking

        # Cancel the update_ui callback specifically (CRITICAL: prevents infinite queue)
        if self._update_ui_callback_id is not None:
            try:
                self.root.after_cancel(self._update_ui_callback_id)
            except:
                pass

        # Cancel all other pending callbacks to prevent post-close updates
        for callback_id in self._pending_callbacks:
            try:
                self.root.after_cancel(callback_id)
            except:
                pass
        self._pending_callbacks.clear()
        
        # Cancel LED blink callback if active
        if self.led_switch_blink_id is not None:
            try:
                self.root.after_cancel(self.led_switch_blink_id)
            except:
                pass

        # Wait for dyna poller thread to exit (with timeout)
        if self._dyna_poller_thread is not None and self._dyna_poller_thread.is_alive():
            try:
                self._dyna_poller_thread.join(timeout=2.0)
            except:
                pass
        
        # Wait for script thread to exit (with timeout)
        if self.script_thread is not None and self.script_thread.is_alive():
            try:
                self.script_thread.join(timeout=2.0)
            except:
                pass

        # Disable device output with error handling
        try:
            self.device.disable_output()
            print(f"[{time.strftime('%H:%M:%S')}] Application closed. Outputs disabled.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error disabling outputs: {e}")
        
        # Close data file if open (with lock protection)
        if self.data_file is not None:
            try:
                with self._csv_lock:
                    self.data_file.close()
                    print(f"Data file closed: {self.data_filename}")
            except Exception as e:
                print(f"Error closing data file: {e}")
        
        # Close auto-log file if open
        try:
            self._close_auto_log()
            print(f"Auto-log file closed")
        except Exception as e:
            print(f"Error closing auto-log: {e}")
        
        # Disconnect instruments with error handling
        try:
            self._dyna_call("disconnect")
            print(f"[{time.strftime('%H:%M:%S')}] Dyna disconnected.")
        except Exception as e:
            print(f"Error disconnecting Dyna: {e}")
        
        try:
            if keithley2450 is not None:
                keithley2450.shutdown()
                keithley2450.disconnect()
        except Exception as e:
            print(f"Error shutting down Keithley 2450: {e}")
            try:
                if keithley2450 is not None:
                    keithley2450.disable_source()
                    keithley2450.disconnect()
            except:
                pass
        
        try:
            if lockin is not None:
                lockin.sine_output_off()  # Set sine output to minimum (0.004V) before closing
        except Exception as e:
            print(f"Error setting lock-in output to minimum: {e}")
        
        try:
            if switch is not None:
                switch.open_all()
                switch.disconnect()
        except Exception as e:
            print(f"Error disconnecting switch: {e}")
        
        # Finally, destroy the root window
        try:
            root.destroy()
        except:
            pass

    def start(self):
        self.start_time = time.time()
        root.mainloop()

root = tk.Tk()
app = DualSMUGUI(root)
app.start()

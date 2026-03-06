"""
v3.gui.switch_tab  —  Switch matrix control tab.

Provides channel configuration (I+, V+, V−, I− for channels a-h),
open/close controls, connection status, and device photo annotation.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import INST_SWITCH
from v3.core.ui_events import (
    W_LED_SWITCH,
    W_SWITCH_CONNECTED,
    W_SWITCH_STATUS,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader, make_led, set_led

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

# Try importing PIL for photo annotation
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Default annotations file
ANNOTATIONS_FILE = Path("device_annotations.json")


class SwitchTab(BaseTab):
    """Switch matrix control tab with device photo annotation."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._switch_led_after_id: str | None = None
        # Photo annotation state
        self.device_photo_path: Path | None = None
        self.photo_image: Any = None  # PIL Image
        self.photo_labels: dict[int, dict] = {}
        self.selected_label: int | None = None
        self.label_buttons: dict[int, ttk.Button] = {}
        self.label_placement_window: tk.Toplevel | None = None
        self.annotations_file = ANNOTATIONS_FILE
        self._channel_config_frame: ttk.LabelFrame | None = None
        self.close_channel_combo: ttk.Combobox | None = None
        self.clone_source_var = tk.StringVar(value="a")
        self.clone_target_var = tk.StringVar(value="b")
        self.template_var = tk.StringVar(value="Sequential 1-4")
        self._template_presets: dict[str, dict[str, int]] = {
            "Sequential 1-4": {"I+": 1, "V+": 2, "V-": 3, "I-": 4},
            "Sequential 5-8": {"I+": 5, "V+": 6, "V-": 7, "I-": 8},
            "Mirror I/V": {"I+": 1, "V+": 4, "V-": 3, "I-": 2},
        }

    def create_widgets(self) -> None:
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="switch",
            display_name="Switch Matrix",
            on_connect=lambda: self.app.connect_instrument("switch"),
            on_disconnect=lambda: self.app.disconnect_instrument("switch"),
        )

        body = ttk.Frame(self.parent)
        body.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_columnconfigure(1, weight=1)

        left = ttk.Frame(body, padding=10)
        left.pack(side="left", fill="y")

        right = ttk.Frame(body, padding=10, width=380)
        right.pack(side="left", fill="both", expand=False)

        self._build_channel_config(left)
        self._build_controls(left)
        self._build_status(left)
        self._build_photo_annotation(right)

    # ------------------------------------------------------------------
    # Channel configuration
    # ------------------------------------------------------------------
    def _build_channel_config(self, parent: ttk.Frame) -> None:
        self._channel_config_frame = ttk.LabelFrame(parent, text="Channel Configuration")
        self._channel_config_frame.pack(fill="x", padx=5, pady=5)
        self._render_channel_config_rows()

    def _render_channel_config_rows(self) -> None:
        if self._channel_config_frame is None:
            return
        frame = self._channel_config_frame
        for child in frame.winfo_children():
            child.destroy()

        headers = ["Channel", "I+", "V+", "V−", "I−"]
        for i, header in enumerate(headers):
            ttk.Label(frame, text=header, style="SectionTitle.TLabel").grid(
                row=0, column=i, padx=5, pady=2
            )

        for row_idx, ch in enumerate(self.app.channels, start=1):
            ttk.Label(frame, text=ch.upper()).grid(row=row_idx, column=0, padx=5, pady=2)
            for col_idx, pin in enumerate(["I+", "V+", "V-", "I-"], start=1):
                var = self.app.channel_configs[ch][pin]
                ttk.Spinbox(frame, from_=1, to=8, textvariable=var, width=5).grid(
                    row=row_idx, column=col_idx, padx=5, pady=2
                )

    def _refresh_channel_selectors(self) -> None:
        values = list(self.app.channels)
        if self.close_channel_combo is not None:
            self.close_channel_combo.configure(values=values)

        if self.close_channel_var.get() not in values and values:
            self.close_channel_var.set(values[0])
        if self.clone_source_var.get() not in values and values:
            self.clone_source_var.set(values[0])
        if self.clone_target_var.get() not in values:
            if len(values) > 1:
                self.clone_target_var.set(values[1])
            elif values:
                self.clone_target_var.set(values[0])

    # ------------------------------------------------------------------
    # Control buttons
    # ------------------------------------------------------------------
    def _build_controls(self, parent: ttk.Frame) -> None:
        bf = ttk.LabelFrame(parent, text="Controls")
        bf.pack(fill="x", padx=5, pady=5)

        default_channel = self.app.channels[0] if self.app.channels else "a"
        self.close_channel_var = tk.StringVar(value=default_channel)
        ttk.Label(bf, text="Channel:").pack(side="left", padx=5)
        self.close_channel_combo = ttk.Combobox(
            bf,
            textvariable=self.close_channel_var,
            values=self.app.channels,
            state="readonly",
            width=8,
        )
        self.close_channel_combo.pack(side="left", padx=5)

        ttk.Button(bf, text="Configure", command=self._on_configure).pack(side="left", padx=5)
        ttk.Button(bf, text="Open All", command=self._on_open_all).pack(side="left", padx=5)
        ttk.Button(bf, text="Close Channel", command=self._on_close).pack(side="left", padx=5)

        manage = ttk.LabelFrame(parent, text="Configuration Management")
        manage.pack(fill="x", padx=5, pady=5)

        row1 = ttk.Frame(manage)
        row1.pack(fill="x", padx=5, pady=3)
        ttk.Button(row1, text="Add Configuration", command=self._on_add_configuration).pack(side="left", padx=3)
        ttk.Button(row1, text="Remove Selected", command=self._on_remove_configuration).pack(side="left", padx=3)

        row2 = ttk.Frame(manage)
        row2.pack(fill="x", padx=5, pady=3)
        ttk.Label(row2, text="Template:").pack(side="left")
        ttk.Combobox(
            row2,
            textvariable=self.template_var,
            values=list(self._template_presets.keys()),
            state="readonly",
            width=20,
        ).pack(side="left", padx=4)
        ttk.Button(row2, text="Apply to Selected", command=self._on_apply_template).pack(side="left", padx=4)

        row3 = ttk.Frame(manage)
        row3.pack(fill="x", padx=5, pady=3)
        ttk.Label(row3, text="Clone").pack(side="left")
        ttk.Combobox(row3, textvariable=self.clone_source_var, values=self.app.channels, state="readonly", width=5).pack(side="left", padx=4)
        ttk.Label(row3, text="→").pack(side="left")
        ttk.Combobox(row3, textvariable=self.clone_target_var, values=self.app.channels, state="readonly", width=5).pack(side="left", padx=4)
        ttk.Button(row3, text="Clone", command=self._on_clone_configuration).pack(side="left", padx=4)

        self._refresh_channel_selectors()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _build_status(self, parent: ttk.Frame) -> None:
        sf = ttk.LabelFrame(parent, text="Status")
        sf.pack(fill="x", padx=5, pady=5)

        self.status_label = ttk.Label(sf, text="Switch: Disconnected")
        self.status_label.pack(anchor="w", padx=5, pady=5)

        self.switch_led = make_led(sf)
        self.switch_led.pack(anchor="w", padx=5, pady=2)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_SWITCH_STATUS:
            self.status_label.configure(text=str(value))
        elif widget_id == W_LED_SWITCH:
            if bool(value):
                self._pulse_switch_widget_led()
            else:
                if self._switch_led_after_id is not None:
                    try:
                        self.app.root.after_cancel(self._switch_led_after_id)
                    except Exception:
                        pass
                    self._switch_led_after_id = None
                set_led(self.switch_led, False)
        elif widget_id == W_SWITCH_CONNECTED:
            if self._conn_header:
                self._conn_header.set_connected(bool(value))

    def _pulse_switch_widget_led(self, duration_ms: int = 500) -> None:
        set_led(self.switch_led, True)
        if self._switch_led_after_id is not None:
            try:
                self.app.root.after_cancel(self._switch_led_after_id)
            except Exception:
                pass
            self._switch_led_after_id = None
        self._switch_led_after_id = self.app.root.after(
            duration_ms,
            lambda: set_led(self.switch_led, False),
        )

    def on_instrument_connected(self, name: str) -> None:
        if name == "switch":
            if self._conn_header:
                self._conn_header.set_connected(True)
            self._post_switch_summary()

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "switch":
            if self._conn_header:
                self._conn_header.set_connected(False)
            self.app.ui_bus.post(W_SWITCH_STATUS, "Switch: Disconnected")
            self.app.ui_bus.post(W_LED_SWITCH, False)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _pulse_switch_led(self, duration_ms: int = 500) -> None:
        self.app.ui_bus.post(W_LED_SWITCH, True)
        if self._switch_led_after_id is not None:
            try:
                self.app.root.after_cancel(self._switch_led_after_id)
            except Exception:
                pass
            self._switch_led_after_id = None
        self._switch_led_after_id = self.app.root.after(
            duration_ms,
            lambda: self.app.ui_bus.post(W_LED_SWITCH, False),
        )

    def _switch_state_summary(self) -> str:
        inst = self.app.bus.get_raw(INST_SWITCH)
        if not self.app.instrument_connected.get("switch", False) or inst is None:
            return "Switch: Disconnected"

        closed = {str(v) for v in getattr(inst, "closed_channels", set())}

        def _pin_is_closed(pin: str) -> bool:
            return (
                pin in closed
                or f"110{pin}" in closed
                or f"120{pin}" in closed
                or f"130{pin}" in closed
                or f"140{pin}" in closed
            )

        closed_channels: list[str] = []
        for ch in self.app.channels:
            cfg = self.app.channel_configs[ch]
            pins = [str(cfg[key].get()) for key in ("I+", "V+", "V-", "I-")]
            is_closed = any(_pin_is_closed(pin) for pin in pins)
            if is_closed:
                closed_channels.append(ch.upper())

        if not closed_channels:
            return "Switch: All Open"
        if len(closed_channels) == 1:
            return f"Switch: Channel {closed_channels[0]} Closed"
        return "Switch: Multiple channels closed"

    def _post_switch_summary(self) -> None:
        self.app.ui_bus.post(W_SWITCH_STATUS, self._switch_state_summary())

    def _on_configure(self) -> None:
        """Configure the selected switch channel."""
        try:
            ch = self.close_channel_var.get()
            cfg = self.app.channel_configs[ch]
            ip = cfg["I+"].get()
            vp = cfg["V+"].get()
            vm = cfg["V-"].get()
            im = cfg["I-"].get()

            from v3.core.measurements import configure_channel
            ctx = self.app.make_context()
            configure_channel(ctx, ch, ip, vp, vm, im)

            self.app.active_channel = ch
            self._pulse_switch_led()
            self._post_switch_summary()
            self._refresh_channel_selectors()
            self.app.ui_bus.post_log(f"Switch channel {ch} configured: I+={ip} V+={vp} V-={vm} I-={im}")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Configure error: {exc}")

    def _on_add_configuration(self) -> None:
        try:
            new_channel = self.app.add_channel_config()
            self._render_channel_config_rows()
            self._refresh_channel_selectors()
            self.close_channel_var.set(new_channel)
            self.app.ui_bus.post_log(f"Added channel configuration '{new_channel}'.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Add configuration error: {exc}")

    def _on_remove_configuration(self) -> None:
        try:
            channel = self.close_channel_var.get().strip().lower()
            self.app.remove_channel_config(channel)
            self._render_channel_config_rows()
            self._refresh_channel_selectors()
            self._post_switch_summary()
            self.app.ui_bus.post_log(f"Removed channel configuration '{channel}'.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Remove configuration error: {exc}")

    def _on_apply_template(self) -> None:
        try:
            channel = self.close_channel_var.get().strip().lower()
            cfg = self.app.channel_configs[channel]
            preset = self._template_presets.get(self.template_var.get())
            if preset is None:
                raise ValueError("Unknown template")
            for pin, value in preset.items():
                cfg[pin].set(int(value))
            self._render_channel_config_rows()
            self.app.ui_bus.post_log(f"Applied template '{self.template_var.get()}' to channel {channel}.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Template apply error: {exc}")

    def _on_clone_configuration(self) -> None:
        try:
            src = self.clone_source_var.get().strip().lower()
            dst = self.clone_target_var.get().strip().lower()
            if src == dst:
                raise ValueError("Source and target channels must be different")
            self.app.clone_channel_config(src, dst)
            self._render_channel_config_rows()
            self.app.ui_bus.post_log(f"Cloned channel config: {src} -> {dst}.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Clone configuration error: {exc}")

    def _on_open_all(self) -> None:
        try:
            from v3.core.measurements import open_all_channels
            ctx = self.app.make_context()
            self._pulse_switch_led()
            open_all_channels(ctx)
            self.app.active_channel = None
            self._post_switch_summary()
            self.app.ui_bus.post_log("All switch channels opened.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Open all error: {exc}")

    def _on_close(self) -> None:
        try:
            ch = self.close_channel_var.get()
            cfg = self.app.channel_configs[ch]
            from v3.core.measurements import close_channel
            from v3.core.measurements import open_all_channels
            ctx = self.app.make_context()

            ip = int(cfg["I+"].get())
            vp = int(cfg["V+"].get())
            vm = int(cfg["V-"].get())
            im = int(cfg["I-"].get())

            # Open all first, then close all 4 pins for selected channel in one operation
            self._pulse_switch_led()
            open_all_channels(ctx)
            inst = self.app.bus.get_raw(INST_SWITCH)
            if inst is not None and hasattr(inst, "close_list"):
                self.app.bus.execute(INST_SWITCH, "close_list", ip, vp, vm, im)
            else:
                for pin in (ip, vp, vm, im):
                    close_channel(ctx, pin)

            self.app.active_channel = ch
            self._post_switch_summary()
            self.app.ui_bus.post_log(f"Switch channel {ch} closed.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Close channel error: {exc}")

    # ==================================================================
    # Device Photo Annotation (matching V2)
    # ==================================================================
    def _build_photo_annotation(self, parent: ttk.Frame) -> None:
        """Build the device photo annotation panel on the right side."""
        ttk.Label(parent, text="Device Photo Annotation",
              style="SectionTitleLarge.TLabel").pack(pady=(0, 10))

        # Photo control buttons
        photo_btn_frame = ttk.Frame(parent)
        photo_btn_frame.pack(fill="x", pady=5)
        ttk.Button(photo_btn_frame, text="Load Photo",
                   command=self._load_device_photo).pack(side="left", padx=2)
        ttk.Button(photo_btn_frame, text="Export Annotated",
                   command=self._export_annotated_photo).pack(side="left", padx=2)

        # Label control frame
        label_ctrl_frame = ttk.LabelFrame(parent, text="Label Controls", padding=5)
        label_ctrl_frame.pack(fill="x", pady=5)

        # Color selector
        self.label_color = tk.StringVar(value="white")
        ttk.Label(label_ctrl_frame, text="Label Color:").grid(
            row=0, column=0, sticky="w", padx=2, pady=2)
        color_combo = ttk.Combobox(
            label_ctrl_frame, textvariable=self.label_color,
            values=["black", "white", "red", "yellow", "green", "blue"],
            state="readonly", width=12,
        )
        color_combo.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        color_combo.bind("<<ComboboxSelected>>", lambda e: self._redraw_photo_canvas())

        # Text size
        self.label_text_size = tk.IntVar(value=20)
        ttk.Label(label_ctrl_frame, text="Text Size:").grid(
            row=1, column=0, sticky="w", padx=2, pady=2)
        size_spinbox = ttk.Spinbox(
            label_ctrl_frame, from_=8, to=100,
            textvariable=self.label_text_size, width=15,
        )
        size_spinbox.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        size_spinbox.bind("<FocusOut>", lambda e: self._redraw_photo_canvas())

        # Label buttons (1-8)
        label_btn_frame = ttk.Frame(label_ctrl_frame)
        label_btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(label_btn_frame, text="Place Label:").pack(side="left", padx=2)
        for num in range(1, 9):
            btn = ttk.Button(
                label_btn_frame, text=str(num), width=3,
                command=lambda n=num: self._prepare_label_placement(n),
            )
            btn.pack(side="left", padx=1)
            self.label_buttons[num] = btn

        # Delete selected label button
        ttk.Button(
            label_ctrl_frame, text="Delete Selected Label",
            command=self._delete_selected_label,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        label_ctrl_frame.columnconfigure(1, weight=1)

        # Canvas for photo display
        canvas_frame = ttk.LabelFrame(parent, text="Photo Preview", padding=5)
        canvas_frame.pack(fill="both", expand=True, pady=5)

        self.photo_canvas = tk.Canvas(canvas_frame, bg="gray20", height=300, width=320)
        self.photo_canvas.pack(fill="both", expand=True)
        self.photo_canvas.bind("<Button-1>", self._on_canvas_click)
        self.photo_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.photo_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.photo_canvas.bind("<Button-3>", self._on_canvas_right_click)

    def _load_device_photo(self) -> None:
        """Load a device photo from file."""
        if not HAS_PIL:
            messagebox.showerror("Missing Dependency",
                                 "PIL/Pillow is required for photo annotation.\n"
                                 "Install with: pip install Pillow")
            return

        file_path = filedialog.askopenfilename(
            title="Select Device Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            self.device_photo_path = Path(file_path)
            self.photo_image = Image.open(self.device_photo_path)
            self.photo_image.thumbnail((320, 300), Image.Resampling.LANCZOS)
            self._load_annotations()
            self._redraw_photo_canvas()
            self.app.ui_bus.post_log(f"Photo loaded: {self.device_photo_path.name}")
        except Exception as e:
            messagebox.showerror("Photo Load Error", f"Failed to load photo: {e}")

    def _redraw_photo_canvas(self) -> None:
        """Redraw canvas with photo and labels."""
        if not HAS_PIL or self.photo_canvas is None or self.photo_image is None:
            return

        try:
            img_copy = self.photo_image.copy()
            draw = ImageDraw.Draw(img_copy)

            for label_num, label_data in self.photo_labels.items():
                x = label_data["x"]
                y = label_data["y"]
                color = label_data["color"]
                size = self.label_text_size.get()

                color_map = {
                    "black": (0, 0, 0), "white": (255, 255, 255),
                    "red": (255, 0, 0), "yellow": (255, 255, 0),
                    "green": (0, 255, 0), "blue": (0, 0, 255),
                }
                rgb_color = color_map.get(color, (255, 255, 255))

                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except Exception:
                    font = ImageFont.load_default()

                circle_radius = size // 2 + 5
                draw.ellipse(
                    [(x - circle_radius, y - circle_radius),
                     (x + circle_radius, y + circle_radius)],
                    fill=rgb_color, outline=rgb_color,
                )
                text_color = (255, 255, 255) if color != "white" else (0, 0, 0)
                draw.text((x, y), str(label_num), fill=text_color, font=font, anchor="mm")

            photo_tk = ImageTk.PhotoImage(img_copy)
            self.photo_canvas.delete("all")
            self.photo_canvas.create_image(0, 0, image=photo_tk, anchor="nw")
            self.photo_canvas.image = photo_tk  # Keep reference
        except Exception as e:
            print(f"Error redrawing canvas: {e}")

    def _prepare_label_placement(self, label_num: int) -> None:
        """Prepare to place a label on the photo."""
        if self.photo_image is None:
            messagebox.showinfo("No Photo", "Please load a photo first.")
            return

        self._close_label_placement_window()
        self.selected_label = label_num

        self.label_placement_window = tk.Toplevel(self.app.root)
        self.label_placement_window.title(f"Place Label {label_num}")
        self.label_placement_window.geometry("300x100")
        self.label_placement_window.attributes("-topmost", True)

        is_editing = label_num in self.photo_labels
        msg = f"Click on canvas to {'reposition' if is_editing else 'place'} label {label_num}"
        ttk.Label(self.label_placement_window, text=msg, wraplength=280).pack(pady=20)
        ttk.Label(
            self.label_placement_window,
            text="Window will close automatically after placement",
            font=("Arial", 8), foreground="gray",
        ).pack()

    def _close_label_placement_window(self) -> None:
        """Close the label placement popup if open."""
        if self.label_placement_window is not None:
            try:
                self.label_placement_window.destroy()
            except Exception:
                pass
            self.label_placement_window = None

    def _on_canvas_click(self, event: tk.Event) -> None:
        """Handle click on the photo canvas."""
        if self.selected_label is not None:
            self.photo_labels[self.selected_label] = {
                "x": event.x,
                "y": event.y,
                "color": self.label_color.get(),
            }
            self._save_annotations()
            self._redraw_photo_canvas()
            self._update_label_button_states()
            self._close_label_placement_window()
            self.app.ui_bus.post_log(f"Label {self.selected_label} placed at ({event.x}, {event.y})")
            self.selected_label = None
        else:
            # Check if click is near an existing label to select it for dragging
            for label_num, data in self.photo_labels.items():
                dx = event.x - data["x"]
                dy = event.y - data["y"]
                if (dx * dx + dy * dy) < 400:  # within 20px radius
                    self.selected_label = label_num
                    break

    def _on_canvas_drag(self, event: tk.Event) -> None:
        """Handle drag on the photo canvas to reposition labels."""
        if self.selected_label is not None and self.selected_label in self.photo_labels:
            self.photo_labels[self.selected_label]["x"] = event.x
            self.photo_labels[self.selected_label]["y"] = event.y
            self._redraw_photo_canvas()

    def _on_canvas_release(self, event: tk.Event) -> None:
        """Handle mouse button release — save label position."""
        if self.selected_label is not None and self.selected_label in self.photo_labels:
            self._save_annotations()
            self.selected_label = None

    def _on_canvas_right_click(self, event: tk.Event) -> None:
        """Right-click to delete a label near the click position."""
        for label_num, data in list(self.photo_labels.items()):
            dx = event.x - data["x"]
            dy = event.y - data["y"]
            if (dx * dx + dy * dy) < 400:
                del self.photo_labels[label_num]
                self._save_annotations()
                self._redraw_photo_canvas()
                self._update_label_button_states()
                self.app.ui_bus.post_log(f"Label {label_num} deleted.")
                break

    def _delete_selected_label(self) -> None:
        """Delete the currently selected label."""
        if self.selected_label is not None and self.selected_label in self.photo_labels:
            del self.photo_labels[self.selected_label]
            self._save_annotations()
            self._redraw_photo_canvas()
            self._update_label_button_states()
            self.app.ui_bus.post_log(f"Label {self.selected_label} deleted.")
            self.selected_label = None
        else:
            messagebox.showinfo("No Selection", "No label selected to delete.")

    def _update_label_button_states(self) -> None:
        """Visually mark buttons for placed labels."""
        for num, btn in self.label_buttons.items():
            if num in self.photo_labels:
                try:
                    btn.configure(style="Accent.TButton")
                except Exception:
                    pass  # style may not exist

    def _save_annotations(self) -> None:
        """Save annotations to JSON file."""
        if self.device_photo_path is None:
            return
        try:
            anno_data = {
                "photo_path": str(self.device_photo_path),
                "labels": self.photo_labels,
            }
            with open(self.annotations_file, "w") as f:
                json.dump(anno_data, f, indent=2)
        except Exception as e:
            print(f"Error saving annotations: {e}")

    def _load_annotations(self) -> None:
        """Load annotations from JSON file."""
        if not self.annotations_file.exists():
            self.photo_labels = {}
            return
        try:
            with open(self.annotations_file, "r") as f:
                anno_data = json.load(f)
            if anno_data.get("photo_path") == str(self.device_photo_path):
                self.photo_labels = {int(k): v for k, v in anno_data.get("labels", {}).items()}
            else:
                self.photo_labels = {}
        except Exception as e:
            print(f"Error loading annotations: {e}")
            self.photo_labels = {}
        self._update_label_button_states()

    def _export_annotated_photo(self) -> None:
        """Export photo with annotations burned in."""
        if not HAS_PIL:
            messagebox.showerror("Missing Dependency", "PIL/Pillow required.")
            return
        if self.photo_image is None:
            messagebox.showinfo("No Photo", "Please load a photo first.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Annotated Photo",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPG files", "*.jpg"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            export_img = self.photo_image.copy()
            draw = ImageDraw.Draw(export_img)
            for label_num, label_data in self.photo_labels.items():
                x, y = label_data["x"], label_data["y"]
                color = label_data["color"]
                size = self.label_text_size.get()

                color_map = {
                    "black": (0, 0, 0), "white": (255, 255, 255),
                    "red": (255, 0, 0), "yellow": (255, 255, 0),
                    "green": (0, 255, 0), "blue": (0, 0, 255),
                }
                rgb_color = color_map.get(color, (255, 255, 255))
                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except Exception:
                    font = ImageFont.load_default()

                circle_radius = size // 2 + 5
                draw.ellipse(
                    [(x - circle_radius, y - circle_radius),
                     (x + circle_radius, y + circle_radius)],
                    fill=rgb_color, outline=rgb_color,
                )
                text_color = (255, 255, 255) if color != "white" else (0, 0, 0)
                draw.text((x, y), str(label_num), fill=text_color, font=font, anchor="mm")

            export_img.save(file_path)
            messagebox.showinfo("Export Successful", f"Photo saved to:\n{file_path}")
            self.app.ui_bus.post_log(f"Annotated photo exported: {Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export photo: {e}")

"""
v3.core.script_parser  -  DSL parser, validator, and executor.

Parses the experiment script language into structured command objects,
validates them, and provides an executor that dispatches to the
appropriate measurement/control functions.

The DSL is line-oriented:
* Blank lines and ``#``-comments are ignored.
* Top-level commands: ``set_dyna_field 1000 100 linear``
* Loop commands: ``scan_dyna_field 0 1000 100 10 linear`` followed by
  indented sub-commands.
* Key=value arguments: ``measure_lockin current=0.001 avg=20``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from v3.core.constants import LOGICAL_CHANNELS

logger = logging.getLogger(__name__)

_CHANNEL_SET = set(LOGICAL_CHANNELS)
_CHANNEL_LIST_TEXT = ", ".join(f"'{ch}'" for ch in LOGICAL_CHANNELS)


# ============================================================================
# Parsed command representation
# ============================================================================
@dataclass
class ParsedCommand:
    """A single parsed DSL command."""

    name: str
    args: list[str] = field(default_factory=list)
    kwargs: dict[str, str] = field(default_factory=dict)
    line_number: int = 0
    raw: str = ""
    indent: int = 0
    has_multiple_commands: bool = False
    # Indented sub-commands (for scan/sweep loops)
    children: list["ParsedCommand"] = field(default_factory=list)

    def get_float(self, key: str, default: float | None = None) -> float | None:
        """Get a kwarg as float, or positional arg, or default."""
        if key in self.kwargs:
            return float(self.kwargs[key])
        return default

    def get_int(self, key: str, default: int | None = None) -> int | None:
        """Get a kwarg as int."""
        if key in self.kwargs:
            return int(self.kwargs[key])
        return default

    def get_str(self, key: str, default: str | None = None) -> str | None:
        """Get a kwarg as string."""
        return self.kwargs.get(key, default)

    def get_bool(self, key: str, default: bool = True) -> bool:
        """Get a kwarg as bool (true/1/yes → True)."""
        val = self.kwargs.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    def get_tuple(self, key: str, default: tuple = ()) -> tuple[str, ...]:
        """Get a kwarg as comma-separated tuple."""
        val = self.kwargs.get(key)
        if val is None:
            return default
        return tuple(s.strip() for s in val.split(","))


# ============================================================================
# Known commands with signatures (for validation)
# ============================================================================
# Commands that accept indented sub-commands (loops)
LOOP_COMMANDS = frozenset({
    "scan_dyna_field",
    "scan_dyna_temp",
    "sweep_dyna_field",
    "sweep_dyna_temp",
    "scan_helmholtz_field",
    "sweep_helmholtz_field",
    "scan_ppms_field_and_fix_hall",
    "time_sweep",
    "for_loop",
})

MAX_LOOP_NESTING = 5

# All valid top-level command names
VALID_COMMANDS = frozenset({
    "test",
    "initialize_data_file",
    "set_dyna_field",
    "set_dyna_temp",
    "set_helmholtz_field",
    "wait_for",
    "run_saved_script",
    "measure_hall_field",
    "continuous_measure_hall_field",
    "enable_hall_output",
    "disable_hall_output",
    "measure_lockin",
    "continuous_measure_lockin",
    "full_measure",
    "continuous_full_measure",
    "set_ppms_field_and_fix_hall",
    "scan_ppms_field_and_fix_hall",
    "auto_gain",
    "auto_phase",
    "auto_reserve",
    "set_lockin_time_constant",
    "set_lockin_sensitivity",
    "set_lockin_filter",
    "set_lockin_frequency",
    "set_lockin_current",
    "add_note",
    "open_all_channels",
    "close_channel",
    "configure_channel",
}) | LOOP_COMMANDS

# Commands that require specific instruments
INSTRUMENT_REQUIREMENTS: dict[str, list[str]] = {
    "set_dyna_field": ["dyna"],
    "set_dyna_temp": ["dyna"],
    "scan_dyna_field": ["dyna"],
    "scan_dyna_temp": ["dyna"],
    "sweep_dyna_field": ["dyna"],
    "sweep_dyna_temp": ["dyna"],
    "set_helmholtz_field": ["helmholtz"],
    "scan_helmholtz_field": ["helmholtz"],
    "sweep_helmholtz_field": ["helmholtz"],
    "wait_for": [],  # depends on event type
    "measure_hall_field": ["hall"],
    "continuous_measure_hall_field": ["hall"],
    "enable_hall_output": ["hall"],
    "disable_hall_output": ["hall"],
    "measure_lockin": ["lockin"],
    "continuous_measure_lockin": ["lockin"],
    "full_measure": ["hall", "lockin", "switch"],
    "continuous_full_measure": ["hall", "lockin"],
    "set_ppms_field_and_fix_hall": ["dyna", "helmholtz", "hall"],
    "scan_ppms_field_and_fix_hall": ["dyna", "helmholtz", "hall"],
    "auto_gain": ["lockin"],
    "auto_phase": ["lockin"],
    "auto_reserve": ["lockin"],
    "set_lockin_time_constant": ["lockin"],
    "set_lockin_sensitivity": ["lockin"],
    "set_lockin_filter": ["lockin"],
    "set_lockin_frequency": ["lockin"],
    "set_lockin_current": ["lockin"],
    "close_channel": ["switch"],
    "open_all_channels": ["switch"],
    "configure_channel": ["switch"],
}

# Minimum positional args
MIN_POSITIONAL: dict[str, int] = {
    "set_dyna_field": 3,      # field rate approach
    "set_dyna_temp": 3,       # temp rate approach
    "set_helmholtz_field": 2, # field rate
    "scan_dyna_field": 5,     # start end step rate approach
    "scan_dyna_temp": 5,      # start end step rate approach
    "sweep_dyna_field": 3,    # start end rate
    "sweep_dyna_temp": 3,     # start end rate
    "scan_helmholtz_field": 4, # start end step rate
    "sweep_helmholtz_field": 3, # start end rate (gap_time optional)
    "close_channel": 1,       # channel_num
    "configure_channel": 5,   # channel ip vp vm im
    "set_lockin_time_constant": 1,  # seconds
    "set_lockin_sensitivity": 1,  # index (0..26)
    "set_lockin_filter": 1,   # db_oct
    "set_lockin_frequency": 1, # freq_hz
    "set_lockin_current": 1,  # current_A
    "set_ppms_field_and_fix_hall": 2, # field_Oe target_hall_G
    "scan_ppms_field_and_fix_hall": 4, # start end step target_hall_G
    "full_measure": 1,        # channel
    "continuous_full_measure": 0,
    "run_saved_script": 1,    # filename
    "wait_for": 2,            # event(s) + additional_time
    "time_sweep": 2,          # sweep_time_s time_gap_s
    "for_loop": 1,            # iterations
}


# Allowed keyword arguments per command (strict validation)
ALLOWED_KWARGS: dict[str, set[str]] = {
    "initialize_data_file": {"directory", "filename", "append"},
    "measure_hall_field": {
        "current", "nplc", "compliance_v", "voltage_range", "filter_count", "tbm",
    },
    "continuous_measure_hall_field": {
        "current", "nplc", "compliance_v", "voltage_range", "filter_count", "tbm",
    },
    "enable_hall_output": {
        "current", "compliance_v",
    },
    "measure_lockin": {
        "channel", "what", "current", "series_resistance", "avg", "start_sens",
        "use_autorange", "use_autophase", "sample_delay",
    },
    "continuous_measure_lockin": {
        "channel", "what", "avg", "sample_delay",
    },
    "full_measure": {
        "time_between",
        "hall_current", "hall_nplc", "hall_compliance",
        "hall_voltage_range", "hall_filter", "hall_excitation", "tbm",
        "lockin_what", "lockin_current", "lockin_series_resistance", "lockin_avg",
        "lockin_start_sens", "lockin_use_autorange", "lockin_use_autophase", "lockin_sample_delay",
    },
    "continuous_full_measure": {
        "time_between",
        "hall_nplc", "hall_compliance", "hall_voltage_range", "hall_filter",
        "lockin_what", "lockin_avg", "lockin_use_autorange", "lockin_use_autophase", "lockin_sample_delay",
    },
    "set_lockin_current": {"series_resistance"},
    "set_ppms_field_and_fix_hall": {"helmholtz_rate", "max_current_change"},
    "scan_ppms_field_and_fix_hall": {"rate", "helmholtz_rate", "max_current_change"},
    "sweep_dyna_field": {"gap_time"},
    "sweep_dyna_temp": {"gap_time"},
    "sweep_helmholtz_field": {"gap_time"},
}


# ============================================================================
# Parser
# ============================================================================
class ScriptParser:
    """Parse a multi-line script string into a list of ParsedCommands."""

    def parse(self, script_text: str) -> list[ParsedCommand]:
        """
        Parse script text into a list of ParsedCommand objects.

        Handles:
        - Comments (lines starting with #)
        - Blank lines
        - Indented sub-commands for loop commands
        - key=value and positional arguments
        """
        lines = script_text.splitlines()

        def _parse_block(start_index: int, parent_indent: int | None) -> tuple[list[ParsedCommand], int]:
            commands: list[ParsedCommand] = []
            i = start_index

            while i < len(lines):
                line = lines[i]
                stripped = line.strip()

                if not stripped or stripped.startswith("#"):
                    i += 1
                    continue

                indent = len(line) - len(line.lstrip())
                if parent_indent is not None and indent <= parent_indent:
                    break

                cmd = self._parse_line(stripped, i + 1, indent)
                i += 1

                if cmd.name in LOOP_COMMANDS:
                    children, i = _parse_block(i, indent)
                    cmd.children = children

                commands.append(cmd)

            return commands, i

        commands, _ = _parse_block(0, None)
        return commands

    def _parse_line(self, stripped: str, line_number: int, indent: int = 0) -> ParsedCommand:
        """Parse a single stripped line into a ParsedCommand."""
        parts = stripped.split()
        name = parts[0].lower() if parts else ""
        args: list[str] = []
        kwargs: dict[str, str] = {}
        has_multiple_commands = False

        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                kwargs[key.lower()] = value
            else:
                token = part.strip().lower()
                if name not in {"add_note"} and token in VALID_COMMANDS:
                    has_multiple_commands = True
                args.append(part)

        return ParsedCommand(
            name=name,
            args=args,
            kwargs=kwargs,
            line_number=line_number,
            raw=stripped,
            indent=indent,
            has_multiple_commands=has_multiple_commands,
        )


# ============================================================================
# Validator
# ============================================================================
@dataclass
class ValidationError:
    """A single validation error."""

    line_number: int
    message: str
    severity: str = "error"  # "error" or "warning"


class ScriptValidator:
    """
    Validate parsed commands against known signatures.

    Produces a list of ValidationError objects.
    """

    def validate(
        self,
        commands: list[ParsedCommand],
        connected_instruments: set[str] | None = None,
        _in_loop_children: bool = False,
        _loop_depth: int = 0,
    ) -> list[ValidationError]:
        """
        Validate a list of parsed commands.

        Parameters
        ----------
        commands : list[ParsedCommand]
            Parsed commands to validate.
        connected_instruments : set[str], optional
            Currently connected instrument names.  If provided, instrument
            requirements are checked.

        Returns
        -------
        list[ValidationError]
            List of validation errors/warnings.
        """
        errors: list[ValidationError] = []

        for cmd in commands:
            if not _in_loop_children and cmd.indent > 0:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="Indented command is only allowed as a sub-command of a loop",
                ))

            # Check command name
            if cmd.name not in VALID_COMMANDS:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"Unknown command: '{cmd.name}'",
                ))
                continue

            if cmd.has_multiple_commands:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="Line appears to contain multiple commands; use exactly one command per line",
                ))

            loop_depth = _loop_depth + 1 if cmd.name in LOOP_COMMANDS else _loop_depth
            if loop_depth > MAX_LOOP_NESTING:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=(
                        f"Loop nesting exceeds maximum depth of {MAX_LOOP_NESTING} "
                        f"(found depth {loop_depth})"
                    ),
                ))

            # Check minimum positional args
            min_args = MIN_POSITIONAL.get(cmd.name, 0)
            if len(cmd.args) < min_args:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=(
                        f"'{cmd.name}' requires at least {min_args} "
                        f"positional argument(s), got {len(cmd.args)}"
                    ),
                ))

            # Check instrument requirements
            if connected_instruments is not None:
                required = INSTRUMENT_REQUIREMENTS.get(cmd.name, [])
                # Map canonical names
                name_map = {
                    "helmholtz": "keithley2600",
                    "hall": "keithley2450",
                }
                for req in required:
                    canonical = name_map.get(req, req)
                    if canonical not in connected_instruments:
                        errors.append(ValidationError(
                            line_number=cmd.line_number,
                            message=f"'{cmd.name}' requires '{req}' but it's not connected",
                            severity="error",
                        ))

            # Validate loop commands have children
            if cmd.name in LOOP_COMMANDS and not cmd.children:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"Loop command '{cmd.name}' has no indented sub-commands",
                    severity="warning",
                ))

            # Recursively validate children
            if cmd.children:
                child_errors = self.validate(
                    cmd.children,
                    connected_instruments,
                    _in_loop_children=True,
                    _loop_depth=loop_depth,
                )
                errors.extend(child_errors)

            # Type-check numeric arguments
            self._validate_numeric_args(cmd, errors)

            # Strict kwarg schema validation
            self._validate_unknown_kwargs(cmd, errors)

            # wait_for semantic validation
            if cmd.name == "wait_for":
                self._validate_wait_for(cmd, errors)

            # Command-specific enumerated options
            self._validate_choice_args(cmd, errors)

        return errors

    def _validate_numeric_args(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        """Validate that expected numeric args are actually numeric."""
        numeric_commands = {
            "set_dyna_field": [0, 1],      # field, rate
            "set_dyna_temp": [0, 1],       # temp, rate
            "set_helmholtz_field": [0, 1],  # field, rate
            "scan_dyna_field": [0, 1, 2, 3],
            "scan_dyna_temp": [0, 1, 2, 3],
            "scan_helmholtz_field": [0, 1, 2, 3],
            "sweep_dyna_field": [0, 1, 2],
            "sweep_dyna_temp": [0, 1, 2],
            "sweep_helmholtz_field": [0, 1, 2],
            "set_lockin_time_constant": [0],
            "set_lockin_sensitivity": [0],
            "set_lockin_filter": [0],
            "set_lockin_frequency": [0],
            "set_lockin_current": [0],
            "set_ppms_field_and_fix_hall": [0, 1],
            "scan_ppms_field_and_fix_hall": [0, 1, 2, 3],
            "time_sweep": [0, 1],
            "for_loop": [0],
        }

        positions = numeric_commands.get(cmd.name, [])
        for pos in positions:
            if pos < len(cmd.args):
                try:
                    float(cmd.args[pos])
                except ValueError:
                    errors.append(ValidationError(
                        line_number=cmd.line_number,
                        message=(
                            f"'{cmd.name}' argument {pos + 1} "
                            f"('{cmd.args[pos]}') is not a number"
                        ),
                    ))

        if cmd.name == "close_channel" and cmd.args:
            token = cmd.args[0].strip().lower()
            if token not in _CHANNEL_SET:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'close_channel' argument 1 must be channel name ({_CHANNEL_LIST_TEXT})",
                ))

    def _validate_unknown_kwargs(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        """Reject unknown kwargs for commands with explicit schemas."""
        allowed = ALLOWED_KWARGS.get(cmd.name)
        if allowed is None:
            if cmd.kwargs:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'{cmd.name}' does not accept keyword arguments: {', '.join(sorted(cmd.kwargs))}",
                ))
            return

        unknown = sorted(k for k in cmd.kwargs if k not in allowed)
        if unknown:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message=f"'{cmd.name}' unknown keyword argument(s): {', '.join(unknown)}",
            ))

    def _validate_wait_for(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        """Validate wait_for event names and duration placement."""
        if not cmd.args:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'wait_for' requires at least one event and a duration",
            ))
            return

        try:
            float(cmd.args[-1])
        except ValueError:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'wait_for' last argument must be a numeric duration (seconds)",
            ))
            return

        raw_events = cmd.args[:-1]
        if not raw_events:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'wait_for' requires at least one event before duration",
            ))
            return

        events: list[str] = []
        for token in raw_events:
            events.extend([part.strip().lower() for part in token.split(",") if part.strip()])

        allowed = {
            "temp", "field", "helmholtz", "no_event", "all",
            "temp_stable", "field_stable", "dyna_ready",
            "helmholtz_field", "helmholtz_stable",
        }
        unknown = [event for event in events if event not in allowed]
        if unknown:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message=f"'wait_for' unknown event(s): {', '.join(sorted(set(unknown)))}",
            ))

        if "no_event" in events and len(set(events)) > 1:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'wait_for' cannot mix 'no_event' with other events",
            ))

    def _validate_choice_args(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        """Validate enum-like string arguments for known commands."""
        if cmd.name == "set_dyna_temp" and len(cmd.args) >= 3:
            approach = cmd.args[2].strip().lower()
            if approach not in {"fast_settle", "fast", "no_overshoot"}:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=(
                        "'set_dyna_temp' approach must be one of "
                        "fast_settle, fast, no_overshoot"
                    ),
                ))

        elif cmd.name == "set_dyna_field" and len(cmd.args) >= 3:
            approach = cmd.args[2].strip().lower()
            if approach not in {"linear", "no_overshoot", "oscillate"}:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=(
                        "'set_dyna_field' approach must be one of "
                        "linear, no_overshoot, oscillate"
                    ),
                ))

        elif cmd.name == "set_lockin_filter" and len(cmd.args) >= 1:
            try:
                db_oct = int(float(cmd.args[0]))
            except Exception:
                return
            if db_oct not in {6, 12, 18, 24}:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'set_lockin_filter' must be one of: 6, 12, 18, 24",
                ))

        elif cmd.name == "set_lockin_time_constant" and len(cmd.args) >= 1:
            try:
                tau = float(cmd.args[0])
            except Exception:
                return
            if tau <= 0:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'set_lockin_time_constant' must be > 0 seconds",
                ))

        elif cmd.name == "set_lockin_sensitivity" and len(cmd.args) >= 1:
            try:
                sens_idx = int(float(cmd.args[0]))
            except Exception:
                return
            if sens_idx < 0 or sens_idx > 26:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'set_lockin_sensitivity' must be an integer index in range 0..26",
                ))

        elif cmd.name == "full_measure" and len(cmd.args) >= 1:
            ch = cmd.args[0].strip().lower()
            if ch not in _CHANNEL_SET:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'{cmd.name}' argument 1 must be channel name ({_CHANNEL_LIST_TEXT})",
                ))
            self._validate_full_measure_kwargs(cmd, errors)

        elif cmd.name == "continuous_full_measure":
            if cmd.args:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'continuous_full_measure' takes no positional arguments",
                ))
            self._validate_continuous_full_measure_kwargs(cmd, errors)

        elif cmd.name == "configure_channel":
            if cmd.args:
                ch = cmd.args[0].strip().lower()
                if ch not in _CHANNEL_SET:
                    errors.append(ValidationError(
                        line_number=cmd.line_number,
                        message=f"'configure_channel' argument 1 must be channel name ({_CHANNEL_LIST_TEXT})",
                    ))
            if len(cmd.args) >= 5:
                pins: list[int] = []
                for idx in range(1, 5):
                    token = cmd.args[idx]
                    try:
                        pin = int(token)
                    except Exception:
                        errors.append(ValidationError(
                            line_number=cmd.line_number,
                            message=f"'configure_channel' pin argument {idx + 1} ('{token}') must be an integer",
                        ))
                        return
                    if pin < 1 or pin > 8:
                        errors.append(ValidationError(
                            line_number=cmd.line_number,
                            message=f"'configure_channel' pin argument {idx + 1} must be in range 1-8",
                        ))
                    pins.append(pin)
                if len(set(pins)) != len(pins):
                    errors.append(ValidationError(
                        line_number=cmd.line_number,
                        message="'configure_channel' pins must be unique",
                    ))

        elif cmd.name in {"measure_hall_field", "continuous_measure_hall_field"}:
            vr_token = cmd.kwargs.get("voltage_range")
            if vr_token is not None:
                if not self._is_valid_voltage_range_token(vr_token):
                    errors.append(ValidationError(
                        line_number=cmd.line_number,
                        message=(
                            f"'{cmd.name} voltage_range' must be 'auto' or a numeric value "
                            "with optional V/mV suffix"
                        ),
                    ))

        elif cmd.name == "measure_lockin":
            self._validate_lockin_measure_kwargs(cmd, errors, continuous=False)

        elif cmd.name == "continuous_measure_lockin":
            self._validate_lockin_measure_kwargs(cmd, errors, continuous=True)

        elif cmd.name == "scan_helmholtz_field" and len(cmd.args) > 4:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'scan_helmholtz_field' accepts exactly 4 positional arguments (start, end, step, rate)",
            ))

    def _validate_lockin_measure_kwargs(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
        *,
        continuous: bool,
    ) -> None:
        what = cmd.kwargs.get("what")
        if what is not None:
            allowed = {"x", "y", "r", "theta"}
            tokens = [t.strip().lower() for t in what.split(",") if t.strip()]
            invalid = sorted(set(t for t in tokens if t not in allowed))
            if invalid:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'{cmd.name} what' unknown parameter(s): {', '.join(invalid)}",
                ))

        bool_keys = ["use_autorange", "use_autophase"] if not continuous else []
        for key in bool_keys:
            if key in cmd.kwargs:
                token = cmd.kwargs[key].strip().lower()
                if token not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                    errors.append(ValidationError(
                        line_number=cmd.line_number,
                        message=f"'{cmd.name} {key}' must be a boolean token (true/false)",
                    ))


    def _validate_continuous_full_measure_kwargs(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        what = cmd.kwargs.get("lockin_what")
        if what is not None:
            allowed = {"x", "y", "r", "theta"}
            tokens = [t.strip().lower() for t in what.split(",") if t.strip()]
            invalid = sorted(set(t for t in tokens if t not in allowed))
            if invalid:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'continuous_full_measure lockin_what' unknown parameter(s): "
                    + ", ".join(invalid),
                ))

        vr_token = cmd.kwargs.get("hall_voltage_range")
        if vr_token is not None and not self._is_valid_voltage_range_token(vr_token):
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message=(
                    "'continuous_full_measure hall_voltage_range' must be 'auto' "
                    "or a numeric value with optional V/mV suffix"
                ),
            ))

        for key in ("lockin_use_autorange", "lockin_use_autophase"):
            if key not in cmd.kwargs:
                continue
            token = cmd.kwargs[key].strip().lower()
            if token not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'continuous_full_measure {key}' must be a boolean token (true/false)",
                ))

    def _validate_full_measure_kwargs(
        self,
        cmd: ParsedCommand,
        errors: list[ValidationError],
    ) -> None:
        what = cmd.kwargs.get("lockin_what")
        if what is not None:
            allowed = {"x", "y", "r", "theta"}
            tokens = [t.strip().lower() for t in what.split(",") if t.strip()]
            invalid = sorted(set(t for t in tokens if t not in allowed))
            if invalid:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message="'full_measure lockin_what' unknown parameter(s): "
                    + ", ".join(invalid),
                ))

        vr_token = cmd.kwargs.get("hall_voltage_range")
        if vr_token is not None and not self._is_valid_voltage_range_token(vr_token):
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message=(
                    "'full_measure hall_voltage_range' must be 'auto' "
                    "or a numeric value with optional V/mV suffix"
                ),
            ))

        hall_excitation = cmd.kwargs.get("hall_excitation")
        if hall_excitation is not None and hall_excitation.strip().lower() not in {"cycle", "keep"}:
            errors.append(ValidationError(
                line_number=cmd.line_number,
                message="'full_measure hall_excitation' must be one of: cycle, keep",
            ))

        for key in ("lockin_use_autorange", "lockin_use_autophase"):
            if key not in cmd.kwargs:
                continue
            token = cmd.kwargs[key].strip().lower()
            if token not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                errors.append(ValidationError(
                    line_number=cmd.line_number,
                    message=f"'full_measure {key}' must be a boolean token (true/false)",
                ))

    @staticmethod
    def _is_valid_voltage_range_token(token: str) -> bool:
        text = str(token).strip().lower()
        if text == "auto":
            return True
        try:
            if text.endswith("mv"):
                float(text[:-2])
                return True
            if text.endswith("v"):
                float(text[:-1])
                return True
            float(text)
            return True
        except Exception:
            return False

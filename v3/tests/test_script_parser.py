"""
Tests for v3.core.script_parser
"""

from __future__ import annotations

import unittest

from v3.core.script_parser import (
    LOOP_COMMANDS,
    VALID_COMMANDS,
    ParsedCommand,
    ScriptParser,
    ScriptValidator,
    ValidationError,
)


class TestParsedCommand(unittest.TestCase):
    def test_get_float(self):
        cmd = ParsedCommand(name="test", kwargs={"rate": "10.5"})
        self.assertAlmostEqual(cmd.get_float("rate"), 10.5)
        self.assertIsNone(cmd.get_float("missing"))
        self.assertAlmostEqual(cmd.get_float("missing", 1.0), 1.0)

    def test_get_int(self):
        cmd = ParsedCommand(name="test", kwargs={"count": "20"})
        self.assertEqual(cmd.get_int("count"), 20)

    def test_get_bool(self):
        cmd = ParsedCommand(name="test", kwargs={"auto": "true", "skip": "false"})
        self.assertTrue(cmd.get_bool("auto"))
        self.assertFalse(cmd.get_bool("skip"))
        self.assertTrue(cmd.get_bool("missing", True))

    def test_get_tuple(self):
        cmd = ParsedCommand(name="test", kwargs={"what": "X,Y,R"})
        self.assertEqual(cmd.get_tuple("what"), ("X", "Y", "R"))

    def test_get_str(self):
        cmd = ParsedCommand(name="test", kwargs={"approach": "linear"})
        self.assertEqual(cmd.get_str("approach"), "linear")


class TestScriptParser(unittest.TestCase):
    def setUp(self):
        self.parser = ScriptParser()

    def test_parse_simple_command(self):
        cmds = self.parser.parse("test\n")
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].name, "test")

    def test_parse_command_with_args(self):
        cmds = self.parser.parse("set_dyna_field 1000 100 linear\n")
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].name, "set_dyna_field")
        self.assertEqual(cmds[0].args, ["1000", "100", "linear"])

    def test_parse_command_with_kwargs(self):
        cmds = self.parser.parse("measure_lockin current=0.001 avg=20\n")
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].kwargs["current"], "0.001")
        self.assertEqual(cmds[0].kwargs["avg"], "20")

    def test_parse_mixed_args_kwargs(self):
        cmds = self.parser.parse("full_measure a hall_current=1.0\n")
        self.assertEqual(cmds[0].args, ["a"])
        self.assertEqual(cmds[0].kwargs["hall_current"], "1.0")

    def test_skip_comments(self):
        script = "# This is a comment\ntest\n# Another comment\n"
        cmds = self.parser.parse(script)
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].name, "test")

    def test_skip_blank_lines(self):
        script = "\n\ntest\n\n\nauto_gain\n\n"
        cmds = self.parser.parse(script)
        self.assertEqual(len(cmds), 2)

    def test_parse_loop_command(self):
        script = (
            "scan_dyna_field 0 1000 100 10 linear\n"
            "    measure_lockin current=0.001\n"
            "    auto_gain\n"
            "test\n"
        )
        cmds = self.parser.parse(script)
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0].name, "scan_dyna_field")
        self.assertEqual(len(cmds[0].children), 2)
        self.assertEqual(cmds[0].children[0].name, "measure_lockin")
        self.assertEqual(cmds[0].children[1].name, "auto_gain")
        self.assertEqual(cmds[1].name, "test")

    def test_parse_multiple_loops(self):
        script = (
            "scan_dyna_field 0 1000 100 10 linear\n"
            "    measure_lockin\n"
            "scan_dyna_temp 300 400 10 5 fast\n"
            "    full_measure a\n"
        )
        cmds = self.parser.parse(script)
        self.assertEqual(len(cmds), 2)
        self.assertEqual(len(cmds[0].children), 1)
        self.assertEqual(len(cmds[1].children), 1)

    def test_parse_nested_loop_commands(self):
        script = (
            "scan_dyna_field -140000 140000 10000 50 linear\n"
            "  sweep_helmholtz_field -500 500 100 gap_time=2\n"
            "    continuous_measure_hall_field current=2 compliance_v=20 tbm=1\n"
            "  disable_hall_output\n"
        )
        cmds = self.parser.parse(script)

        self.assertEqual(len(cmds), 1)
        outer = cmds[0]
        self.assertEqual(outer.name, "scan_dyna_field")
        self.assertEqual(len(outer.children), 2)

        inner_loop = outer.children[0]
        self.assertEqual(inner_loop.name, "sweep_helmholtz_field")
        self.assertEqual(len(inner_loop.children), 1)
        self.assertEqual(inner_loop.children[0].name, "continuous_measure_hall_field")

        self.assertEqual(outer.children[1].name, "disable_hall_output")

    def test_case_insensitive_command_names(self):
        cmds = self.parser.parse("Set_Dyna_Field 1000 100 linear\n")
        self.assertEqual(cmds[0].name, "set_dyna_field")

    def test_line_numbers(self):
        script = "# comment\ntest\n\nauto_gain\n"
        cmds = self.parser.parse(script)
        self.assertEqual(cmds[0].line_number, 2)
        self.assertEqual(cmds[1].line_number, 4)

    def test_empty_script(self):
        cmds = self.parser.parse("")
        self.assertEqual(len(cmds), 0)

    def test_comments_only_script(self):
        cmds = self.parser.parse("# just comments\n# nothing else\n")
        self.assertEqual(len(cmds), 0)


class TestScriptValidator(unittest.TestCase):
    def setUp(self):
        self.parser = ScriptParser()
        self.validator = ScriptValidator()

    def test_valid_simple_commands(self):
        cmds = self.parser.parse("test\nauto_gain\nauto_phase\n")
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 0)

    def test_unknown_command(self):
        cmds = self.parser.parse("nonexistent_command\n")
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 1)
        self.assertIn("Unknown command", errors[0].message)

    def test_missing_positional_args(self):
        cmds = self.parser.parse("set_dyna_field 1000\n")
        errors = self.validator.validate(cmds)
        error_msgs = [e.message for e in errors]
        self.assertTrue(any("positional" in m for m in error_msgs))

    def test_sufficient_positional_args(self):
        cmds = self.parser.parse("set_dyna_field 1000 100 linear\n")
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 0)

    def test_instrument_requirement_check(self):
        connected = {"lockin", "switch"}
        cmds = self.parser.parse("set_dyna_field 1000 100 linear\n")
        errors = self.validator.validate(cmds, connected)
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertTrue(any("dyna" in e.message for e in hard_errors))

    def test_instrument_connected_no_warning(self):
        connected = {"dyna"}
        cmds = self.parser.parse("set_dyna_field 1000 100 linear\n")
        errors = self.validator.validate(cmds, connected)
        # Should have no instrument warnings
        inst_warnings = [e for e in errors if "not connected" in e.message]
        self.assertEqual(len(inst_warnings), 0)

    def test_loop_without_children_warning(self):
        # Parse a loop command followed by a top-level command
        cmds = self.parser.parse("scan_dyna_field 0 1000 100 10 linear\ntest\n")
        errors = self.validator.validate(cmds)
        warnings = [e for e in errors if e.severity == "warning"]
        self.assertTrue(any("sub-commands" in w.message for w in warnings))

    def test_loop_with_children_no_warning(self):
        script = (
            "scan_dyna_field 0 1000 100 10 linear\n"
            "    measure_lockin\n"
        )
        cmds = self.parser.parse(script)
        errors = self.validator.validate(cmds)
        child_warnings = [e for e in errors if "sub-commands" in e.message]
        self.assertEqual(len(child_warnings), 0)

    def test_numeric_arg_validation(self):
        cmds = self.parser.parse("set_dyna_field abc 100 linear\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("not a number" in e.message for e in errors))

    def test_valid_numeric_args(self):
        cmds = self.parser.parse("set_helmholtz_field 100 10\n")
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 0)

    def test_close_channel_alias_valid(self):
        cmds = self.parser.parse("close_channel a\n")
        errors = self.validator.validate(cmds)
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertEqual(len(hard_errors), 0)

    def test_close_channel_numeric_invalid(self):
        cmds = self.parser.parse("close_channel 3\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("must be channel name" in e.message for e in errors))

    def test_sweep_helmholtz_field_accepts_optional_gap_time(self):
        cmds = self.parser.parse("sweep_helmholtz_field 0 500 10\n")
        errors = self.validator.validate(cmds)
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertEqual(len(hard_errors), 0)
        self.assertFalse(any("requires at least" in e.message for e in errors))

    def test_children_validated(self):
        script = (
            "scan_dyna_field 0 1000 100 10 linear\n"
            "    nonexistent_cmd\n"
        )
        cmds = self.parser.parse(script)
        errors = self.validator.validate(cmds)
        self.assertTrue(any("Unknown command" in e.message for e in errors))

    def test_wait_for_alias_event_is_valid(self):
        cmds = self.parser.parse("wait_for dyna_ready 2\n")
        errors = self.validator.validate(cmds)
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertEqual(len(hard_errors), 0)

    def test_wait_for_unknown_event_errors(self):
        cmds = self.parser.parse("wait_for not_an_event 2\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("unknown event" in e.message for e in errors))

    def test_wait_for_requires_numeric_duration(self):
        cmds = self.parser.parse("wait_for temp not_a_number\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("numeric duration" in e.message for e in errors))

    def test_wait_for_no_event_cannot_mix(self):
        cmds = self.parser.parse("wait_for temp no_event 2\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("cannot mix 'no_event'" in e.message for e in errors))

    def test_set_dyna_temp_invalid_approach_errors(self):
        cmds = self.parser.parse("set_dyna_temp 300 2 fast_settel\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("approach must be one of" in e.message for e in errors))

    def test_indented_command_outside_loop_errors(self):
        cmds = self.parser.parse("    measure_lockin\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("Indented command" in e.message for e in errors))

    def test_mixed_top_level_then_indented_non_child_errors(self):
        script = (
            "test\n"
            "    measure_hall_field\n"
        )
        cmds = self.parser.parse(script)
        errors = self.validator.validate(cmds)
        self.assertTrue(any("Indented command" in e.message for e in errors))

    def test_multiple_commands_in_single_line_errors(self):
        cmds = self.parser.parse("test auto_gain\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("multiple commands" in e.message for e in errors))

    def test_add_note_can_contain_command_words(self):
        cmds = self.parser.parse("add_note test auto_gain full_measure\n")
        errors = self.validator.validate(cmds)
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertEqual(len(hard_errors), 0)

    def test_unknown_kwarg_rejected(self):
        cmds = self.parser.parse("measure_hall_field bogus=1\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("unknown keyword argument" in e.message for e in errors))

    def test_unknown_kwarg_rejected_for_enable_hall_output(self):
        cmds = self.parser.parse("enable_hall_output bogus=1\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("unknown keyword argument" in e.message for e in errors))

    def test_command_without_kwargs_rejects_any_kwarg(self):
        cmds = self.parser.parse("auto_gain x=1\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("does not accept keyword arguments" in e.message for e in errors))

    def test_configure_channel_pin_range_and_unique(self):
        cmds = self.parser.parse("configure_channel a 1 2 9 4\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("range 1-8" in e.message for e in errors))

        cmds = self.parser.parse("configure_channel a 1 2 2 4\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("pins must be unique" in e.message for e in errors))

    def test_measure_hall_voltage_range_choice(self):
        cmds = self.parser.parse("measure_hall_field voltage_range=2V\n")
        errors = self.validator.validate(cmds)
        self.assertFalse(any("voltage_range" in e.message for e in errors))

    def test_continuous_measure_hall_voltage_range_choice(self):
        cmds = self.parser.parse("continuous_measure_hall_field voltage_range=100mV\n")
        errors = self.validator.validate(cmds)
        self.assertFalse(any("voltage_range" in e.message for e in errors))

    def test_continuous_measure_hall_invalid_voltage_range(self):
        cmds = self.parser.parse("continuous_measure_hall_field voltage_range=abcV\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("voltage_range" in e.message for e in errors))

    def test_new_hall_output_commands_valid(self):
        cmds = self.parser.parse(
            "enable_hall_output current=1.0 compliance_v=2\n"
            "continuous_measure_hall_field current=1.0 nplc=1 compliance_v=2 voltage_range=auto filter_count=3 tbm=0.2\n"
            "disable_hall_output\n"
        )
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 0)

    def test_set_lockin_filter_must_be_supported_value(self):
        cmds = self.parser.parse("set_lockin_filter 30\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("must be one of: 6, 12, 18, 24" in e.message for e in errors))

    def test_full_measure_channel_validation(self):
        cmds = self.parser.parse("full_measure z\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("must be channel name" in e.message for e in errors))

    def test_measure_lockin_what_validation(self):
        cmds = self.parser.parse("measure_lockin what=X,Q\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("unknown parameter" in e.message for e in errors))

    def test_continuous_measure_lockin_excitation_validation(self):
        cmds = self.parser.parse("continuous_measure_lockin excitation=toggle\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("must be one of: on, off, keep" in e.message for e in errors))

    def test_scan_helmholtz_field_rejects_approach_argument(self):
        cmds = self.parser.parse("scan_helmholtz_field 0 500 50 10 linear\n")
        errors = self.validator.validate(cmds)
        self.assertTrue(any("accepts exactly 4 positional arguments" in e.message for e in errors))

    def test_loop_nesting_depth_of_five_is_allowed(self):
        script = (
            "scan_dyna_field 0 10 1 1 linear\n"
            "  sweep_dyna_field 0 10 1\n"
            "    sweep_dyna_temp 0 10 1\n"
            "      sweep_helmholtz_field 0 10 1\n"
            "        scan_dyna_temp 0 10 1 1 fast_settle\n"
            "          test\n"
        )
        cmds = self.parser.parse(script)
        errors = self.validator.validate(cmds)
        self.assertFalse(any("Loop nesting exceeds maximum depth" in e.message for e in errors))

    def test_loop_nesting_depth_above_five_errors(self):
        script = (
            "scan_dyna_field 0 10 1 1 linear\n"
            "  sweep_dyna_field 0 10 1\n"
            "    sweep_dyna_temp 0 10 1\n"
            "      sweep_helmholtz_field 0 10 1\n"
            "        scan_dyna_temp 0 10 1 1 fast_settle\n"
            "          scan_helmholtz_field 0 10 1 1\n"
            "            test\n"
        )
        cmds = self.parser.parse(script)
        errors = self.validator.validate(cmds)
        self.assertTrue(any("Loop nesting exceeds maximum depth" in e.message for e in errors))


class TestValidCommands(unittest.TestCase):
    def test_all_loop_commands_are_valid(self):
        for cmd in LOOP_COMMANDS:
            self.assertIn(cmd, VALID_COMMANDS)

    def test_minimum_expected_commands(self):
        expected = [
            "test", "initialize_data_file", "set_dyna_field",
            "set_helmholtz_field", "measure_lockin", "full_measure",
            "auto_gain", "wait_for", "continuous_measure_hall_field",
            "enable_hall_output", "disable_hall_output",
        ]
        for cmd in expected:
            self.assertIn(cmd, VALID_COMMANDS)


class TestComplexScripts(unittest.TestCase):
    def setUp(self):
        self.parser = ScriptParser()
        self.validator = ScriptValidator()

    def test_realistic_script(self):
        script = """
# Initialize data file
initialize_data_file

# Set temperature
set_dyna_temp 300 10 fast

# Wait for stability
wait_for temp 10

# Scan Helmholtz field
scan_helmholtz_field 0 500 50 10
    measure_lockin current=0.001 avg=20
    full_measure a hall_current=1.0

# Final measurement
auto_gain
measure_lockin current=0.001
"""
        cmds = self.parser.parse(script)
        self.assertEqual(len(cmds), 6)

        # The scan should have 2 children
        scan_cmd = cmds[3]
        self.assertEqual(scan_cmd.name, "scan_helmholtz_field")
        self.assertEqual(len(scan_cmd.children), 2)

        # Validate
        errors = self.validator.validate(cmds)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()

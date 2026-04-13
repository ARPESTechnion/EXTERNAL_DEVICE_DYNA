from __future__ import annotations

import unittest

from Utility.Keithley7001 import MockKeithley7001


class TestMockKeithley7001(unittest.TestCase):
    def test_open_all_clears_channels(self) -> None:
        sw = MockKeithley7001()
        sw.closed_channels = {"1", "2"}
        sw.open_all()
        self.assertEqual(sw.closed_channels, set())

    def test_close_list_sets_columns(self) -> None:
        sw = MockKeithley7001()
        sw.close_list(1, 2, 3, 4)
        self.assertEqual(sw.closed_channels, {"1", "2", "3", "4"})

    def test_close_channel_uses_single_column(self) -> None:
        sw = MockKeithley7001()
        sw.close_channel(6)
        self.assertEqual(sw.closed_channels, {"6"})

    def test_invalid_column_raises(self) -> None:
        sw = MockKeithley7001()
        with self.assertRaises(ValueError):
            sw.close_list(-1, 0, 0, 0)

        with self.assertRaises(ValueError):
            sw.close_list(9, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()

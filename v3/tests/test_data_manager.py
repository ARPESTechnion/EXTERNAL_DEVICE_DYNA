"""Tests for v3.core.data_manager."""

import csv
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from v3.core.data_manager import DataManager
from v3.core.constants import CSV_FIELDNAMES, AUTO_LOG_FIELDNAMES


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def tmp_log_dir(tmp_path):
    """Provide a temporary log directory."""
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def dm(tmp_data_dir, tmp_log_dir):
    """DataManager with temporary directories."""
    mgr = DataManager(data_dir=tmp_data_dir, log_dir=tmp_log_dir)
    yield mgr
    mgr.close()


# ---------------------------------------------------------------------------
# File initialization
# ---------------------------------------------------------------------------
class TestInitializeFile:
    def test_auto_increment(self, dm, tmp_data_dir):
        path = dm.initialize_file()
        assert path is not None
        assert path.exists()
        assert path.parent == tmp_data_dir
        assert path.name.startswith("Data_")
        assert path.name.endswith("_001.csv")

    def test_auto_increment_sequential(self, dm, tmp_data_dir):
        p1 = dm.initialize_file()
        # Close first so second can open
        dm.close()
        p2 = dm.initialize_file()
        # Empty new files are cleaned up on close, so numbering restarts.
        assert p1 == p2
        assert "_001.csv" in p1.name
        assert "_001.csv" in p2.name

    def test_explicit_filename(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="my_data")
        assert path.name == "my_data.csv"

    def test_explicit_filename_with_csv(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="my_data.csv")
        assert path.name == "my_data.csv"

    def test_numbered_variant_on_conflict(self, dm, tmp_data_dir):
        # Create first file
        p1 = dm.initialize_file(filename="test")
        dm.close()
        # Empty new files are cleaned up on close, so the same name is reused.
        p2 = dm.initialize_file(filename="test")
        assert p2.name == "test.csv"
        assert p1 == p2

    def test_custom_directory(self, dm, tmp_path):
        custom = tmp_path / "custom_data"
        path = dm.initialize_file(directory=str(custom))
        assert path.parent == custom
        assert custom.exists()

    def test_csv_header_matches_schema(self, dm, tmp_data_dir):
        path = dm.initialize_file()
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == CSV_FIELDNAMES

    def test_empty_new_file_removed_on_close(self, dm):
        path = dm.initialize_file(filename="empty_session")
        assert path.exists()
        dm.close()
        assert not path.exists()

    def test_session_header_row_written_when_enabled(self, dm):
        dm.configure_session_header(enabled=True, user="alice", sample="sample-7")
        path = dm.initialize_file(filename="with_meta")
        dm.write_row({"Time": 1.0, "Temp": 300.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert rows[0]["Measurement_Type"] == "SessionInfo"
        assert "Date:" in rows[0]["Notes"]
        assert "User: alice" in rows[0]["Notes"]
        assert "Sample: sample-7" in rows[0]["Notes"]
        assert rows[1]["Measurement_Type"] == "Full"


# ---------------------------------------------------------------------------
# Append mode
# ---------------------------------------------------------------------------
class TestAppendMode:
    def test_append_continues_from_existing(self, dm, tmp_data_dir):
        # Create initial file with some data
        dm.initialize_file(filename="append_test")
        dp = {"Time": 10.5, "Temp": 300.0}
        dm.write_row(dp)
        dm.close()

        # Reopen in append mode
        dm2 = DataManager(data_dir=tmp_data_dir)
        path = dm2.initialize_file(filename="append_test", append=True)
        assert path is not None
        assert dm2.time_offset == pytest.approx(10.5)
        dm2.close()

    def test_append_to_nonexistent_creates_new(self, dm, tmp_data_dir):
        # If file doesn't exist, append=True still creates it (falls through)
        path = dm.initialize_file(filename="new_file", append=True)
        assert path is not None
        assert path.exists()

    def test_append_empty_file_writes_header(self, dm, tmp_data_dir):
        target = tmp_data_dir / "empty_existing.csv"
        target.write_text("", encoding="utf-8")

        path = dm.initialize_file(filename="empty_existing.csv", append=True)
        assert path == target
        dm.write_row({"Time": 1.0, "Temp": 300.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert reader.fieldnames == CSV_FIELDNAMES
        assert len(rows) == 1

    def test_append_marks_first_new_row_with_timestamp_note(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="append_note_test")
        dm.write_row({"Time": 2.0, "Temp": 300.0}, measurement_type="Full")
        dm.close()

        dm2 = DataManager(data_dir=tmp_data_dir)
        dm2.initialize_file(filename="append_note_test", append=True)
        dm2.write_row({"Time": 3.0, "Temp": 301.0}, measurement_type="Full")
        dm2.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert "Data appended at" in rows[-1]["Notes"]

    def test_append_schema_mismatch_creates_numbered_variant(self, dm, tmp_data_dir):
        bad = tmp_data_dir / "bad_schema.csv"
        bad.write_text("A,B,C\n1,2,3\n", encoding="utf-8")

        new_path = dm.initialize_file(filename="bad_schema.csv", append=True)
        assert new_path is not None
        assert new_path != bad
        assert new_path.name == "bad_schema_001.csv"
        dm.close()


# ---------------------------------------------------------------------------
# Row writing
# ---------------------------------------------------------------------------
class TestWriteRow:
    def test_write_single_row(self, dm):
        dm.initialize_file()
        data_point = {
            "Time": 1.5,
            "Temp": 295.0,
            "In-plane_Field": 1000.0,
            "Channel": "a",
            "LockIn_X": 0.001,
            "LockIn_X_Error": 0.0001,
        }
        assert dm.write_row(data_point, measurement_type="LockIn") is True

    def test_written_row_readable(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="readable_test")
        dm.write_row({"Time": 2.0, "Temp": 300.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert float(rows[0]["Time(s)"]) == pytest.approx(2.0)
        assert float(rows[0]["Temp(K)"]) == pytest.approx(300.0)
        assert rows[0]["Measurement_Type"] == "Full"

    def test_missing_keys_become_nan(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="nan_test")
        dm.write_row({"Time": 1.0}, measurement_type="Test")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        # Most columns should be nan
        assert row["LockIn_X(V)"] == "nan"
        assert row["Time(s)"] == "1.0"

    def test_auto_initialize_on_first_write(self, dm):
        """If no file is initialized, write_row auto-creates one."""
        result = dm.write_row({"Time": 0.0}, measurement_type="Auto")
        assert result is True
        assert dm.data_filename is not None

    def test_note_attached_to_row(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="note_test")
        dm.set_note("test note")
        dm.write_row({"Time": 1.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert row["Notes"] == "test note"

    def test_note_cleared_after_write(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="note_clear")
        dm.set_note("one-time note")
        dm.write_row({"Time": 1.0}, measurement_type="Full")
        dm.write_row({"Time": 2.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["Notes"] == "one-time note"
        assert rows[1]["Notes"] == ""

    def test_all_data_keys_mapped(self, dm, tmp_data_dir):
        """Every key in DATA_KEY_TO_CSV should map to the correct column."""
        from v3.core.constants import DATA_KEY_TO_CSV

        path = dm.initialize_file(filename="all_keys")
        full_point = {k: 1.0 for k in DATA_KEY_TO_CSV.keys()}
        full_point["Time"] = 99.9
        dm.write_row(full_point, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        for internal_key, csv_col in DATA_KEY_TO_CSV.items():
            assert csv_col in row, f"Column {csv_col} not in CSV"
            val = float(row[csv_col])
            if internal_key == "Time":
                assert val == pytest.approx(99.9)
            else:
                assert val == pytest.approx(1.0)

    def test_write_100_rows(self, dm, tmp_data_dir):
        """Write 100 rows and verify all are persisted."""
        path = dm.initialize_file(filename="hundred")
        for i in range(100):
            dm.write_row({"Time": float(i), "Temp": 300.0 + i * 0.1},
                         measurement_type="Scan")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 100
        assert float(rows[0]["Time(s)"]) == pytest.approx(0.0)
        assert float(rows[99]["Time(s)"]) == pytest.approx(99.0)


class TestHallMetadataLogging:
    def test_no_hall_metadata_for_non_hall_measurement_types(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="hall_meta_non_hall")
        dm.set_hall_metadata(hall_bar="Wire Hall Bar 1", v_per_g=2.15e-5, hall_offset_v=0.001)
        dm.write_row({"Time": 1.0, "Temp": 300.0}, measurement_type="LockIn")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["Measurement_Type"] == "LockIn"
        assert "HallBar:" not in rows[0]["Notes"]

    def test_first_hall_write_emits_single_metadata_row(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="hall_meta_first")
        dm.set_hall_metadata(hall_bar="Wire Hall Bar 1", v_per_g=2.15e-5, hall_offset_v=0.001)
        dm.write_row({"Time": 1.0, "Hall_Field": 100.0}, measurement_type="Hall")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert rows[0]["Measurement_Type"] == "SessionInfo"
        assert "HallBar: Wire Hall Bar 1" in rows[0]["Notes"]
        assert "VperG:" in rows[0]["Notes"]
        assert "HallOffsetV:" in rows[0]["Notes"]
        assert "GperV" not in rows[0]["Notes"]
        assert "HallOffsetG" not in rows[0]["Notes"]
        assert rows[1]["Measurement_Type"] == "Hall"

    def test_hall_metadata_not_duplicated_without_changes(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="hall_meta_no_dup")
        dm.set_hall_metadata(hall_bar="Wire Hall Bar 2", v_per_g=2.10e-5, hall_offset_v=0.002)
        dm.write_row({"Time": 1.0}, measurement_type="Hall")
        dm.write_row({"Time": 2.0}, measurement_type="Full")
        dm.write_row({"Time": 3.0}, measurement_type="Hall")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        metadata_rows = [
            r for r in rows
            if r["Measurement_Type"] == "SessionInfo" and "HallBar:" in r["Notes"]
        ]
        assert len(metadata_rows) == 1

    def test_hall_metadata_re_emits_after_change(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="hall_meta_change")
        dm.set_hall_metadata(hall_bar="Wire Hall Bar 1", v_per_g=2.15e-5, hall_offset_v=0.001)
        dm.write_row({"Time": 1.0}, measurement_type="Hall")

        dm.set_hall_metadata(hall_bar="Wire Hall Bar 3", v_per_g=2.00e-5, hall_offset_v=0.004)
        dm.write_row({"Time": 2.0}, measurement_type="Full")
        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        metadata_rows = [
            r for r in rows
            if r["Measurement_Type"] == "SessionInfo" and "HallBar:" in r["Notes"]
        ]
        assert len(metadata_rows) == 2
        assert "HallBar: Wire Hall Bar 1" in metadata_rows[0]["Notes"]
        assert "HallBar: Wire Hall Bar 3" in metadata_rows[1]["Notes"]


# ---------------------------------------------------------------------------
# Results buffer
# ---------------------------------------------------------------------------
class TestResultsBuffer:
    def test_results_appended(self, dm):
        dm.initialize_file()
        dm.write_row({"Time": 1.0}, measurement_type="A")
        dm.write_row({"Time": 2.0}, measurement_type="B")
        assert dm.results_count == 2

    def test_results_bounded(self, tmp_data_dir, tmp_log_dir):
        dm = DataManager(data_dir=tmp_data_dir, log_dir=tmp_log_dir,
                         max_results=5)
        dm.initialize_file()
        for i in range(10):
            dm.write_row({"Time": float(i)}, measurement_type="T")
        assert dm.results_count == 5
        results = dm.get_results()
        # Oldest entries dropped; latest 5 remain
        assert results[0]["Time"] == 5.0
        assert results[4]["Time"] == 9.0
        dm.close()

    def test_get_results_returns_copy(self, dm):
        dm.initialize_file()
        dm.write_row({"Time": 1.0}, measurement_type="T")
        r1 = dm.get_results()
        r2 = dm.get_results()
        assert r1 is not r2
        assert r1 == r2

    def test_clear_results(self, dm):
        dm.initialize_file()
        dm.write_row({"Time": 1.0}, measurement_type="T")
        dm.clear_results()
        assert dm.results_count == 0


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
class TestTiming:
    def test_elapsed_time_starts_near_zero(self, dm):
        dm.initialize_file()
        t = dm.elapsed_time()
        assert t < 1.0  # should be very close to 0

    def test_elapsed_time_increases(self, dm):
        dm.initialize_file()
        t1 = dm.elapsed_time()
        time.sleep(0.1)
        t2 = dm.elapsed_time()
        assert t2 > t1


# ---------------------------------------------------------------------------
# Auto-log
# ---------------------------------------------------------------------------
class TestAutoLog:
    def test_initialize_creates_file(self, dm, tmp_log_dir):
        path = dm.initialize_auto_log()
        assert path is not None
        assert path.exists()
        assert path.parent == tmp_log_dir

    def test_auto_log_header(self, dm, tmp_log_dir):
        path = dm.initialize_auto_log()
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == AUTO_LOG_FIELDNAMES

    def test_write_auto_log_entry(self, dm, tmp_log_dir):
        path = dm.initialize_auto_log()
        result = dm.write_auto_log_entry(
            temp=295.5, ppms_field=1000, helmholtz_current_a=0.5
        )
        assert result is True
        dm.close_auto_log()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
        assert float(row[2]) == pytest.approx(295.5)
        assert float(row[3]) == pytest.approx(1000)

    def test_write_without_init_returns_false(self, dm):
        assert dm.write_auto_log_entry(temp=300) is False

    def test_close_auto_log(self, dm, tmp_log_dir):
        dm.initialize_auto_log()
        assert dm.is_auto_log_open
        dm.close_auto_log()
        assert not dm.is_auto_log_open

    def test_resume_existing_log(self, dm, tmp_log_dir):
        # First session
        p1 = dm.initialize_auto_log()
        dm.write_auto_log_entry(temp=300)
        dm.close_auto_log()

        # Second session should append
        p2 = dm.initialize_auto_log()
        assert p2 == p1
        dm.write_auto_log_entry(temp=301)
        dm.close_auto_log()

        with open(p1, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
        # Header only once + 2 data rows
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Thread safety of CSV writes
# ---------------------------------------------------------------------------
class TestThreadSafety:
    def test_concurrent_writes(self, dm, tmp_data_dir):
        """Multiple threads writing rows concurrently — no corruption."""
        path = dm.initialize_file(filename="concurrent_test")
        n_threads = 4
        n_rows = 50
        barrier = threading.Barrier(n_threads)

        def writer(tid):
            barrier.wait()
            for i in range(n_rows):
                dm.write_row(
                    {"Time": float(tid * 1000 + i), "Temp": 300.0},
                    measurement_type=f"T{tid}",
                )

        threads = [threading.Thread(target=writer, args=(tid,))
                    for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        dm.close()

        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == n_threads * n_rows


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------
class TestClose:
    def test_close_flushes(self, dm, tmp_data_dir):
        path = dm.initialize_file(filename="flush_test")
        dm.write_row({"Time": 1.0}, measurement_type="F")
        dm.close()
        # File should be readable after close
        with open(path, "r") as f:
            content = f.read()
        assert "1.0" in content

    def test_double_close_safe(self, dm):
        dm.initialize_file()
        dm.close()
        dm.close()  # should not raise

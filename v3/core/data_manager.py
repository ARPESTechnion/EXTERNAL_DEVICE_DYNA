"""
v3.core.data_manager  —  Thread-safe measurement data persistence.

Responsibilities
----------------
* CSV data file: create, write rows, flush, close.
* In-memory results buffer (``collections.deque``, bounded).
* Auto-log subsystem (PPMS monitoring log with rotation).
* Column-name translation  (internal data_point keys → CSV headers).

Threading contract
------------------
* ``write_row()`` is called from the experiment worker thread.
* ``get_results()`` is called from the main/GUI thread for plotting.
* ``deque`` is used for the results buffer — thread-safe for
  single-producer / single-consumer with bounded maxlen.
* CSV access is serialized via ``_csv_lock``.
* Auto-log access is serialized via ``_auto_log_lock``.
"""

from __future__ import annotations

import csv
import logging
import math
import time
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from v3.core.constants import (
    AUTO_LOG_FIELDNAMES,
    AUTO_LOG_MAX_SIZE_BYTES,
    CSV_FIELDNAMES,
    DATA_KEY_TO_CSV,
    DEFAULT_DATA_DIR,
    DEFAULT_LOG_DIR,
    MAX_RESULTS_POINTS,
)

logger = logging.getLogger(__name__)


class DataManager:
    """
    Manages experiment CSV files, in-memory result buffers, and PPMS
    auto-logging.

    Parameters
    ----------
    data_dir : str | Path
        Root directory for measurement CSVs.
    log_dir : str | Path
        Root directory for auto-log CSVs.
    max_results : int
        Maximum number of data points kept in the in-memory buffer.
    auto_log_max_size : int
        Maximum auto-log file size in bytes before rotation.
    """

    def __init__(
        self,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        log_dir: str | Path = DEFAULT_LOG_DIR,
        max_results: int = MAX_RESULTS_POINTS,
        auto_log_max_size: int = AUTO_LOG_MAX_SIZE_BYTES,
    ) -> None:
        # --- Data file ---
        self.data_dir = Path(data_dir)
        self._csv_lock = threading.Lock()
        self._data_file = None
        self._csv_writer = None
        self._data_filename: Path | None = None
        self._time_offset: float = 0.0
        self._measurement_start_time: float | None = None
        self._current_note: str = ""
        self._session_rows_written: int = 0
        self._session_created_new_file: bool = False
        self._session_header_enabled: bool = False
        self._session_user: str = ""
        self._session_sample: str = ""

        # --- Results buffer ---
        self._results: deque[dict[str, Any]] = deque(maxlen=max_results)

        # --- Auto-log ---
        self.log_dir = Path(log_dir)
        self._auto_log_lock = threading.Lock()
        self._auto_log_file = None
        self._auto_log_writer = None
        self._auto_log_filename: Path | None = None
        self._auto_log_max_size = auto_log_max_size
        self._auto_log_start_time: float | None = None

    # ==================================================================
    # Data file lifecycle
    # ==================================================================
    def configure_session_header(
        self,
        *,
        enabled: bool,
        user: str = "",
        sample: str = "",
    ) -> None:
        """Configure optional session metadata row written to new files."""
        self._session_header_enabled = bool(enabled)
        self._session_user = str(user).strip()
        self._session_sample = str(sample).strip()

    def initialize_file(
        self,
        directory: str | Path | None = None,
        filename: str | None = None,
        append: bool = False,
    ) -> Path | None:
        """
        Create (or reopen) a data CSV file.

        Parameters
        ----------
        directory : path, optional
            Override the default data directory.  Updates ``self.data_dir``.
        filename : str, optional
            Specific filename.  If None, auto-generates ``Data_YYYYMMDD_NNN.csv``.
        append : bool
            If True and the file exists, reopen in append mode and continue
            timestamps from the last ``Time(s)`` value.

        Returns
        -------
        Path | None
            The filepath of the initialised file, or None on error.
        """
        try:
            target_dir = Path(directory) if directory is not None else self.data_dir
            if directory is not None:
                self.data_dir = target_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            if filename is None:
                filepath = self._auto_increment_filepath(target_dir)
            else:
                if not filename.lower().endswith(".csv"):
                    filename += ".csv"
                filepath = target_dir / filename

                if filepath.exists():
                    if append:
                        try:
                            return self._open_append(filepath)
                        except ValueError as exc:
                            logger.warning(
                                "Append rejected for %s (%s); creating numbered variant instead",
                                filepath,
                                exc,
                            )
                            filepath = self._numbered_variant(filepath)
                    else:
                        filepath = self._numbered_variant(filepath)

            return self._open_new(filepath)
        except Exception:
            logger.exception("Failed to initialize data file")
            return None

    def _auto_increment_filepath(self, target_dir: Path) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"Data_{today}"
        counter = 0
        while True:
            counter += 1
            candidate = target_dir / f"{prefix}_{counter:03d}.csv"
            if not candidate.exists():
                return candidate

    def _numbered_variant(self, filepath: Path) -> Path:
        base = filepath.stem
        ext = filepath.suffix
        counter = 0
        while True:
            counter += 1
            candidate = filepath.parent / f"{base}_{counter:03d}{ext}"
            if not candidate.exists():
                return candidate

    def _open_new(self, filepath: Path) -> Path:
        with self._csv_lock:
            self._close_file_unlocked()
            self._time_offset = 0.0
            self._measurement_start_time = None
            self._results.clear()
            self._session_rows_written = 0
            self._session_created_new_file = True
            self._data_filename = filepath
            self._data_file = open(filepath, "w", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(
                self._data_file, fieldnames=CSV_FIELDNAMES
            )
            self._csv_writer.writeheader()
            self._write_session_header_row_unlocked()
            self._data_file.flush()
        logger.info("Data file created: %s", filepath)
        return filepath

    def _open_append(self, filepath: Path) -> Path:
        last_time = 0.0
        is_empty_file = False
        try:
            with open(filepath, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = [name.strip() for name in (reader.fieldnames or [])]
                if not fieldnames:
                    is_empty_file = True
                elif fieldnames != CSV_FIELDNAMES:
                    raise ValueError("CSV header does not match expected schema")

                for row in reader:
                    raw = row.get("Time(s)", "")
                    if raw in (None, ""):
                        continue
                    try:
                        candidate = float(raw)
                        if math.isfinite(candidate):
                            last_time = max(last_time, candidate)
                    except (ValueError, TypeError):
                        continue
        except ValueError:
            raise
        except Exception:
            logger.warning("Could not read last time from %s", filepath)
            last_time = 0.0

        with self._csv_lock:
            self._close_file_unlocked()
            self._time_offset = last_time
            self._measurement_start_time = None
            self._results.clear()
            self._session_rows_written = 0
            self._session_created_new_file = False
            self._data_filename = filepath
            self._data_file = open(filepath, "a", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(
                self._data_file, fieldnames=CSV_FIELDNAMES
            )
            if is_empty_file:
                self._csv_writer.writeheader()
                self._data_file.flush()

        self.append_note(f"Data appended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Data file opened for append: %s (offset %.2fs)", filepath, last_time)
        return filepath

    def _write_session_header_row_unlocked(self) -> None:
        if not self._session_header_enabled or self._csv_writer is None:
            return

        note_parts = [f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
        if self._session_user:
            note_parts.append(f"User: {self._session_user}")
        if self._session_sample:
            note_parts.append(f"Sample: {self._session_sample}")

        row: dict[str, Any] = {}
        for csv_col in CSV_FIELDNAMES:
            row[csv_col] = np.nan
        row["Measurement_Type"] = "SessionInfo"
        row["Notes"] = " | ".join(note_parts)
        self._csv_writer.writerow(row)

    def _close_file_unlocked(self) -> None:
        """Close the current data file.  Caller must hold ``_csv_lock``."""
        filepath = self._data_filename
        should_delete_empty_new_file = (
            filepath is not None
            and self._session_created_new_file
            and self._session_rows_written == 0
        )

        if self._data_file is not None:
            try:
                self._data_file.flush()
                self._data_file.close()
            except Exception:
                logger.exception("Error closing data file")
            self._data_file = None
            self._csv_writer = None

        if should_delete_empty_new_file and filepath is not None:
            try:
                if filepath.exists():
                    filepath.unlink()
                    logger.info("Removed empty session data file: %s", filepath)
                    if self._data_filename == filepath:
                        self._data_filename = None
            except Exception:
                logger.exception("Failed to remove empty session data file: %s", filepath)

        self._session_created_new_file = False
        self._session_rows_written = 0

    def close(self) -> None:
        """Flush and close both data file and auto-log."""
        with self._csv_lock:
            self._close_file_unlocked()
        self.close_auto_log()
        logger.info("DataManager closed")

    # ==================================================================
    # Row writing
    # ==================================================================
    def set_note(self, note: str) -> None:
        """Set a note to be attached to the *next* written row."""
        self._current_note = note

    def append_note(self, note: str) -> None:
        """Append text to the next-row note, separated by '; ' when needed."""
        text = str(note).strip()
        if not text:
            return
        if self._current_note:
            self._current_note = f"{self._current_note}; {text}"
        else:
            self._current_note = text

    def write_row(
        self,
        data_point: dict[str, Any],
        measurement_type: str = "Full",
    ) -> bool:
        """
        Translate a measurement ``data_point`` dict and write one CSV row.

        Returns True on success, False on failure.
        """
        if self._csv_writer is None:
            # Auto-initialize if no file open
            if self.initialize_file() is None:
                return False

        try:
            row: dict[str, Any] = {}
            for csv_col in CSV_FIELDNAMES:
                row[csv_col] = np.nan  # default

            # Map internal keys → CSV columns
            for internal_key, csv_col in DATA_KEY_TO_CSV.items():
                if internal_key in data_point:
                    row[csv_col] = data_point[internal_key]

            row["Measurement_Type"] = measurement_type
            row["Notes"] = self._current_note

            with self._csv_lock:
                if self._csv_writer is not None and self._data_file is not None:
                    self._csv_writer.writerow(row)
                    self._data_file.flush()
                    self._session_rows_written += 1

            # Append to in-memory buffer (deque is bounded; oldest auto-dropped)
            self._results.append(data_point)

            self._current_note = ""
            return True
        except Exception:
            logger.exception("Error writing data row")
            return False

    # ==================================================================
    # Results buffer access  (plotting)
    # ==================================================================
    def get_results(self) -> list[dict[str, Any]]:
        """Return a snapshot of the results buffer (list copy)."""
        return list(self._results)

    def clear_results(self) -> None:
        """Clear the in-memory results buffer."""
        self._results.clear()

    @property
    def results_count(self) -> int:
        return len(self._results)

    # ==================================================================
    # Timing helpers
    # ==================================================================
    def elapsed_time(self) -> float:
        """Seconds since the first measurement, plus any append offset."""
        if self._measurement_start_time is None:
            self._measurement_start_time = time.time()
        return time.time() - self._measurement_start_time + self._time_offset

    @property
    def time_offset(self) -> float:
        return self._time_offset

    @property
    def data_filename(self) -> Path | None:
        return self._data_filename

    # ==================================================================
    # Auto-log subsystem
    # ==================================================================
    def _auto_log_base_path(self) -> Path:
        date_str = datetime.now().strftime("%y%m%d")
        return self.log_dir / f"{date_str}_external_PPMS_log.csv"

    @staticmethod
    def _auto_log_suffixed_path(base_path: Path, index: int) -> Path:
        return base_path.parent / f"{base_path.stem}_{index:03d}{base_path.suffix}"

    def _select_auto_log_candidate(self) -> tuple[Path, bool]:
        """
        Select a log candidate preserving existing non-full files.

        Returns
        -------
        tuple[Path, bool]
            (path, append_mode). append_mode=True means resume existing file.
        """
        base_path = self._auto_log_base_path()
        idx = 0
        while True:
            candidate = base_path if idx == 0 else self._auto_log_suffixed_path(base_path, idx)
            if not candidate.exists():
                return candidate, False
            try:
                if candidate.stat().st_size < self._auto_log_max_size:
                    return candidate, True
            except Exception:
                logger.exception("Failed to inspect auto-log candidate: %s", candidate)
                return candidate, False
            idx += 1

    def initialize_auto_log(self) -> Path | None:
        """
        Create or reopen today's auto-log file.

        Returns
        -------
        Path | None
            Path to the log file, or None on error.
        """
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._auto_log_lock:
                self._close_auto_log_unlocked()

                path, append_mode = self._select_auto_log_candidate()
                mode = "a" if append_mode else "w"
                self._auto_log_filename = path
                self._auto_log_file = open(path, mode, newline="", encoding="utf-8")
                self._auto_log_writer = csv.writer(self._auto_log_file)

                if not append_mode:
                    self._auto_log_writer.writerow(AUTO_LOG_FIELDNAMES)
                    self._auto_log_file.flush()

                self._auto_log_start_time = time.time()
                if append_mode:
                    file_size = path.stat().st_size if path.exists() else 0
                    logger.info(
                        "Auto-log resumed: %s (%.1f MB)",
                        path.name,
                        file_size / 1024 / 1024,
                    )
                else:
                    logger.info("Auto-log created: %s", path.name)
                return path
        except Exception:
            logger.exception("Failed to initialize auto-log")
            return None

    def write_auto_log_entry(
        self,
        temp: Any = "",
        ppms_field: Any = "",
        helmholtz_current_a: Any = "",
        helmholtz_current_b: Any = "",
        helmholtz_resistance_a: Any = "",
        helmholtz_resistance_b: Any = "",
        helmholtz_field: Any = "",
    ) -> bool:
        """
        Write one row to the auto-log.  Non-critical — failures are logged
        but do not propagate.

        Returns True on success.
        """
        if self._auto_log_file is None or self._auto_log_writer is None:
            return False
        try:
            rotate_needed = False
            with self._auto_log_lock:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elapsed = round(
                    time.time() - (self._auto_log_start_time or time.time()), 2
                )
                self._auto_log_writer.writerow([
                    timestamp,
                    elapsed,
                    temp if temp is not None else "",
                    ppms_field if ppms_field is not None else "",
                    helmholtz_current_a,
                    helmholtz_current_b,
                    helmholtz_resistance_a if helmholtz_resistance_a is not None else "",
                    helmholtz_resistance_b if helmholtz_resistance_b is not None else "",
                    helmholtz_field,
                ])
                self._auto_log_file.flush()

                # Check rotation
                if self._auto_log_filename and self._auto_log_filename.exists():
                    if self._auto_log_filename.stat().st_size >= self._auto_log_max_size:
                        self._close_auto_log_unlocked()
                        rotate_needed = True

            if rotate_needed:
                rotated = self.initialize_auto_log()
                if rotated is None:
                    logger.warning("Auto-log rotation failed to open next file")
                else:
                    logger.info("Auto-log rotated to: %s", rotated.name)

            return True
        except Exception:
            logger.exception("Error writing auto-log entry")
            return False

    def _close_auto_log_unlocked(self) -> None:
        """Close auto-log file.  Caller must hold ``_auto_log_lock``."""
        if self._auto_log_file is not None:
            try:
                self._auto_log_file.flush()
                self._auto_log_file.close()
            except Exception:
                logger.exception("Error closing auto-log file")
            self._auto_log_file = None
            self._auto_log_writer = None

    def close_auto_log(self) -> None:
        """Public close for auto-log."""
        with self._auto_log_lock:
            self._close_auto_log_unlocked()

    @property
    def auto_log_filename(self) -> Path | None:
        return self._auto_log_filename

    @property
    def is_auto_log_open(self) -> bool:
        return self._auto_log_file is not None

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from v3.core.constants import INST_DYNA
from v3.core.ui_events import UIEventBus, W_LOG_MESSAGE
from v3.gui.app import MeasureApp


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _DummyDynaTab:
    def __init__(self, interval: float):
        self.dyna_plot_interval = _Var(interval)
        self.update_plot = MagicMock()
        self.refresh_auto_log_status = MagicMock()


def _build_minimal_app() -> MeasureApp:
    app = MeasureApp.__new__(MeasureApp)
    app.auto_log_enabled = _Var(False)
    app.data_mgr = MagicMock()
    app.ui_bus = UIEventBus()
    app._all_tabs = []
    app._shutting_down = False
    app._schedule_update_ui = MagicMock()
    app.dyna_tab = _DummyDynaTab(1.0)
    return app


def test_set_auto_logging_enabled_true_initializes_log() -> None:
    app = _build_minimal_app()
    app.data_mgr.initialize_auto_log.return_value = Path("Logs/test_log.csv")

    MeasureApp.set_auto_logging_enabled(app, True)

    assert app.auto_log_enabled.get() is True
    app.data_mgr.initialize_auto_log.assert_called_once()
    app.data_mgr.close_auto_log.assert_not_called()
    events = app.ui_bus.drain()
    assert W_LOG_MESSAGE in events
    assert "Auto-logging active" in str(events[W_LOG_MESSAGE])


def test_set_auto_logging_enabled_false_closes_log() -> None:
    app = _build_minimal_app()
    app.auto_log_enabled.set(True)

    MeasureApp.set_auto_logging_enabled(app, False)

    assert app.auto_log_enabled.get() is False
    app.data_mgr.close_auto_log.assert_called_once()
    events = app.ui_bus.drain()
    assert W_LOG_MESSAGE in events
    assert "disabled" in str(events[W_LOG_MESSAGE]).lower()


def test_set_auto_log_directory_reopens_when_enabled() -> None:
    app = _build_minimal_app()
    app.auto_log_enabled.set(True)
    app.data_mgr.initialize_auto_log.return_value = Path("NewLogs/test_log.csv")

    MeasureApp.set_auto_log_directory(app, Path("NewLogs"))

    assert app.data_mgr.log_dir == Path("NewLogs")
    app.data_mgr.close_auto_log.assert_called_once()
    app.data_mgr.initialize_auto_log.assert_called_once()


def test_update_ui_autolog_only_on_new_dyna_sample() -> None:
    app = _build_minimal_app()
    app.auto_log_enabled.set(True)
    app._write_auto_log = MagicMock()
    app.instrument_connected = {"helmholtz": False}
    app.helmholtz = MagicMock()
    app.helmholtz.is_enabled = False
    app.engine = MagicMock()
    app.engine.is_running = False
    app.get_dyna_snapshot = MagicMock(return_value={"temp_val": 300.0, "field_val": 10.0})
    app.current_temp = None
    app.current_inplane_field = None
    app.dyna_time_data = []
    app.dyna_temp_data = []
    app.dyna_field_data = []
    app.start_time_dyna = 0.0
    app.last_plot_time_dyna = 0.0
    app.last_plot_time = 0.0

    app.bus = MagicMock()
    app.bus.is_connected.side_effect = lambda key: key == INST_DYNA

    with patch("v3.gui.app.time.time", return_value=100.0):
        MeasureApp._update_ui(app)
    assert app._write_auto_log.call_count == 1

    with patch("v3.gui.app.time.time", return_value=100.2):
        MeasureApp._update_ui(app)
    assert app._write_auto_log.call_count == 1

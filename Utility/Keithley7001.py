from __future__ import annotations

import time

import pyvisa


class _Keithley7001Base:
    """Shared behavior for real and mock Keithley 7001 switch drivers."""

    def __init__(self, relay_settle_s: float = 1.0) -> None:
        self.name = "Keithley7001"
        self.data: list[str] = []
        self.IsConnected = False
        # UI status code in v3 matches by column-number strings.
        self.closed_channels: set[str] = set()
        self._relay_settle_s = max(0.0, float(relay_settle_s))

    @staticmethod
    def _validate_column(column: int) -> int:
        value = int(column)
        if value < 1 or value > 8:
            raise ValueError(f"Routing number {value} out of range (1-8)")
        return value

    @staticmethod
    def _build_crosspoint(card: int, row: int, column: int) -> str:
        return f"{card}!{row}!{column:02d}"

    def _build_close_list(self, i1: int, i2: int = 0, i3: int = 0, i4: int = 0) -> tuple[list[int], str]:
        columns = [int(v) for v in (i1, i2, i3, i4) if int(v) != 0]
        for c in columns:
            self._validate_column(c)

        row_map = [1, 2, 3, 4]
        items: list[str] = []
        for idx, col in enumerate(columns[:4]):
            row = row_map[idx]
            items.append(self._build_crosspoint(card=1, row=row, column=col))

        return columns, f"(@{','.join(items)})"

    def open_all_channels(self) -> None:
        self.open_all()

    def close_channel(self, channel_num: int) -> None:
        self.close_list(int(channel_num), 0, 0, 0)


class Keithley7001(_Keithley7001Base):
    """
    Keithley 7001 switch mainframe driver.

    Notes:
    - API mirrors Utility/MySwitch.py for drop-in integration.
    - Command format currently follows legacy in-project routing usage.
      Keep command strings centralized here for easy manual-aligned updates.
    """

    def __init__(
        self,
        resource_name: str = "GPIB0::7::INSTR",
        timeout: int = 5000,
        debug: bool = False,
        relay_settle_s: float = 1.0,
    ) -> None:
        super().__init__(relay_settle_s=relay_settle_s)
        self.address = resource_name
        self.timeout = int(timeout)
        self.debug = bool(debug)
        self.rm: pyvisa.ResourceManager | None = None
        self.switch = None

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[Keithley7001] {msg}")

    def connect(self) -> str:
        self.rm = pyvisa.ResourceManager()
        self.switch = self.rm.open_resource(self.address)
        self.switch.timeout = self.timeout
        self.switch.write_termination = "\n"
        self.switch.read_termination = "\n"
        idn = str(self.switch.query("*IDN?")).strip()
        self.IsConnected = True
        self._log(f"Connected to {idn}")
        return idn

    def disconnect(self) -> None:
        if self.switch is not None:
            try:
                self.switch.close()
            finally:
                self.switch = None
        if self.rm is not None:
            try:
                self.rm.close()
            finally:
                self.rm = None
        self.IsConnected = False

    def write(self, command: str) -> None:
        if self.switch is None:
            raise RuntimeError("Keithley 7001 is not connected")
        self._log(f">> {command}")
        self.switch.write(command)

    def read(self) -> str:
        if self.switch is None:
            raise RuntimeError("Keithley 7001 is not connected")
        response = str(self.switch.read())
        self._log(f"<< {response}")
        return response

    def query(self, command: str) -> str:
        if self.switch is None:
            raise RuntimeError("Keithley 7001 is not connected")
        self._log(f">> {command}")
        response = str(self.switch.query(command)).strip()
        self._log(f"<< {response}")
        return response

    def open_all(self) -> None:
        self.write(":ROUTE:OPEN ALL")
        self.closed_channels.clear()

    def close_list(self, i1: int, i2: int = 0, i3: int = 0, i4: int = 0) -> None:
        columns, list_text = self._build_close_list(i1, i2, i3, i4)
        if not columns:
            self.open_all()
            return

        self.open_all()
        if self._relay_settle_s > 0:
            time.sleep(self._relay_settle_s)
        self.write(f"ROUTE:CLOSE {list_text}")
        self.closed_channels = {str(c) for c in columns}


class MockKeithley7001(_Keithley7001Base):
    """Mock Keithley 7001 driver used in mockup mode and tests."""

    def __init__(self, relay_settle_s: float = 0.0) -> None:
        super().__init__(relay_settle_s=relay_settle_s)
        self.name = "MockKeithley7001"
        self.address = "MOCK::KEITHLEY7001::INSTR"
        self.switch = None
        self._last_response = ""

    def connect(self) -> str:
        self.switch = "MockResource"
        self.IsConnected = True
        self._last_response = "MOCK,KEITHLEY,7001,1.0"
        return self._last_response

    def disconnect(self) -> None:
        self.switch = None
        self.IsConnected = False

    def write(self, command: str) -> None:
        cmd = str(command).strip()
        cmd_upper = cmd.upper()
        if "ROUT:OPEN:ALL" in cmd_upper:
            self.closed_channels.clear()
            return

        if "ROUTE:CLOSE" in cmd_upper or "ROUT:CLOS" in cmd_upper:
            if "(@" in cmd and ")" in cmd:
                body = cmd.split("(@", 1)[1].split(")", 1)[0]
                items = [tok.strip() for tok in body.split(",") if tok.strip()]
                cols: list[str] = []
                for item in items:
                    digits = "".join(ch for ch in item if ch.isdigit())
                    if len(digits) >= 2:
                        cols.append(str(int(digits[-2:])))
                self.closed_channels = set(cols)

    def read(self) -> str:
        return self._last_response or "MOCK RESPONSE"

    def query(self, command: str) -> str:
        cmd = str(command).strip().upper()
        if cmd == "*IDN?":
            return "MOCK,KEITHLEY,7001,1.0"
        return ""

    def open_all(self) -> None:
        self.write("ROUT:OPEN:ALL ALL")

    def close_list(self, i1: int, i2: int = 0, i3: int = 0, i4: int = 0) -> None:
        columns, list_text = self._build_close_list(i1, i2, i3, i4)
        if not columns:
            self.open_all()
            return

        self.open_all()
        if self._relay_settle_s > 0:
            time.sleep(self._relay_settle_s)
        self.write(f"ROUTE:CLOSE {list_text}")
        self.closed_channels = {str(c) for c in columns}

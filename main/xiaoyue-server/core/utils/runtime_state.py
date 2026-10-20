from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass


@dataclass
class ConnectedDevice:
    device_id: str
    peer: str
    connected_at: float


class RuntimeState:
    def __init__(self):
        self._started_at = time.time()
        self._lock = threading.Lock()
        self._devices: dict[str, ConnectedDevice] = {}

    def device_connected(self, connection_key: str, device_id: str, peer: str) -> None:
        now = time.time()
        with self._lock:
            self._devices[connection_key] = ConnectedDevice(
                device_id=device_id or "unknown",
                peer=peer,
                connected_at=now,
            )

    def device_disconnected(self, connection_key: str) -> None:
        with self._lock:
            self._devices.pop(connection_key, None)

    def snapshot(self) -> dict:
        now = time.time()
        with self._lock:
            devices = []
            for connection in self._devices.values():
                item = asdict(connection)
                item["connected_seconds"] = max(0, int(now - connection.connected_at))
                item["connected_at"] = int(connection.connected_at)
                devices.append(item)
        return {
            "started_at": int(self._started_at),
            "uptime_seconds": max(0, int(now - self._started_at)),
            "device_count": len(devices),
            "devices": sorted(devices, key=lambda item: item["connected_at"]),
        }


runtime_state = RuntimeState()

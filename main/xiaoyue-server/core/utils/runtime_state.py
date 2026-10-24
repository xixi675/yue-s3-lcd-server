from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class DeviceRecord:
    device_id: str
    peer: str
    first_seen: float
    last_seen: float
    connected_at: float = 0.0
    disconnected_at: float = 0.0
    active_connections: int = 0


class RuntimeState:
    def __init__(self):
        self._started_at = time.time()
        self._lock = threading.Lock()
        self._devices: dict[str, DeviceRecord] = {}
        self._connections: dict[str, str] = {}

    def device_connected(self, connection_key: str, device_id: str, peer: str) -> None:
        now = time.time()
        device_key = device_id or peer or "unknown"
        with self._lock:
            device = self._devices.get(device_key)
            if device is None:
                device = DeviceRecord(
                    device_id=device_key,
                    peer=peer,
                    first_seen=now,
                    last_seen=now,
                )
                self._devices[device_key] = device

            device.peer = peer
            device.last_seen = now
            device.disconnected_at = 0.0
            device.active_connections += 1
            if device.active_connections == 1:
                device.connected_at = now
            self._connections[connection_key] = device_key

    def device_seen(self, device_id: str, peer: str) -> None:
        if not device_id:
            return
        now = time.time()
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                device = DeviceRecord(
                    device_id=device_id,
                    peer=peer,
                    first_seen=now,
                    last_seen=now,
                )
                self._devices[device_id] = device
            else:
                device.last_seen = now
            device.peer = peer or device.peer

    def device_disconnected(self, connection_key: str) -> None:
        now = time.time()
        with self._lock:
            device_key = self._connections.pop(connection_key, None)
            if device_key is None:
                return
            device = self._devices.get(device_key)
            if device is None:
                return
            device.active_connections = max(0, device.active_connections - 1)
            device.last_seen = now
            if device.active_connections == 0:
                device.disconnected_at = now

    def snapshot(self) -> dict:
        now = time.time()
        with self._lock:
            devices = []
            for device in self._devices.values():
                online = device.active_connections > 0
                last_seen_seconds = max(0, int(now - device.last_seen))
                if online:
                    status = "online"
                elif last_seen_seconds <= 300:
                    status = "idle"
                else:
                    status = "offline"
                devices.append(
                    {
                        "device_id": device.device_id,
                        "peer": device.peer,
                        "online": online,
                        "status": status,
                        "connected_at": int(device.connected_at)
                        if online
                        else 0,
                        "disconnected_at": int(device.disconnected_at)
                        if not online
                        else 0,
                        "last_seen": int(device.last_seen),
                        "last_seen_seconds": last_seen_seconds,
                        "connected_seconds": max(
                            0, int(now - device.connected_at)
                        )
                        if online
                        else 0,
                    }
                )
            devices.sort(
                key=lambda item: (
                    not item["online"],
                    -item["last_seen"],
                )
            )
            online_count = sum(1 for device in devices if device["online"])
        return {
            "started_at": int(self._started_at),
            "uptime_seconds": max(0, int(now - self._started_at)),
            "device_count": online_count,
            "known_device_count": len(devices),
            "devices": devices,
        }


runtime_state = RuntimeState()

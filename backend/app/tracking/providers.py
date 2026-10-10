"""Container tracking providers.

A real provider (a paid tracking API) plugs in by implementing TrackingProvider and being added to get_provider().
The sample provider is deterministic demo data and is always labelled as such. No provider ever guesses.
"""
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings


class TrackingNotConfigured(RuntimeError):
    pass


class TrackingProvider(ABC):
    name = "provider"
    sample = False

    @abstractmethod
    def track(self, container_number: str, carrier: str, origin_port: str, destination_port: str) -> dict:
        """Return {status, location, vessel, voyage, eta (ISO datetime), events:[{time, location, description, key}]}.
        `key` optionally maps an event to a timeline step: factory_pickup, port_arrival_origin, loaded, in_transit, arrived_destination, warehouse_delivery."""


class SampleProvider(TrackingProvider):
    name = "sample"
    sample = True

    def track(self, container_number: str, carrier: str, origin_port: str, destination_port: str) -> dict:
        h = int(hashlib.sha256(container_number.encode()).hexdigest()[:8], 16)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        eta_days = 3 + h % 9
        events = [
            {"time": (now - timedelta(days=9)).isoformat(), "location": origin_port, "description": "Gate in at origin terminal", "key": "port_arrival_origin"},
            {"time": (now - timedelta(days=8)).isoformat(), "location": origin_port, "description": "Loaded on vessel", "key": "loaded"},
            {"time": (now - timedelta(days=7)).isoformat(), "location": origin_port, "description": "Vessel departed", "key": "in_transit"},
        ]
        location = f"At sea, bound for {destination_port}"
        if h % 3 == 2:
            events.append({"time": (now - timedelta(days=3)).isoformat(), "location": "Singapore", "description": "Transshipment: discharged and reloaded", "key": None})
            location = "Singapore, transshipment"
        return {"status": "In transit", "location": location, "vessel": "MV Ocean Meridian", "voyage": "031E", "eta": (now + timedelta(days=eta_days)).isoformat(), "events": list(reversed(events))}


class NoProvider(TrackingProvider):
    name = "none"

    def track(self, *args, **kwargs) -> dict:
        raise TrackingNotConfigured("No tracking provider is connected. Set TRACKING_PROVIDER, or update the timeline by hand.")


def get_provider() -> TrackingProvider:
    name = (get_settings().tracking_provider or "sample").lower()
    if name == "sample":
        return SampleProvider()
    if name == "none":
        return NoProvider()
    raise TrackingNotConfigured(f"Unknown TRACKING_PROVIDER '{name}'. Add an adapter in app/tracking/providers.py.")

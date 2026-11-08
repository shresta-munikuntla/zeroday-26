import os
from backend.notifications.mock import MockAdapter
from backend.notifications.photon import PhotonAdapter


def get_adapter():
    mode = os.getenv("NOTIFICATION_MODE", "mock").lower()
    if mode == "mock":
        return MockAdapter()
    if mode == "photon":
        return PhotonAdapter()
    raise RuntimeError(f"Unsupported NOTIFICATION_MODE: {mode}")

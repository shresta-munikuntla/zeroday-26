"""Photon 2.0 Beta REST adapter."""
from __future__ import annotations

import json
import os
import uuid

import httpx

from backend.notifications.base import NotificationAdapter
from backend.storage import connect


class PhotonConfigurationError(ValueError):
    """Raised when the local Photon project or recipient mapping is incomplete."""


class PhotonAPIError(RuntimeError):
    """A safe, credential-free error returned while calling Photon."""


class PhotonAdapter(NotificationAdapter):
    """Create/reuse a Photon User and Space, then submit an approved message.

    ``PHOTON_CHANNEL_MAP`` maps the application's existing, allowlisted employee
    notification channels (for example ``mock:avery.chen``) to Photon addresses:
    ``{"mock:avery.chen":{"platform":"email","handle":"avery@example.test"}}``.
    The map belongs in the local, git-ignored ``.env`` because it can contain personal
    contact details.
    """

    def __init__(self):
        self.api_key = os.getenv("PHOTON_API_KEY", "").strip()
        self.project_id = os.getenv("PHOTON_PROJECT_ID", "").strip()
        self.agent_user_id = os.getenv("PHOTON_AGENT_USER_ID", "").strip()
        raw_map = os.getenv("PHOTON_CHANNEL_MAP", "{}").strip() or "{}"
        try:
            self.channel_map = json.loads(raw_map)
        except json.JSONDecodeError as exc:
            raise PhotonConfigurationError("PHOTON_CHANNEL_MAP must be valid JSON") from exc
        if not isinstance(self.channel_map, dict):
            raise PhotonConfigurationError("PHOTON_CHANNEL_MAP must be a JSON object")
        missing = [name for name, value in (("PHOTON_API_KEY", self.api_key),
                                             ("PHOTON_PROJECT_ID", self.project_id),
                                             ("PHOTON_AGENT_USER_ID", self.agent_user_id)) if not value]
        if missing:
            raise PhotonConfigurationError("Missing Photon configuration: " + ", ".join(missing))
        self.base_url = os.getenv("PHOTON_API_BASE_URL", "https://api.photon.codes").rstrip("/")
        try:
            timeout = float(os.getenv("PHOTON_TIMEOUT_SECONDS", "15"))
        except ValueError as exc:
            raise PhotonConfigurationError("PHOTON_TIMEOUT_SECONDS must be a number") from exc
        self.timeout = httpx.Timeout(timeout)

    @staticmethod
    def _idempotency_key(*parts: str) -> str:
        material = "\x1f".join(parts)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "photon:" + material))

    def _post(self, client: httpx.Client, path: str, payload: dict, key: str) -> dict:
        url = f"{self.base_url}/v1/projects/{self.project_id}{path}"
        response = client.post(url, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": key,
        }, json=payload)
        try:
            result = response.json()
        except ValueError:
            result = {}
        if not isinstance(result, dict):
            raise PhotonAPIError("Photon returned an unexpected response")
        if not response.is_success:
            detail = result.get("detail") or result.get("title") or result.get("code") or response.reason_phrase
            raise PhotonAPIError(f"Photon returned HTTP {response.status_code}: {detail}")
        return result

    def _route(self, client: httpx.Client, channel: str, destination: dict) -> str:
        platform = destination.get("platform")
        handle = destination.get("handle")
        if not isinstance(platform, str) or not platform.strip() or not isinstance(handle, str) or not handle.strip():
            raise PhotonConfigurationError(f"Photon destination for {channel} needs platform and handle")

        with connect() as db:
            route = db.execute("SELECT * FROM photon_routes WHERE notification_channel=?", (channel,)).fetchone()
        if route and (route["platform"], route["handle"]) == (platform, handle) and route["photon_space_id"]:
            return route["photon_space_id"]

        user_id = route["photon_user_id"] if route and (route["platform"], route["handle"]) == (platform, handle) else None
        if not user_id:
            user = self._post(client, "/users", {"platform": platform, "handle": handle},
                              self._idempotency_key("user", channel, platform, handle))
            user_id = user.get("id")
            if not isinstance(user_id, str) or not user_id:
                raise PhotonAPIError("Photon created the recipient User but returned no id")
            with connect() as db:
                db.execute("""INSERT INTO photon_routes
                    (notification_channel, platform, handle, photon_user_id, photon_space_id)
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(notification_channel) DO UPDATE SET platform=excluded.platform,
                    handle=excluded.handle, photon_user_id=excluded.photon_user_id, photon_space_id=NULL""",
                    (channel, platform, handle, user_id))

        space = self._post(client, "/spaces", {"platform": platform,
            "participantIds": [self.agent_user_id, user_id]},
            self._idempotency_key("space", channel, platform, handle, self.agent_user_id))
        space_id = space.get("id")
        if not isinstance(space_id, str) or not space_id:
            raise PhotonAPIError("Photon created the Space but returned no id")
        with connect() as db:
            db.execute("""INSERT INTO photon_routes
                (notification_channel, platform, handle, photon_user_id, photon_space_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(notification_channel) DO UPDATE SET platform=excluded.platform,
                handle=excluded.handle, photon_user_id=excluded.photon_user_id,
                photon_space_id=excluded.photon_space_id""",
                (channel, platform, handle, user_id, space_id))
        return space_id

    def send(self, channel: str, subject: str, body: str) -> dict:
        """Submit a message. Photon acceptance is not confirmation of final delivery."""
        destination = self.channel_map.get(channel)
        if destination is None:
            raise PhotonConfigurationError(f"No Photon destination is configured for {channel}")
        if not isinstance(destination, dict):
            raise PhotonConfigurationError(f"Photon destination for {channel} must be an object")

        with httpx.Client(timeout=self.timeout) as client:
            space_id = self._route(client, channel, destination)
            message = self._post(client, "/messages", {
                "spaceId": space_id,
                "senderId": self.agent_user_id,
                "content": {"type": "text", "format": "plain", "text": f"{subject}\n\n{body}"},
            }, self._idempotency_key("message", channel, subject, body))

        provider_status = message.get("status", "accepted")
        if str(provider_status).lower() == "failed":
            detail = message.get("reason") or message.get("detail") or "Photon did not accept the message"
            return {"status": "failed", "detail": str(detail), "provider_status": provider_status}
        return {"status": "sent", "detail": "Photon accepted the message request; final delivery is not confirmed.",
                "provider_status": provider_status, "message_id": message.get("id")}

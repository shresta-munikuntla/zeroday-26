from abc import ABC, abstractmethod


class NotificationAdapter(ABC):
    @abstractmethod
    def send(self, channel: str, subject: str, body: str, *, recipient_label: str | None = None,
             idempotency_key: str | None = None, recipient_id: str | None = None) -> dict:
        raise NotImplementedError

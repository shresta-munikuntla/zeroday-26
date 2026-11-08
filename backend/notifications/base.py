from abc import ABC, abstractmethod


class NotificationAdapter(ABC):
    @abstractmethod
    def send(self, channel: str, subject: str, body: str) -> dict:
        raise NotImplementedError

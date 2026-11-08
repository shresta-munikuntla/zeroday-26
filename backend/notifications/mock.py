class MockAdapter:
    """Records that delivery would occur; sends no external message."""
    def __init__(self):
        self.records = []

    def send(self, channel: str, subject: str, body: str, *, recipient_label: str | None = None,
             idempotency_key: str | None = None, recipient_id: str | None = None) -> dict:
        record = {"channel": channel, "subject": subject, "detail": "Mocked delivery; not actually sent."}
        self.records.append(record)
        return {"status": "mocked", "detail": record["detail"]}

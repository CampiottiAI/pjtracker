"""Gmail SMTP notifier.

Requires a Gmail App Password (Google Account → Security → 2-Step Verification →
App passwords). Set PJTRACKER_SMTP_USER, PJTRACKER_SMTP_PASSWORD, and
PJTRACKER_ALERT_TO.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    to_addr: str

    @classmethod
    def from_env(cls) -> EmailConfig:
        user = os.environ.get("PJTRACKER_SMTP_USER", "").strip()
        password = os.environ.get("PJTRACKER_SMTP_PASSWORD", "").strip()
        to_addr = os.environ.get("PJTRACKER_ALERT_TO", "").strip()
        from_addr = os.environ.get("PJTRACKER_ALERT_FROM", "").strip() or user
        host = os.environ.get("PJTRACKER_SMTP_HOST", "smtp.gmail.com").strip()
        port_raw = os.environ.get("PJTRACKER_SMTP_PORT", "587").strip()
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"Invalid PJTRACKER_SMTP_PORT: {port_raw!r}") from exc
        missing = [
            name
            for name, value in (
                ("PJTRACKER_SMTP_USER", user),
                ("PJTRACKER_SMTP_PASSWORD", password),
                ("PJTRACKER_ALERT_TO", to_addr),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Missing email config env vars: " + ", ".join(missing)
            )
        return cls(
            host=host,
            port=port,
            user=user,
            password=password,
            from_addr=from_addr,
            to_addr=to_addr,
        )


class EmailNotifier:
    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._config.from_addr
        msg["To"] = self._config.to_addr
        msg.set_content(body)

        with smtplib.SMTP(self._config.host, self._config.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self._config.user, self._config.password)
            smtp.send_message(msg)

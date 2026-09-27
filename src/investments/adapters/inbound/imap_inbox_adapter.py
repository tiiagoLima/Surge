"""IMAP inbox adapter for Gmail app-password authentication."""

from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header

from src.investments.domain.email_models import IncomingEmail
from src.investments.domain.ports import InboxPort

logger = logging.getLogger(__name__)


class ImapInboxAdapter(InboxPort):
    """Reads unread Gmail messages and filters them by subject prefix."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox: str = "INBOX",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._mailbox = mailbox

    def fetch_unprocessed(self, subject_prefix: str) -> list[IncomingEmail]:
        """Fetch unread messages whose subject starts with the configured prefix."""
        if not self._username or not self._password:
            return []
        with imaplib.IMAP4_SSL(self._host, self._port) as client:
            client.login(self._username, self._password)
            client.select(self._mailbox)
            status, data = client.uid("search", "", "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []
            messages: list[IncomingEmail] = []
            for uid in data[0].split():
                status, fetched = client.uid("fetch", uid, "(RFC822)")
                if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                    continue
                message = email.message_from_bytes(fetched[0][1])
                subject = self._decode_header(message.get("Subject", ""))
                if not subject.upper().startswith(subject_prefix.upper()):
                    continue
                messages.append(
                    IncomingEmail(
                        uid=uid.decode(),
                        subject=subject,
                        body=self._body(message),
                    )
                )
            return messages

    def mark_processed(self, uid: str) -> None:
        """Mark a message as read after successful processing."""
        with imaplib.IMAP4_SSL(self._host, self._port) as client:
            client.login(self._username, self._password)
            client.select(self._mailbox)
            client.uid("store", uid, "+FLAGS", "(\\Seen)")

    @staticmethod
    def _decode_header(value: str) -> str:
        parts = decode_header(value)
        return "".join(
            part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part
            for part, charset in parts
        )

    @classmethod
    def _body(cls, message: email.message.Message) -> str:
        parts = message.walk() if message.is_multipart() else [message]
        for part in parts:
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""

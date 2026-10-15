"""Payment report policy, PDF rendering, and audit-safe delivery."""

from __future__ import annotations

import base64
import hashlib
import html
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    status: Literal["settled", "refunded", "disputed"]
    risk_level: Literal["low", "medium", "high"]


class PaymentReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1, max_length=80)
    account_reference: str = Field(min_length=1, max_length=80)
    recipient_email: str = Field(min_length=3, max_length=254)
    period_label: str = Field(min_length=1, max_length=80)
    events: list[PaymentEvent] = Field(min_length=1, max_length=250)

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient_email(cls, value: str) -> str:
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("recipient_email must be a complete email address")
        return value


class ReportDecision(BaseModel):
    report_id: str
    action: Literal["sent", "hold_for_review"]
    reason: str
    message_id: str | None = None
    recipient_hash: str


def deliver_payment_report(
    request: PaymentReportRequest,
    sender: Any,
) -> ReportDecision:
    recipient_hash = hashlib.sha256(
        request.recipient_email.lower().encode("utf-8")
    ).hexdigest()[:16]

    if any(event.risk_level == "high" for event in request.events):
        return ReportDecision(
            report_id=request.report_id,
            action="hold_for_review",
            reason="high_risk_event_present",
            recipient_hash=recipient_hash,
        )

    pdf = render_payment_report(request)
    pdf_data = base64.b64encode(pdf).decode("ascii")
    safe_period = html.escape(request.period_label)
    body = (
        f"<p>Your payment report for {safe_period} is ready.</p>"
        f'<p><a download="payment-report.pdf" href="data:application/pdf;base64,{pdf_data}">'
        "Download PDF report</a></p>"
        "<p>This notification contains only the requested account summary.</p>"
    )
    message_id = sender.email_send(
        to=str(request.recipient_email),
        subject=f"Payment report: {request.period_label}",
        html=body,
        idempotency_key=f"payment-report:{request.report_id}",
    )
    return ReportDecision(
        report_id=request.report_id,
        action="sent",
        reason="risk_policy_passed",
        message_id=message_id,
        recipient_hash=recipient_hash,
    )


def render_payment_report(request: PaymentReportRequest) -> bytes:
    lines = [
        "Payment activity report",
        f"Period: {request.period_label}",
        f"Account: {request.account_reference}",
        "",
    ]
    lines.extend(
        f"{event.occurred_at.date().isoformat()}  {event.event_id}  "
        f"{event.amount:.2f} {event.currency}  {event.status}"
        for event in request.events
    )
    lines.append(f"Report ID: {request.report_id}")
    pages = [lines[index : index + 42] for index in range(0, len(lines), 42)]
    return _write_pdf(pages)


def _write_pdf(pages: list[list[str]]) -> bytes:
    page_ids = [4 + index * 2 for index in range(len(pages))]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            f"<< /Type /Pages /Count {len(pages)} /Kids "
            f"[{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] >>"
        ).encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, page_lines in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        commands = ["BT", "/F1 10 Tf", "48 744 Td"]
        for line_index, line in enumerate(page_lines):
            if line_index:
                commands.append("0 -16 Td")
            commands.append(f"({_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, len(objects) + 1):
        offsets.append(len(document))
        document.extend(f"{object_id} 0 obj\n".encode("ascii"))
        document.extend(objects[object_id])
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(document)


def _pdf_text(value: str) -> str:
    ascii_value = value.encode("ascii", "replace").decode("ascii")
    return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

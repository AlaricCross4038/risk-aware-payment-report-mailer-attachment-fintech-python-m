from datetime import datetime, timezone
from decimal import Decimal

from fintech_report_mailer.payment_report_service import (
    PaymentEvent,
    PaymentReportRequest,
    deliver_payment_report,
)


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def email_send(self, **request: str) -> str:
        self.calls.append(request)
        return "msg_test_42"


def make_request(risk_level: str) -> PaymentReportRequest:
    return PaymentReportRequest.model_validate(
        {
            "report_id": "report-42",
            "account_reference": "account-7",
            "recipient_email": "patient-payments@example.com",
            "period_label": "September 2026",
            "events": [
                PaymentEvent(
                    event_id="payment-9",
                    occurred_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
                    amount=Decimal("125.50"),
                    currency="USD",
                    status="settled",
                    risk_level=risk_level,
                )
            ],
        }
    )


def test_high_risk_event_is_held_without_sending() -> None:
    sender = RecordingSender()

    decision = deliver_payment_report(make_request("high"), sender)

    assert decision.action == "hold_for_review"
    assert decision.reason == "high_risk_event_present"
    assert decision.message_id is None
    assert sender.calls == []


def test_low_risk_event_sends_pdf_with_stable_idempotency_key() -> None:
    sender = RecordingSender()

    decision = deliver_payment_report(make_request("low"), sender)

    assert decision.action == "sent"
    assert decision.message_id == "msg_test_42"
    assert sender.calls[0]["idempotency_key"] == "payment-report:report-42"
    assert "data:application/pdf;base64," in sender.calls[0]["html"]

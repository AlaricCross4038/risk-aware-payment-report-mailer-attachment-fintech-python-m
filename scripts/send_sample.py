"""Send one low-risk payment report through the service layer."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

from fintech_report_mailer.infrai_email import InfraiEmailClient
from fintech_report_mailer.payment_report_service import (
    PaymentEvent,
    PaymentReportRequest,
    deliver_payment_report,
)


def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    recipient = os.environ.get("REPORT_EMAIL_TO")
    if not api_key or not recipient:
        raise SystemExit("Set INFRAI_API_KEY and REPORT_EMAIL_TO")

    request = PaymentReportRequest(
        report_id="demo-2026-09",
        account_reference="acct-demo-1042",
        recipient_email=recipient,
        period_label="September 2026",
        events=[
            PaymentEvent(
                event_id="pay-demo-001",
                occurred_at=datetime.now(timezone.utc),
                amount=Decimal("48.25"),
                currency="USD",
                status="settled",
                risk_level="low",
            )
        ],
    )
    with InfraiEmailClient(api_key) as sender:
        decision = deliver_payment_report(request, sender)
    print(json.dumps(decision.model_dump(), indent=2))


if __name__ == "__main__":
    main()

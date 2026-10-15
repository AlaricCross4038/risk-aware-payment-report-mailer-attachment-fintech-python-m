"""HTTP boundary for payment report delivery."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from .infrai_email import InfraiEmailClient, InfraiError, InfraiTransportError
from .payment_report_service import (
    PaymentReportRequest,
    ReportDecision,
    deliver_payment_report,
)

app = FastAPI(title="Payment Report Mailer")


@app.post("/notifications/payment-report", response_model=ReportDecision)
def send_payment_report(request: PaymentReportRequest) -> ReportDecision:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")

    try:
        with InfraiEmailClient(api_key) as sender:
            return deliver_payment_report(request, sender)
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": str(exc.detail.get("message", "Request rejected"))},
        ) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail="Email delivery was not confirmed") from exc

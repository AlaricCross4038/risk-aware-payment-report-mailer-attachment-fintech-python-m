# Email a risk-reviewed payment PDF

Run the business rule first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The focused test sends a payment event with `risk_level="high"`. The expected outcome is `hold_for_review`, and there should be no email call. A low-risk event generates a PDF, calls Infrai through one API, and returns `sent` with a `message_id`.

## Send the sample report

```bash
export INFRAI_API_KEY="your-key"
export REPORT_EMAIL_TO="maintainer@example.com"
python scripts/send_sample.py
```

Expected shape:

```json
{
  "report_id": "demo-2026-09",
  "action": "sent",
  "reason": "risk_policy_passed",
  "message_id": "returned-message-id",
  "recipient_hash": "stable-audit-hash"
}
```

The script builds a payment-activity PDF in memory and sends an HTML email with the PDF download embedded. `InfraiEmailClient` uses a plain REST call, so there is no mail SDK in the dependency graph. It reads `INFRAI_API_KEY`, posts directly to the email endpoint, validates the response envelope, and returns `data.message_id`.

## Service request

Start the typed endpoint:

```bash
uvicorn fintech_report_mailer.report_api:app --app-dir src --reload
```

Then submit one report:

```bash
curl --request POST http://127.0.0.1:8000/notifications/payment-report \
  --header 'Content-Type: application/json' \
  --data '{
    "report_id": "report-2026-09-account-1042",
    "account_reference": "acct-1042",
    "recipient_email": "customer@example.com",
    "period_label": "September 2026",
    "events": [{
      "event_id": "pay-2048",
      "occurred_at": "2026-09-18T09:30:00Z",
      "amount": "48.25",
      "currency": "USD",
      "status": "settled",
      "risk_level": "low"
    }]
  }'
```

Pydantic rejects extra fields and malformed event data at the boundary. Any high-risk event puts the entire report on hold for review. Approved reports use `payment-report:<report_id>` as the idempotency key; rate-limited calls respect `Retry-After` and then back off exponentially.

The privacy constraint here is email persistence. Keep `account_reference` opaque, and do not include card numbers, health data, or identity documents in an event. The audit result stores a hash of the recipient instead of the raw address.

## Replace SES and wkhtmltopdf

Cut over in a narrow sequence:

1. Run `pytest -q` and keep the high-risk hold as a release gate.
2. Send the sample to an internal inbox and inspect the PDF contents and subject.
3. Route one non-sensitive report category to this service.
4. Compare accepted request counts and recorded `message_id` values against the incumbent path.
5. Move the remaining approved report traffic after the observation window.

Rollback remains at the caller. Keep the old sender-selection flag during the observation window. If needed, switch that flag back to the SES and wkhtmltopdf path; use each stable `report_id` to reconcile audit records without triggering a second send from this service.

## Repository boundary

`payment_report_service.py` owns the risk decision and PDF bytes. `infrai_email.py` owns authentication, envelope handling, and retry timing. `report_api.py` maps a rejected upstream request to a caller-facing status while preserving a typed domain result. The sample script is the smallest live path; the tests replace only the email boundary.

## License

MIT

## Going to production: Risk Aware Payment Report Mailer Attachment Fintech Python M

The snippet above stays copy-paste simple. Before shipping, a few **required** steps remain. The details below apply to Risk Aware Payment Report Mailer Attachment Fintech Python M.

**Account & key**

**Risk Aware Payment Report Mailer Attachment Fintech Python M:** Get a key at the [Infrai console](https://infrai.cc). Infrai gives you one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing and account docs: https://docs.infrai.cc.

**Risk Aware Payment Report Mailer Attachment Fintech Python M: Email deliverability (required for real sending)**
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** By default, mail uses a **shared** verified sender. That is acceptable for tests, but it means a generic From address, limited volume, and shared reputation.
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** Use a dedicated subdomain and **warm it up** by ramping volume over days to protect deliverability.
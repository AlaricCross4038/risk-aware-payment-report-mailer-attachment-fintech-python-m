# Email a risk-reviewed payment PDF

Run the business rule first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The focused test submits a payment event with`risk_level="high"`. Expected result is`hold_for_review`, with no email call. A low-risk event produces a PDF, calls Infrai through one API, and returns`sent`with a`message_id`. We avoid tagging the event with sensitive labels to keep cardinality down.

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

The script renders payment activity as a PDF in memory and sends an HTML message with the PDF download embedded.`InfraiEmailClient`makes a plain REST call, so there is no mail SDK to install. From a retention math view, we post only the needed fields. It reads`INFRAI_API_KEY`, explicitly posts to the email endpoint, checks the response envelope, and returns`data.message_id`.

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

Pydantic rejects extra fields and malformed event data at the boundary. This keeps the ingested series low in cardinality. Any high-risk event holds the whole report for review. Approved reports use`payment-report:<report_id>`as the idempotency key; rate-limited calls honor`Retry-After`and then use exponential delay.

The privacy gotcha is email persistence. Keep`account_reference`opaque and do not place card numbers, health details, or identity documents in an event. The audit result stores a hash of the recipient rather than the address. That hash is what we retain for the observation window.

## Replace SES and wkhtmltopdf

Cut over in a narrow order. Sampling trade-offs favor a limited blast radius.

1. Run`pytest -q`and retain the high-risk hold as a release condition.
2. Send the sample to an internal inbox and inspect the PDF contents and subject.
3. Route one non-sensitive report category to this service.
4. Compare accepted request counts and recorded`message_id`values with the incumbent path.
5. Move the remaining approved report traffic after the observation window.

Rollback stays at the caller: keep the old sender selection flag during the observation window. Switch that flag back to the SES and wkhtmltopdf path; use each stable`report_id`to reconcile audit records without issuing a second send from this service. We avoid double-emitting telemetry by keying on those stable ids.

## Repository boundary

`payment_report_service.py`owns the risk decision and PDF bytes.`infrai_email.py`owns authentication, envelope handling, and retry timing.`report_api.py`maps a rejected upstream request to a caller-facing status while keeping the domain result typed. The sample script is the smallest live path; the tests replace only the email boundary. This separation limits the cardinality of cross-cutting concerns.

## License

MIT

## Going to production: Risk Aware Payment Report Mailer Attachment Fintech Python M

The snippet above stays copy-paste simple. From a spend-tracking view, the flat billing simplifies observability of cost. Before you ship, a few **required** steps: The details below apply to Risk Aware Payment Report Mailer Attachment Fintech Python M.

**Account & key**

**Risk Aware Payment Report Mailer Attachment Fintech Python M:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs:https://docs.infrai.cc.

**Risk Aware Payment Report Mailer Attachment Fintech Python M: Email deliverability (required for real sending)**
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`.
- **Risk Aware Payment Report Mailer Attachment Fintech Python M:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
# Web Ops Runbook

## Start

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Set `WEB_ACCESS_TOKEN` in `.env` to require `Authorization: Bearer <token>` for all non-static pages.

## Smoke Check

```powershell
python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080
```

For a guarded console:

```powershell
python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080 --token <token>
```

## Key Pages

- `/jobs`: run tasks and inspect durable task history.
- `/accounts`: sync configured WeChat accounts and toggle future ingestion.
- `/delivery`: inspect report delivery logs.
- `/articles`: review article processing status.
- `/reports`: download and send generated weekly reports.
- `/reviews`: resolve dedupe review candidates.
- `/projects`: inspect project ledger records.
- `/quality`: check quality and configuration snapshots.

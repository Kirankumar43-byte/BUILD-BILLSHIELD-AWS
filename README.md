# 🛡️ BillShield v2 — Cloud Cost & Security Guardian for Students
*Catch the waste. Close the risk. Before the bill arrives.*

Read-only AWS scanner → plain-language findings → month-end forecast → health score → safe, confirmed fixes.
UI languages: **English, தமிழ், हिन्दी, മലയാളം**. Works with **no AWS account** via Demo Mode.

## Windows quick start (PowerShell)
```powershell
cd billshield
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q                      # expect: 24 passed
python -m streamlit run dashboard/app.py # click "Try Demo Mode"
```
Use `python -m streamlit` (not bare `streamlit`) to avoid broken-launcher errors, especially in OneDrive/space-in-path folders.

**Common Windows fixes**
- *Activate.ps1 blocked:* `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- *`python` not found:* reinstall Python 3.11+ and tick "Add python.exe to PATH", reopen the terminal.
- *AWS CLI:* install from the official AWS page, then `aws --version` and `aws configure` (use an IAM user/role built from `infra/iam_policy_readonly.json`, never root keys).
- *Venv acts strange after moving the folder:* delete `venv` and recreate it.

## How other people use it (3-step start screen)
1. **What is BillShield** - what it checks and what it never does. Or click *Try Demo Mode* (no AWS account).
2. **Connect** - choose an AWS *profile* (recommended: `aws configure --profile billshield` with a user built from `infra/iam_policy_readonly.json`) or paste keys for this browser session only (kept in memory, never saved or logged). Pick regions, click *Test connection*. The app shows the masked account ID and identity and refuses the root account.
3. **Scan** - read-only scan, then Overview shows your own waste, risks, forecast and score.
Your data never leaves your computer when you run it locally.

## Features
| Area | What it does |
|---|---|
| Cost scanner | stopped EC2, unattached EBS, unused Elastic IPs, snapshots older than 90 days, running NAT gateways |
| Security scanner | public S3 buckets, SG open to 0.0.0.0/0 on 22/3389, IAM users without MFA |
| Estimates | price table in `config.py`; every number labeled *estimate* |
| Forecast | spent + last-7-day average × remaining days, ± 1σ range; fallback if Cost Explorer is off |
| Anomaly alert | day > mean(prev 7) + 2.5 × max(σ, 10% mean) |
| Health score | `100 − min(40, waste/5) − min(60, Σ security weights)`; fully explained in the UI |
| AI explainer | rule-based in 4 languages; optional Bedrock from structured facts only, auto-fallback |
| **Savings Simulator** | tick findings → see new score + savings before you fix anything |
| **Fix-order planner** | ranked checklist, progress saved in SQLite |
| **Ask BillShield** | grounded Q&A: answers only from your findings, no invented data |
| **Bill Shock Meter** | forecast vs your budget at a glance |
| Settings | language, dark/light, accent, USD/INR (editable rate), budget, Bedrock, real-actions switch |
| Safe actions | dry-run by default; real action (release Elastic IP) needs Live mode + Settings switch + typed `CONFIRM <id>`; all logged |
| Reports | CSV (formula-injection safe) + branded PDF |

## Honest limits
- PDF reports are **English only** (Helvetica has no Tamil/Hindi/Malayalam glyphs; bundling Noto fonts needs complex-script shaping that ReportLab doesn't do reliably).
- Translations are AI-assisted: **have native speakers review them**.
- "Idle" EC2 (CPU-based) detection is not included; stopped instances are.
- Prices are approximate estimates — verify at aws.amazon.com/pricing. AWS free-tier rules change; check current AWS docs.
- Cost Explorer costs about $0.01/request. Bedrock and App Runner/EC2 can cost money. Nothing here was deployed or tested against a real AWS account — only against `moto` mocks.
- Favicon is an emoji; the SVG logo is in `dashboard/assets/logo.svg`.
- Light theme is basic; dark is the polished default.

## Architecture
```
Streamlit UI ──> scanners (boto3, read-only) ──> findings ──> scoring / forecast / anomaly / ai / ask
      │                                                          │
      └── SQLite (settings, audit log, plan) <── actions (dry-run default) ──> alerts (SNS)
EventBridge ──> Lambda (infra/lambda_handler.py) ──> scan ──> SNS email
```

## Security
Read-only IAM policy in `infra/`. No hardcoded secrets (`.env`, profiles, IAM roles). Inputs validated (allocation-id regex, typed confirmation). Defensive checks only. See `infra/DEPLOY.md` before deploying.

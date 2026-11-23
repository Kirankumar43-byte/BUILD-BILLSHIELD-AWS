# Deploy BillShield (nothing here was run against real AWS/hosting; verify each step in current docs)

## A. Free public DEMO (recommended for recruiters) - Streamlit Community Cloud
1. Push the project to a PUBLIC GitHub repo (`.env`, `venv`, `*.db` are already git-ignored).
2. share.streamlit.io -> New app -> pick the repo, branch `main`, main file `dashboard/app.py`.
3. Advanced settings -> Secrets/env: `BILLSHIELD_DEMO_ONLY = "true"` (hides the AWS-connect step).
4. Deploy, then open the URL and click "Try Demo Mode".

## B. Docker (any host)
```
docker build -t billshield .
docker run -p 8501:8501 billshield          # demo-only by default
```
To use it privately with your own AWS profile, run locally instead of hosting it.

## C. AWS (may cost money - check pricing first)
- EC2 t3.micro / App Runner: keep `BILLSHIELD_DEMO_ONLY=true` if the URL is public. Put it behind a login or IP allow-list if you ever turn it off.
- App Runner and idle EC2 bill hourly. Stop/delete when done; set an AWS Budget alert first.

## D. Daily scan emails (Lambda + EventBridge + SNS)
1. SNS: create topic `billshield-alerts`, add your email, confirm the email.
2. IAM: role for Lambda = `iam_policy_readonly.json` + `sns:Publish` on that topic (see `iam_policy_optional.json`).
3. Package: zip the folders `scanners forecast scoring alerts i18n` plus `config.py models.py` and `infra/lambda_handler.py` placed at the zip root; install `python-dotenv` into the zip or leave it out (config tolerates its absence). Runtime Python 3.12, handler `lambda_handler.handler`.
4. Env vars: `SNS_TOPIC_ARN`, `BILLSHIELD_REGIONS`. Only set `USE_COST_EXPLORER=true` if you accept ~$0.01 per request.
5. EventBridge schedule `cron(0 3 * * ? *)` -> that Lambda.
6. Test once from the Lambda console and read the CloudWatch logs.

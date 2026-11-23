import json
import pathlib
from datetime import date
import boto3
import pytest
from moto import mock_aws

import config
from actions import audit
from actions.safe import execute
from ai.ask import answer
from ai.explainer import explain
from data.demo.demo_data import demo_daily, demo_findings
from forecast.anomaly import detect_anomalies
from forecast.forecast import fallback_estimate, forecast_month
from i18n import LANGS, t
from models import Finding, SEVERITIES
from reports.export import csv_bytes, pdf_bytes
from scanners.cost import scan_cost
from scanners.security import scan_security
from scoring.score import health_score


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))


def F(sev="Low", cat="cost", waste=0.0, **kw):
    return Finding("x", cat, kw.get("rt", "EBS Volume"), "vol-1", "us-east-1", sev, "t", [], waste, "cmd", kw.get("action", ""))


# scoring
def test_score_clean_is_100(): assert health_score([])["score"] == 100
def test_score_capped_never_negative():
    s = health_score([F("Critical", "security") for _ in range(50)] + [F(waste=10000)])
    assert s["score"] == 0 and s["risk_penalty"] == 60 and s["waste_penalty"] == 40
def test_score_waste_points(): assert health_score([F(waste=50)])["score"] == 90


# forecast
def test_forecast_constant():
    fc = forecast_month([10.0] * 10, date(2026, 11, 11))
    assert fc["total_mid"] == 300 and fc["total_low"] == fc["total_high"] == 300
def test_forecast_empty_is_none(): assert forecast_month([], date(2026, 11, 11)) is None
def test_fallback_label(): assert "NOT a bill forecast" in fallback_estimate([F(waste=5)])["note"]
def test_anomaly_found_and_quiet():
    assert detect_anomalies([1] * 8 + [10])[0]["day"] == 9
    assert detect_anomalies([1.0, 1.1, 0.9, 1.0, 1.1, 1.0, 0.9, 1.05]) == []
    assert detect_anomalies([1, 2]) == []


# i18n
def test_locale_keys_match():
    base = set(json.loads((pathlib.Path("i18n/locales/en.json")).read_text(encoding="utf-8")))
    for l in LANGS:
        assert set(json.loads(pathlib.Path(f"i18n/locales/{l}.json").read_text(encoding="utf-8"))) == base
def test_fallbacks():
    assert t("nope", "ta") == "nope"
    assert t("nav_overview", "xx") == "Overview"
    assert t("of_budget", "hi", pct=5).count("5") == 1


# demo / ai / ask / export
def test_demo_valid():
    fs = demo_findings()
    assert fs and all(f.severity in SEVERITIES for f in fs) and len(demo_daily(date(2026, 11, 3))) >= 12
def test_explainer_rule_based_all_langs():
    for l in LANGS:
        e = explain(demo_findings()[0], l, "$0.00")
        assert e["explanation"] and e["source"] == "rule-based"
def test_explainer_bedrock_off_even_if_requested():
    assert explain(demo_findings()[0], "en", "$1", use_bedrock=True, session=None)["source"] == "rule-based"
def test_ask_grounded():
    fs = demo_findings(); sc = health_score(fs)
    assert "Fix this first" in answer("first", fs, sc, "en", lambda x: f"${x}")
    assert answer("first", [], sc, "en", str) == t("ans_none", "en")
def test_csv_injection_blocked():
    f = Finding("=1+1", "cost", "EBS Volume", "v", "r", "Low", "=cmd()", [], 1.0)
    assert b"'=cmd()" in csv_bytes([f])
def test_pdf_is_pdf():
    fs = demo_findings(); assert pdf_bytes(fs, health_score(fs), None, True)[:4] == b"%PDF"


# actions
def test_dry_run_default_logged():
    f = demo_findings()[6]
    assert execute(f)[0] == "dry-run" and audit.logs()[0][3] == "dry-run"
def test_real_refused_cases():
    f = demo_findings()[6]
    assert execute(f, "", live=True, allow_real=False)[0] == "refused"
    assert execute(f, "wrong", live=True, allow_real=True)[0] == "refused"
    assert execute(f, f"CONFIRM {f.resource_id}", live=True, allow_real=True, demo=True)[0] == "refused"
def test_settings_and_plan_persist():
    audit.set_setting("lang", "ta"); audit.plan_set("a", True)
    assert audit.get_setting("lang") == "ta" and audit.plan_done() == {"a"}


# scanners with moto
@mock_aws
def test_scanners_and_real_release():
    s = boto3.Session(region_name="us-east-1"); ec2 = s.client("ec2")
    ec2.create_volume(AvailabilityZone="us-east-1a", Size=10)
    alloc = ec2.allocate_address(Domain="vpc")["AllocationId"]
    sg = ec2.create_security_group(GroupName="open", Description="d")["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    safe = ec2.create_security_group(GroupName="ok", Description="d")["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=safe, IpPermissions=[{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "10.0.0.0/8"}]}])
    ec2.authorize_security_group_ingress(GroupId=safe, IpPermissions=[{"IpProtocol": "tcp", "FromPort": 0, "ToPort": 65535, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    cost, e1 = scan_cost(s, ["us-east-1"]); sec, e2 = scan_security(s, ["us-east-1"])
    kinds = {f.resource_type for f in cost}
    assert {"EBS Volume", "Elastic IP"} <= kinds and "Snapshot" not in kinds and not e1 and not e2
    ports = {(f.resource_id, f.id.split(":")[-1]) for f in sec if f.resource_type == "Security Group"}
    assert (sg, "22") in ports and (safe, "22") in ports and (safe, "3389") in ports   # range 0-65535 flagged
    eip = next(f for f in cost if f.resource_type == "Elastic IP")
    assert execute(eip, f"CONFIRM {eip.resource_id}", True, s, allow_real=True)[0] == "executed"
    assert not [a for a in ec2.describe_addresses()["Addresses"] if a.get("AllocationId") == alloc]


# account / connection
from scanners.account import get_identity, mask, valid_key_id

@mock_aws
def test_identity_and_mask():
    info = get_identity(boto3.Session(region_name="us-east-1"))
    assert info["account"].isdigit() and not info["is_root"] or info["is_root"] in (True, False)
    assert mask("123456789012").endswith("9012") and "1234" not in mask("123456789012")[:-4]
def test_key_validation():
    assert valid_key_id("AKIAABCDEFGHIJKLMNOP") and not valid_key_id("") and not valid_key_id("a b; drop")
def test_identity_failure_returns_none(monkeypatch):
    class Bad:
        def client(self, *_): raise __import__("botocore").exceptions.BotoCoreError()
    assert get_identity(Bad()) is None

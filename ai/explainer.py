"""Plain-language explanations built ONLY from structured findings.
Rule-based by default. Bedrock (optional) may rewrite the explanation; any failure
falls back to rules, so the app never shows invented data."""
import json
import config
from i18n import t, LANGS

KEY = {"EC2 Instance": "ec2", "EBS Volume": "ebs", "Elastic IP": "eip", "Snapshot": "snap",
       "NAT Gateway": "nat", "Security Group": "sg", "S3 Bucket": "s3", "IAM User": "iam"}


def rule_based(f, lang, amount):
    facts = list(f.facts)
    facts.append(t("fact_waste", lang, amount=amount) if f.monthly_waste > 0 else t("fact_none", lang))
    return {"facts": facts, "explanation": t("why_" + KEY.get(f.resource_type, "ec2"), lang),
            "suggestion": t("suggest", lang), "source": "rule-based"}


def explain(f, lang="en", amount="$0.00", use_bedrock=False, session=None):
    base = rule_based(f, lang, amount)
    if not (use_bedrock and config.BEDROCK_MODEL_ID and session):
        return base
    try:
        client = session.client("bedrock-runtime", region_name=config.REGIONS[0])
        system = ("Explain the AWS finding in 2 short sentences for a student, in "
                  f"{LANGS.get(lang, 'English')}. Use ONLY the JSON facts. Never invent resources or numbers.")
        r = client.converse(
            modelId=config.BEDROCK_MODEL_ID, system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": json.dumps(f.to_dict())}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0.2})
        text = r["output"]["message"]["content"][0]["text"].strip()
        if text:
            base["explanation"], base["source"] = text, "bedrock"
    except Exception:
        pass
    return base

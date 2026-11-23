"""Who am I connected as? sts:GetCallerIdentity needs no IAM permission."""
import re
from botocore.exceptions import BotoCoreError, ClientError

KEY_RE = re.compile(r"^[A-Z0-9]{16,128}$")


def valid_key_id(k):
    return bool(KEY_RE.match((k or "").strip()))


def get_identity(session):
    try:
        r = session.client("sts").get_caller_identity()
    except (BotoCoreError, ClientError):
        return None
    return {"account": r["Account"], "arn": r["Arn"], "is_root": r["Arn"].endswith(":root")}


def mask(account):
    return "••••••••" + account[-4:]

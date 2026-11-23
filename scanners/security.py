"""Read-only security scanners (defensive checks only)."""
from botocore.exceptions import BotoCoreError, ClientError
from config import RISKY_PORTS
from models import Finding

PORT_NAMES = {22: "SSH", 3389: "RDP"}


def _sg_findings(session, region):
    ec2 = session.client("ec2", region_name=region)
    out = []
    for page in ec2.get_paginator("describe_security_groups").paginate():
        for sg in page["SecurityGroups"]:
            hit = set()
            for p in sg.get("IpPermissions", []):
                if not any(r.get("CidrIp") == "0.0.0.0/0" for r in p.get("IpRanges", [])):
                    continue
                for port in RISKY_PORTS:
                    if p.get("IpProtocol") == "-1" or (
                            "FromPort" in p and p["FromPort"] <= port <= p["ToPort"]):
                        hit.add(port)
            for port in sorted(hit):
                gid = sg["GroupId"]
                out.append(Finding(
                    f"sg:{gid}:{port}", "security", "Security Group", gid, region, "Critical",
                    f"{PORT_NAMES[port]} (port {port}) open to the whole internet on {gid}",
                    [f"Group name: {sg['GroupName']}", f"Port {port} allows 0.0.0.0/0"], 0.0,
                    f"aws ec2 revoke-security-group-ingress --group-id {gid} --protocol tcp "
                    f"--port {port} --cidr 0.0.0.0/0 --region {region} --dry-run"))
    return out


def _bucket_public(s3, b):
    try:
        if s3.get_bucket_policy_status(Bucket=b)["PolicyStatus"]["IsPublic"]:
            return True
    except ClientError:
        pass
    try:
        if all(s3.get_public_access_block(Bucket=b)["PublicAccessBlockConfiguration"].values()):
            return False
    except ClientError:
        pass
    try:
        for g in s3.get_bucket_acl(Bucket=b)["Grants"]:
            if g.get("Grantee", {}).get("URI", "").endswith("/global/AllUsers"):
                return True
    except ClientError:
        pass
    return False


def _s3_findings(session):
    s3 = session.client("s3")
    out = []
    for b in s3.list_buckets().get("Buckets", []):
        name = b["Name"]
        if _bucket_public(s3, name):
            out.append(Finding(
                f"s3:{name}", "security", "S3 Bucket", name, "global", "Critical",
                f"Bucket {name} may be publicly accessible",
                ["Policy or ACL allows public access and Block Public Access is not fully on"], 0.0,
                f"aws s3api put-public-access-block --bucket {name} --public-access-block-configuration "
                "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"))
    return out


def _iam_findings(session):
    iam = session.client("iam")
    out = []
    for page in iam.get_paginator("list_users").paginate():
        for u in page["Users"]:
            name = u["UserName"]
            if iam.list_mfa_devices(UserName=name)["MFADevices"]:
                continue
            try:
                iam.get_login_profile(UserName=name)
                console = True
            except iam.exceptions.NoSuchEntityException:
                console = False
            out.append(Finding(
                f"iam:{name}", "security", "IAM User", name, "global",
                "High" if console else "Low", f"IAM user {name} has no MFA",
                [f"Console password: {'yes' if console else 'no'}", "MFA devices: 0"], 0.0,
                f"# Console: IAM > Users > {name} > Security credentials > Assign MFA device"))
    return out


def scan_security(session, regions):
    findings, errors = [], []
    for r in regions:
        try:
            findings += _sg_findings(session, r)
        except (ClientError, BotoCoreError) as e:
            errors.append(f"Security group scan failed in {r}: {e}")
    for label, fn in (("S3", _s3_findings), ("IAM", _iam_findings)):
        try:
            findings += fn(session)
        except (ClientError, BotoCoreError) as e:
            errors.append(f"{label} scan failed: {e}")
    return findings, errors

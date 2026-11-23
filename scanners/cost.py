"""Read-only cost scanners. Only Describe* calls are used."""
from datetime import datetime, timezone, timedelta
from botocore.exceptions import BotoCoreError, ClientError
from config import PRICES, SNAPSHOT_MAX_AGE_DAYS
from models import Finding


def scan_region(session, region):
    ec2 = session.client("ec2", region_name=region)
    out = []
    # 1) Stopped instances (you still pay for their disks)
    pages = ec2.get_paginator("describe_instances").paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}])
    for page in pages:
        for res in page["Reservations"]:
            for i in res["Instances"]:
                iid = i["InstanceId"]
                vols = ec2.describe_volumes(
                    Filters=[{"Name": "attachment.instance-id", "Values": [iid]}])["Volumes"]
                gb = sum(v["Size"] for v in vols)
                out.append(Finding(
                    f"ec2:{iid}", "cost", "EC2 Instance", iid, region, "Low",
                    f"Stopped instance {iid}",
                    ["State: stopped", f"Attached EBS storage: {gb} GB"],
                    round(gb * PRICES["ebs_gb_month"], 2),
                    f"aws ec2 terminate-instances --instance-ids {iid} --region {region} --dry-run"))
    # 2) Unattached EBS volumes
    for page in ec2.get_paginator("describe_volumes").paginate(
            Filters=[{"Name": "status", "Values": ["available"]}]):
        for v in page["Volumes"]:
            vid = v["VolumeId"]
            out.append(Finding(
                f"ebs:{vid}", "cost", "EBS Volume", vid, region, "Medium",
                f"Unattached volume {vid}",
                [f"Size: {v['Size']} GB", "Status: available (not attached)"],
                round(v["Size"] * PRICES["ebs_gb_month"], 2),
                f"aws ec2 delete-volume --volume-id {vid} --region {region} --dry-run"))
    # 3) Unused Elastic IPs
    for a in ec2.describe_addresses()["Addresses"]:
        if "AssociationId" not in a:
            aid = a.get("AllocationId", a.get("PublicIp"))
            out.append(Finding(
                f"eip:{aid}", "cost", "Elastic IP", aid, region, "Medium",
                f"Unused Elastic IP {a.get('PublicIp', aid)}",
                ["Not associated with any instance or network interface"],
                PRICES["eip_idle_month"],
                f"aws ec2 release-address --allocation-id {aid} --region {region} --dry-run",
                "release_ip"))
    # 4) Old snapshots
    cutoff = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_MAX_AGE_DAYS)
    for page in ec2.get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
        for s in page["Snapshots"]:
            if s["StartTime"] < cutoff:
                sid = s["SnapshotId"]
                age = (datetime.now(timezone.utc) - s["StartTime"]).days
                out.append(Finding(
                    f"snap:{sid}", "cost", "Snapshot", sid, region, "Low",
                    f"Old snapshot {sid}",
                    [f"Age: {age} days", f"Volume size: {s['VolumeSize']} GB"],
                    round(s["VolumeSize"] * PRICES["snapshot_gb_month"], 2),
                    f"aws ec2 delete-snapshot --snapshot-id {sid} --region {region} --dry-run"))
    # 5) Running NAT gateways
    nats = ec2.describe_nat_gateways(Filter=[{"Name": "state", "Values": ["available"]}])
    for n in nats["NatGateways"]:
        nid = n["NatGatewayId"]
        out.append(Finding(
            f"nat:{nid}", "cost", "NAT Gateway", nid, region, "High",
            f"Running NAT gateway {nid}",
            ["State: available (billed per hour even with no traffic)"],
            PRICES["nat_gateway_month"],
            f"# Review first: aws ec2 describe-nat-gateways --nat-gateway-ids {nid} --region {region}"))
    return out


def scan_cost(session, regions):
    findings, errors = [], []
    for r in regions:
        try:
            findings += scan_region(session, r)
        except (ClientError, BotoCoreError) as e:
            errors.append(f"Cost scan failed in {r}: {e}")
    return findings, errors

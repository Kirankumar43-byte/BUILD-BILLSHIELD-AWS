"""Synthetic demo dataset. Nothing here is real AWS data."""
import calendar
from models import Finding


def demo_findings():
    F = Finding
    return [
        F("sg:sg-0a1b2c3d:22", "security", "Security Group", "sg-0a1b2c3d", "us-east-1", "Critical",
          "SSH (port 22) open to the whole internet on sg-0a1b2c3d",
          ["Group name: dev-web", "Port 22 allows 0.0.0.0/0"], 0.0,
          "aws ec2 revoke-security-group-ingress --group-id sg-0a1b2c3d --protocol tcp --port 22 --cidr 0.0.0.0/0 --dry-run"),
        F("sg:sg-0e4f5a6b:3389", "security", "Security Group", "sg-0e4f5a6b", "us-east-1", "Critical",
          "RDP (port 3389) open to the whole internet on sg-0e4f5a6b",
          ["Group name: win-lab", "Port 3389 allows 0.0.0.0/0"], 0.0,
          "aws ec2 revoke-security-group-ingress --group-id sg-0e4f5a6b --protocol tcp --port 3389 --cidr 0.0.0.0/0 --dry-run"),
        F("s3:college-project-uploads", "security", "S3 Bucket", "college-project-uploads", "global", "Critical",
          "Bucket college-project-uploads may be publicly accessible",
          ["Policy or ACL allows public access and Block Public Access is not fully on"], 0.0,
          "aws s3api put-public-access-block --bucket college-project-uploads --public-access-block-configuration "
          "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"),
        F("iam:intern-ravi", "security", "IAM User", "intern-ravi", "global", "High", "IAM user intern-ravi has no MFA",
          ["Console password: yes", "MFA devices: 0"], 0.0, "# Console: IAM > Users > intern-ravi > Assign MFA device"),
        F("iam:ci-bot", "security", "IAM User", "ci-bot", "global", "Low", "IAM user ci-bot has no MFA",
          ["Console password: no", "MFA devices: 0"], 0.0, "# Console: IAM > Users > ci-bot > Assign MFA device"),
        F("nat:nat-0123456789abcdef0", "cost", "NAT Gateway", "nat-0123456789abcdef0", "us-east-1", "High",
          "Running NAT gateway nat-0123456789abcdef0", ["State: available (billed per hour even with no traffic)"],
          32.85, "# Review first: aws ec2 describe-nat-gateways --nat-gateway-ids nat-0123456789abcdef0"),
        F("eip:eipalloc-0a1b2c3d4e5f60718", "cost", "Elastic IP", "eipalloc-0a1b2c3d4e5f60718", "us-east-1", "Medium",
          "Unused Elastic IP 3.91.10.22", ["Not associated with any instance or network interface"], 3.65,
          "aws ec2 release-address --allocation-id eipalloc-0a1b2c3d4e5f60718 --dry-run", "release_ip"),
        F("eip:eipalloc-0f9e8d7c6b5a40312", "cost", "Elastic IP", "eipalloc-0f9e8d7c6b5a40312", "us-east-1", "Medium",
          "Unused Elastic IP 54.12.200.9", ["Not associated with any instance or network interface"], 3.65,
          "aws ec2 release-address --allocation-id eipalloc-0f9e8d7c6b5a40312 --dry-run", "release_ip"),
        F("ebs:vol-0aaa111122223333", "cost", "EBS Volume", "vol-0aaa111122223333", "us-east-1", "Medium",
          "Unattached volume vol-0aaa111122223333", ["Size: 200 GB", "Status: available (not attached)"], 16.0,
          "aws ec2 delete-volume --volume-id vol-0aaa111122223333 --dry-run"),
        F("ebs:vol-0bbb444455556666", "cost", "EBS Volume", "vol-0bbb444455556666", "us-east-1", "Medium",
          "Unattached volume vol-0bbb444455556666", ["Size: 50 GB", "Status: available (not attached)"], 4.0,
          "aws ec2 delete-volume --volume-id vol-0bbb444455556666 --dry-run"),
        F("ec2:i-0123abcd4567ef890", "cost", "EC2 Instance", "i-0123abcd4567ef890", "us-east-1", "Low",
          "Stopped instance i-0123abcd4567ef890", ["State: stopped", "Attached EBS storage: 100 GB"], 8.0,
          "aws ec2 terminate-instances --instance-ids i-0123abcd4567ef890 --dry-run"),
        F("snap:snap-0abc1234def567890", "cost", "Snapshot", "snap-0abc1234def567890", "us-east-1", "Low",
          "Old snapshot snap-0abc1234def567890", ["Age: 212 days", "Volume size: 120 GB"], 6.0,
          "aws ec2 delete-snapshot --snapshot-id snap-0abc1234def567890 --dry-run"),
    ]


def demo_daily(today):
    days = calendar.monthrange(today.year, today.month)[1]
    n = min(max(today.day - 1, 12), days - 1)
    base = [4.2, 4.6, 4.4, 4.8, 4.3, 4.5, 4.7]
    return [round(base[i % 7] + 0.03 * i + (6.0 if i == 11 else 0), 2) for i in range(n)]

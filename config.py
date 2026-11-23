"""Central settings. Secrets come from .env or IAM roles, never from code."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # Lambda runtime may not bundle python-dotenv
    pass

# ESTIMATED USD prices (us-east-1, approximate, checked Nov 2026 from memory).
# Verify at https://aws.amazon.com/pricing/ - every number in the app is an ESTIMATE.
PRICES = {
    "ebs_gb_month": 0.08,        # gp3 per GB-month
    "snapshot_gb_month": 0.05,   # upper bound; snapshots are incremental
    "eip_idle_month": 3.65,      # $0.005/hr public IPv4 x 730h
    "nat_gateway_month": 32.85,  # $0.045/hr x 730h (excludes data processing)
}
SNAPSHOT_MAX_AGE_DAYS = 90
RISKY_PORTS = (22, 3389)

BUDGET = float(os.getenv("BILLSHIELD_BUDGET", "100"))
REGIONS = [r.strip() for r in os.getenv("BILLSHIELD_REGIONS", "us-east-1").split(",") if r.strip()]
DB_PATH = os.getenv("BILLSHIELD_DB", "billshield.db")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "")   # empty = Bedrock off
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")         # empty = alerts printed only
ALLOW_REAL = os.getenv("BILLSHIELD_ALLOW_REAL_ACTIONS", "false").lower() == "true"

#!/usr/bin/env python3
"""Export an EC2 inventory (all or selected regions) to CSV.

Requires: boto3 and AWS credentials (env vars, profile or role).

Examples:
    ./aws_ec2_inventory.py --regions ap-south-1 us-east-1 -o inventory.csv
    ./aws_ec2_inventory.py --all-regions --profile dev
"""
import argparse
import csv
import sys

import boto3


def tag(tags, key):
    return next((t["Value"] for t in tags or [] if t["Key"] == key), "")


def list_regions(session):
    ec2 = session.client("ec2", region_name="us-east-1")
    return [r["RegionName"] for r in ec2.describe_regions()["Regions"]]


def collect(session, region):
    ec2 = session.client("ec2", region_name=region)
    for page in ec2.get_paginator("describe_instances").paginate():
        for reservation in page["Reservations"]:
            for i in reservation["Instances"]:
                yield {
                    "region": region,
                    "instance_id": i["InstanceId"],
                    "name": tag(i.get("Tags"), "Name"),
                    "state": i["State"]["Name"],
                    "type": i["InstanceType"],
                    "private_ip": i.get("PrivateIpAddress", ""),
                    "public_ip": i.get("PublicIpAddress", ""),
                    "launch_time": i["LaunchTime"].isoformat(),
                    "environment": tag(i.get("Tags"), "Environment"),
                }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--regions", nargs="+")
    p.add_argument("--all-regions", action="store_true")
    p.add_argument("--profile")
    p.add_argument("-o", "--output", default="ec2_inventory.csv")
    args = p.parse_args()

    session = boto3.Session(profile_name=args.profile)
    regions = list_regions(session) if args.all_regions else (args.regions or [session.region_name or "ap-south-1"])

    fields = ["region", "instance_id", "name", "state", "type", "private_ip", "public_ip", "launch_time", "environment"]
    count = 0
    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for region in regions:
            for row in collect(session, region):
                writer.writerow(row)
                count += 1
    print(f"Wrote {count} instances to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

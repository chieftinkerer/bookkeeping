#!/usr/bin/env python3
"""
s3_secure_setup.py
One-time secure configuration for your backup bucket.

What it does:
- Blocks all public access on the bucket
- Enables default encryption (SSE-KMS if KMS_KEY_ID provided, else SSE-S3)
- Enables bucket versioning
- Adds a lifecycle rule: transition noncurrent versions to Glacier Deep Archive after 365 days
- (Optional) Creates a deny policy for non-SSL requests (enforce HTTPS)

Usage:
  pip install boto3
  export AWS_PROFILE=yourprofile   # or configure via SSO/default
  python s3_secure_setup.py --bucket my-personal-finance-data --kms-key-id alias/my-kms-key --deny-non-ssl
"""
import argparse
import json
import boto3

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--kms-key-id", default=None, help="KMS CMK ID or alias (alias/my-key). Optional.")
    ap.add_argument("--deny-non-ssl", action="store_true")
    args = ap.parse_args()

    s3 = boto3.client("s3")

    print("Blocking public access...")
    s3.put_public_access_block(
        Bucket=args.bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    print("Setting default encryption...")
    if args.kms_key_id:
        s3.put_bucket_encryption(
            Bucket=args.bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "aws:kms",
                        "KMSMasterKeyID": args.kms_key_id
                    },
                    "BucketKeyEnabled": True
                }]
            }
        )
    else:
        s3.put_bucket_encryption(
            Bucket=args.bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    },
                    "BucketKeyEnabled": True
                }]
            }
        )

    print("Enabling versioning...")
    s3.put_bucket_versioning(
        Bucket=args.bucket,
        VersioningConfiguration={"Status": "Enabled"}
    )

    print("Adding lifecycle rule...")
    s3.put_bucket_lifecycle_configuration(
        Bucket=args.bucket,
        LifecycleConfiguration={
            "Rules": [{
                "ID": "noncurrent-to-deep-archive",
                "Filter": {"Prefix": ""},
                "Status": "Enabled",
                "NoncurrentVersionTransitions": [{
                    "NoncurrentDays": 365,
                    "StorageClass": "DEEP_ARCHIVE"
                }],
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
            }]
        }
    )

    if args.deny_non_ssl:
        print("Enforcing HTTPS-only via bucket policy...")
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{args.bucket}",
                    f"arn:aws:s3:::{args.bucket}/*"
                ],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}}
            }]
        }
        s3.put_bucket_policy(Bucket=args.bucket, Policy=json.dumps(policy))

    print("Done. Review bucket settings in the AWS Console to confirm.")

if __name__ == "__main__":
    main()

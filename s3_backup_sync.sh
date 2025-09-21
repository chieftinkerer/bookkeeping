#!/usr/bin/env bash
# s3_backup_sync.sh
# Sync a local folder of CSVs (or an encrypted vault folder) to S3.
# Requires: AWS CLI v2 configured (`aws configure sso` or `aws configure`)
#
# Usage:
#   export S3_BUCKET="my-personal-finance-data"
#   export S3_PREFIX="backups/csvs"              # optional
#   export LOCAL_DIR="$HOME/FinanceVault"        # or ./downloads
#   export KMS_KEY_ID="alias/my-kms-key"         # or leave empty to use SSE-S3
#   ./s3_backup_sync.sh
#
# Notes:
# - This script NEVER deletes from S3 (no --delete), to avoid accidents.
# - Uses --exact-timestamps for precise sync behavior.
# - Blocks accidental upload of obvious private files via --exclude examples.
set -euo pipefail

: "${S3_BUCKET:?Set S3_BUCKET}"
: "${LOCAL_DIR:?Set LOCAL_DIR}"
S3_PREFIX="${S3_PREFIX:-backups/csvs}"
KMS_KEY_ID="${KMS_KEY_ID:-}"

DEST="s3://${S3_BUCKET}/${S3_PREFIX}"
echo "Syncing ${LOCAL_DIR} -> ${DEST}"

EXTRA_OPTS=(--only-show-errors --exact-timestamps)
if [ -n "$KMS_KEY_ID" ]; then
  EXTRA_OPTS+=(--sse aws:kms --sse-kms-key-id "$KMS_KEY_ID")
else
  EXTRA_OPTS+=(--sse AES256)
fi

aws s3 sync "$LOCAL_DIR" "$DEST" \
  --exclude ".DS_Store" \
  --exclude "*.tmp" \
  --exclude "*.lock" \
  "${EXTRA_OPTS[@]}"

echo "Done."

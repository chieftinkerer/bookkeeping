#!/usr/bin/env bash
# s3_restore_sync.sh
# Sync from S3 to local folder (pull latest files for a second workstation).
# Requires: AWS CLI v2 configured.
#
# Usage:
#   export S3_BUCKET="my-personal-finance-data"
#   export S3_PREFIX="backups/csvs"
#   export LOCAL_DIR="$HOME/FinanceVault"
#   ./s3_restore_sync.sh
#
# Notes:
# - Does NOT delete local files; it only brings down what's in S3.
# - If using an encrypted vault (Cryptomator/VeraCrypt), point LOCAL_DIR at the vault folder.
set -euo pipefail

: "${S3_BUCKET:?Set S3_BUCKET}"
: "${LOCAL_DIR:?Set LOCAL_DIR}"
S3_PREFIX="${S3_PREFIX:-backups/csvs}"

SRC="s3://${S3_BUCKET}/${S3_PREFIX}"
echo "Syncing ${SRC} -> ${LOCAL_DIR}"

aws s3 sync "$SRC" "$LOCAL_DIR" \
  --only-show-errors \
  --exact-timestamps

echo "Done."

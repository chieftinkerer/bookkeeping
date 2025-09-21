# S3 Backup / Restore

## Setup (secure bucket)
```bash
pip install boto3
python s3_secure_setup.py --bucket my-personal-finance-data --kms-key-id alias/my-kms-key --deny-non-ssl
```

## Backup (upload)
```bash
export S3_BUCKET="my-personal-finance-data"
export S3_PREFIX="backups/csvs"
export LOCAL_DIR="C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data"
export KMS_KEY_ID="alias/my-kms-key"   # optional
chmod +x s3_backup_sync.sh
./s3_backup_sync.sh
```

## Restore (download)
```bash
export S3_BUCKET="my-personal-finance-data"
export S3_PREFIX="backups/csvs"
export LOCAL_DIR="C:\Users\james\Digital Storage\Personal - Documents\Financials\AI Bookkeeping\Data"
chmod +x s3_restore_sync.sh
./s3_restore_sync.sh
```

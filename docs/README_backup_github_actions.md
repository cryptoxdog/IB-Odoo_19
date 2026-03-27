# PlasticOS Disaster Recovery — External Backup via GitHub Actions

**File:** `.github/workflows/backup-to-s3.yml`
**Strategy:** External pull — backups are pulled by infrastructure you own, running on GitHub's schedule, storing to your S3 bucket. Odoo.sh never sees the AWS credentials.

---

## Why External Pull

Any backup mechanism running *inside* Odoo.sh is also compromised if Odoo.sh is hacked — including cron jobs, S3 credentials stored as system parameters, and the backup module itself. The GitHub Actions approach runs entirely outside Odoo.sh. Odoo.sh has zero visibility into the S3 destination.

---

## Architecture

```
GitHub Actions (runs daily 3 AM UTC / Sunday 4 AM UTC)
  │
  ├─ SSH into Odoo.sh → SCP /home/odoo/backup.daily/*.sql.gz
  │
  ├─ Validate (reject if < 1MB — likely corrupt)
  │
  ├─ Upload to S3 → backups/daily/ or backups/weekly/
  │
  └─ S3 Object Lock (COMPLIANCE mode) → nobody can delete backups for 90 days
```

---

## Required Secrets (GitHub → Settings → Secrets and Variables → Actions)

| Secret | Value |
|---|---|
| `ODOOSH_SSH_KEY` | Private key for the `plasticos-backup-bot` SSH keypair |
| `ODOOSH_SSH_HOST` | `<build-id>@<project>.odoo.com` (from Odoo.sh SSH tab) |
| `AWS_ACCESS_KEY_ID` | Write-only IAM user key |
| `AWS_SECRET_ACCESS_KEY` | Write-only IAM user secret |
| `S3_BUCKET` | `plasticos-disaster-recovery` |
| `ODOO_DB_NAME` | Your production DB name (run `echo $PGDATABASE` in Odoo.sh shell) |

**SSH Key setup:**
```bash
ssh-keygen -t ed25519 -C "plasticos-backup-bot" -f ~/.ssh/plasticos_backup_bot
# Add public key to: Odoo.sh Dashboard → Project → Settings → SSH Keys
```

---

## S3 Bucket Configuration

### Create with Object Lock (must be enabled at creation time)

```bash
aws s3api create-bucket \
  --bucket plasticos-disaster-recovery \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket plasticos-disaster-recovery \
  --versioning-configuration Status=Enabled

aws s3api put-object-lock-configuration \
  --bucket plasticos-disaster-recovery \
  --object-lock-configuration '{
    "ObjectLockEnabled": "Enabled",
    "Rule": {
      "DefaultRetention": {
        "Mode": "COMPLIANCE",
        "Days": 90
      }
    }
  }'
```

**COMPLIANCE mode:** Not even the AWS root account can delete objects during the 90-day retention period.

### IAM Policy (Write-Only)

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:PutObjectTagging"],
    "Resource": "arn:aws:s3:::plasticos-disaster-recovery/*"
  }]
}
```

This IAM user **cannot read, list, or delete** existing backups. Leaked credentials cannot destroy your recovery point.

### Lifecycle Policy

```json
{
  "Rules": [
    {
      "ID": "DailyExpire30Days",
      "Filter": { "Prefix": "backups/daily/" },
      "Status": "Enabled",
      "Expiration": { "Days": 30 }
    },
    {
      "ID": "WeeklyToGlacierDeepArchive",
      "Filter": { "Prefix": "backups/weekly/" },
      "Status": "Enabled",
      "Transitions": [
        { "Days": 90, "StorageClass": "GLACIER_DEEP_ARCHIVE" }
      ]
    }
  ]
}
```

Daily backups expire at 30 days. Weekly archives move to Glacier Deep Archive (~$0.00099/GB/month) at 90 days and stay forever.

---

## Workflow Behavior

| Schedule | Backup Type | S3 Prefix | Retention |
|---|---|---|---|
| Daily 3 AM UTC | Latest `.sql.gz` from Odoo.sh | `backups/daily/` | 30 days |
| Sunday 4 AM UTC | Same file | `backups/weekly/` | Forever (→ Glacier at 90d) |
| Manual (`workflow_dispatch`) | On-demand | `backups/daily/` | 30 days |

**Validation gate:** Backup is rejected before upload if file size < 1MB (likely corrupt or empty DB export). GitHub Actions will email on failure.

---

## Threat Model Coverage

| Threat | Mitigation |
|---|---|
| Odoo.sh fully compromised | Backups already in S3; GitHub Actions doesn't run on Odoo.sh |
| Attacker gets AWS write credentials | Write-only policy — can't read, list, or delete existing backups |
| Attacker gets AWS root account | COMPLIANCE Object Lock — physical deletion blocked for 90 days |
| Corrupt backup uploaded | < 1MB size check rejects before upload |
| Silent backup failure | GitHub Actions emails on workflow failure |
| Accidental deletion | Versioning + Object Lock |

---

## Belt-and-Suspenders (Optional Secondary Layer)

The `auto_backup_sh` module (Yentech/Yenthe666) can run inside Odoo.sh and push the daily backup to a separate SFTP server you control. Install via `requirements.txt` with `pysftp`. This gives a **second independent stream** — if GitHub Actions fails, SFTP still runs.

The GitHub Actions external pull is your **primary lifeline**. SFTP is belt-and-suspenders.

---

## Recovery Procedure

```bash
# List available backups
aws s3 ls s3://plasticos-disaster-recovery/backups/daily/ --recursive

# Download most recent
aws s3 cp s3://plasticos-disaster-recovery/backups/daily/plasticos_20260319T030000Z.sql.gz .

# Restore to local Postgres
gunzip plasticos_20260319T030000Z.sql.gz
psql -U odoo -d odoo_restore < plasticos_20260319T030000Z.sql

# Or restore to Odoo.sh via the Odoo.sh platform backup restore UI
```


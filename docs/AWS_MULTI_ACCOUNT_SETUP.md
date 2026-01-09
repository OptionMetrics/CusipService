# AWS Multi-Account Setup Guide

This guide explains how to set up CusipService across multiple AWS accounts with a shared S3 bucket for PIF files.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Shared Data Account                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  S3 Bucket: cusip-pif-files-shared                              │   │
│  │  └── pif/                                                        │   │
│  │      └── CED01-15R.PIP, CED01-15E.PIP, CED01-15A.PIP            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                   Cross-Account Read Access                             │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Dev Account  │    │  Test Account │    │  Prod Account │
│               │    │               │    │               │
│  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │
│  │   RDS   │  │    │  │   RDS   │  │    │  │   RDS   │  │
│  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │
│  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │
│  │   ECS   │  │    │  │   ECS   │  │    │  │   ECS   │  │
│  │  + ALB  │  │    │  │  + ALB  │  │    │  │  + ALB  │  │
│  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Account IDs (Example)

Replace these with your actual account IDs:

| Account | Account ID | Description |
|---------|------------|-------------|
| Shared Data | `111111111111` | Owns the S3 bucket with PIF files |
| Dev | `222222222222` | Development environment |
| Test | `333333333333` | Testing/QA environment |
| Prod | `444444444444` | Production environment |

## Step 1: Set Up the Shared S3 Bucket

In the **Shared Data Account**, create the S3 bucket and configure cross-account access.

### 1.1 Create the S3 Bucket

```bash
aws s3 mb s3://cusip-pif-files-shared --region us-east-1
```

### 1.2 Configure Bucket Policy

Apply this bucket policy to allow read access from the environment accounts:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::222222222222:root",
          "arn:aws:iam::333333333333:root",
          "arn:aws:iam::444444444444:root"
        ]
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cusip-pif-files-shared",
        "arn:aws:s3:::cusip-pif-files-shared/*"
      ]
    }
  ]
}
```

Save as `bucket-policy.json` and apply:

```bash
aws s3api put-bucket-policy \
  --bucket cusip-pif-files-shared \
  --policy file://bucket-policy.json
```

### 1.3 Organize Files in S3

Upload PIF files with the expected naming convention:

```
s3://cusip-pif-files-shared/
└── pif/
    ├── CED01-15R.PIP   (Issuer file for Jan 15)
    ├── CED01-15E.PIP   (Issue file for Jan 15)
    ├── CED01-15A.PIP   (Issue attributes for Jan 15)
    ├── CED01-16R.PIP
    ├── CED01-16E.PIP
    └── ...
```

## Step 2: Configure Each Environment Account

In each environment account (Dev, Test, Prod), set up the ECS task role with S3 permissions.

### 2.1 Create IAM Policy for S3 Access

Create this policy in each environment account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadSharedPIFFiles",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cusip-pif-files-shared",
        "arn:aws:s3:::cusip-pif-files-shared/*"
      ]
    }
  ]
}
```

Save as `s3-read-policy.json` and create:

```bash
aws iam create-policy \
  --policy-name CusipS3ReadAccess \
  --policy-document file://s3-read-policy.json
```

### 2.2 Attach Policy to ECS Task Role

Attach the policy to your ECS task execution role:

```bash
aws iam attach-role-policy \
  --role-name cusip-service-task-role \
  --policy-arn arn:aws:iam::222222222222:policy/CusipS3ReadAccess
```

### 2.3 (Optional) Add VPC Endpoint for S3

For better security and performance, create a Gateway VPC Endpoint for S3:

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxxxxxxx \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-xxxxxxxx
```

## Step 3: Configure CusipService

### 3.1 Environment Variables

Set these environment variables for the CusipService container:

| Variable | Dev | Test | Prod |
|----------|-----|------|------|
| `CUSIP_FILE_SOURCE` | `s3` | `s3` | `s3` |
| `CUSIP_S3_BUCKET` | `cusip-pif-files-shared` | `cusip-pif-files-shared` | `cusip-pif-files-shared` |
| `CUSIP_S3_PREFIX` | `pif/` | `pif/` | `pif/` |
| `CUSIP_S3_REGION` | `us-east-1` | `us-east-1` | `us-east-1` |
| `CUSIP_DB_HOST` | `dev-cusip.xxx.rds.amazonaws.com` | `test-cusip.xxx.rds.amazonaws.com` | `prod-cusip.xxx.rds.amazonaws.com` |
| `CUSIP_DB_NAME` | `cusip` | `cusip` | `cusip` |
| `CUSIP_DB_USER` | `cusip_app` | `cusip_app` | `cusip_app` |
| `CUSIP_DB_PASSWORD` | (from Secrets Manager) | (from Secrets Manager) | (from Secrets Manager) |
| `CUSIP_API_TOKEN` | (from Secrets Manager) | (from Secrets Manager) | (from Secrets Manager) |

### 3.2 ECS Task Definition (Example)

```json
{
  "family": "cusip-service",
  "taskRoleArn": "arn:aws:iam::222222222222:role/cusip-service-task-role",
  "executionRoleArn": "arn:aws:iam::222222222222:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "cusip-api",
      "image": "222222222222.dkr.ecr.us-east-1.amazonaws.com/cusip-service:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "CUSIP_FILE_SOURCE", "value": "s3"},
        {"name": "CUSIP_S3_BUCKET", "value": "cusip-pif-files-shared"},
        {"name": "CUSIP_S3_PREFIX", "value": "pif/"},
        {"name": "CUSIP_S3_REGION", "value": "us-east-1"}
      ],
      "secrets": [
        {
          "name": "CUSIP_DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:222222222222:secret:cusip/db-password"
        },
        {
          "name": "CUSIP_API_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:222222222222:secret:cusip/api-token"
        }
      ]
    }
  ]
}
```

## Step 4: Local Development with Remote S3

You can develop locally while using the remote S3 bucket for file source.

### 4.1 Configure AWS SSO

Set up AWS SSO in your `~/.aws/config`:

```ini
[profile cusip-dev]
sso_start_url = https://your-org.awsapps.com/start
sso_region = us-east-1
sso_account_id = 222222222222
sso_role_name = DeveloperAccess
region = us-east-1
```

### 4.2 Login and Set Profile

```bash
# Login to AWS SSO
aws sso login --profile cusip-dev

# Set the profile for your session
export AWS_PROFILE=cusip-dev
```

### 4.3 Run Locally with S3 + Local PostgreSQL

Using the API:

```bash
# Start local PostgreSQL (via Docker)
cd docker && docker-compose up -d db

# Run the API with S3 file source
CUSIP_FILE_SOURCE=s3 \
CUSIP_S3_BUCKET=cusip-pif-files-shared \
CUSIP_S3_PREFIX=pif/ \
CUSIP_S3_REGION=us-east-1 \
CUSIP_DB_HOST=localhost \
CUSIP_DB_NAME=cusip \
CUSIP_DB_USER=cusip_app \
CUSIP_DB_PASSWORD=cusip_pass \
CUSIP_API_TOKEN=changeme \
uv run uvicorn cusipservice.api.main:app --reload
```

Using the CLI:

```bash
# Load from S3 by date
AWS_PROFILE=cusip-dev uv run python -m cusipservice \
  --s3-bucket cusip-pif-files-shared \
  --s3-prefix pif/ \
  --date 2024-01-15 \
  --dbname cusip \
  --user cusip_app \
  --password cusip_pass

# Load specific S3 file
AWS_PROFILE=cusip-dev uv run python -m cusipservice \
  --s3-bucket cusip-pif-files-shared \
  --s3-key pif/CED01-15R.PIP \
  --type issuer \
  --dbname cusip \
  --user cusip_app \
  --password cusip_pass
```

### 4.4 Hybrid Mode: Local Files + Local DB

For completely offline development, use local file source:

```bash
# Default: local files from /data/pif_files
CUSIP_FILE_SOURCE=local \
CUSIP_FILE_DIR=/path/to/local/pif/files \
CUSIP_DB_HOST=localhost \
uv run uvicorn cusipservice.api.main:app --reload

# Or via CLI
uv run python -m cusipservice /path/to/CED01-15R.PIP --dbname cusip --user cusip_app
```

## Step 5: Stonebranch Integration

Configure Stonebranch to:

1. Download files from CUSIP Global Services via SFTP
2. Upload to the shared S3 bucket
3. Call the CusipService API to trigger loads

### 5.1 Stonebranch Upload Script (Example)

```bash
#!/bin/bash
DATE=$(date +%m-%d)

# Upload downloaded files to S3
aws s3 cp /sftp/incoming/CED${DATE}R.PIP s3://cusip-pif-files-shared/pif/
aws s3 cp /sftp/incoming/CED${DATE}E.PIP s3://cusip-pif-files-shared/pif/
aws s3 cp /sftp/incoming/CED${DATE}A.PIP s3://cusip-pif-files-shared/pif/
```

### 5.2 Stonebranch Load Trigger (Example)

```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d)
API_URL="https://cusip-api.example.com"
API_TOKEN="your-api-token"

curl -X POST "${API_URL}/jobs/load-all" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"date\": \"${DATE}\"}"
```

## Security Considerations

1. **Least Privilege**: Only grant `s3:GetObject` and `s3:ListBucket` - no write access
2. **Encryption**: Enable S3 bucket encryption (SSE-S3 or SSE-KMS)
3. **VPC Endpoints**: Use Gateway VPC Endpoints to keep traffic private
4. **CloudTrail**: Enable S3 data events for audit logging
5. **Bucket Versioning**: Consider enabling for audit trail of file changes
6. **Lifecycle Policies**: Archive or delete old files after retention period

## Troubleshooting

### Access Denied Errors

1. Verify bucket policy includes the correct account IDs
2. Verify ECS task role has the S3 read policy attached
3. Check if VPC endpoint is configured (if using private subnets)

```bash
# Test S3 access from ECS task
aws s3 ls s3://cusip-pif-files-shared/pif/ --region us-east-1
```

### Files Not Found

1. Check the S3 prefix configuration matches the actual folder structure
2. Verify file naming convention: `CED{mm-dd}{R|E|A}.PIP`

```bash
# List files for a specific date
aws s3 ls s3://cusip-pif-files-shared/pif/CED01-15 --region us-east-1
```

### AWS SSO Token Expired

```bash
# Re-authenticate
aws sso login --profile cusip-dev

# Verify credentials
aws sts get-caller-identity --profile cusip-dev
```

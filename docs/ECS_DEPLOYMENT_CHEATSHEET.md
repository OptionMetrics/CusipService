# ECS Fargate Deployment Cheatsheet

Step-by-step guide for manually deploying CusipService to AWS ECS Fargate without CDK/Terraform.

## Prerequisites

- AWS CLI v2 installed
- Docker installed
- AWS SSO configured with appropriate permissions
- VPN access to private subnets (if not using public IPs)

## Variables

Set these for your environment:

```bash
# AWS settings
export AWS_PROFILE=your-sso-profile
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Service settings
export SERVICE_NAME=cusip-service
export CLUSTER_NAME=cusip-cluster
export ECR_REPO_NAME=cusip-service

# Networking (get these from your VPC)
export VPC_ID=vpc-xxxxxxxxx
export SUBNET_1=subnet-xxxxxxxx
export SUBNET_2=subnet-yyyyyyyy
export SECURITY_GROUP=sg-xxxxxxxx

# Database settings
export DB_HOST=your-rds-instance.xxxxxx.us-east-1.rds.amazonaws.com
export DB_NAME=cusip
export DB_SSLMODE=require

# S3 bucket for PIP files
export S3_BUCKET=cusip-pip-files
export S3_PREFIX=pip/
```

---

## Step 1: AWS SSO Login

```bash
aws sso login --profile $AWS_PROFILE
export AWS_PROFILE=$AWS_PROFILE
```

Verify access:

```bash
aws sts get-caller-identity
```

---

## Step 2: Create ECR Repository

```bash
# Create the repository
aws ecr create-repository \
  --repository-name $ECR_REPO_NAME \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256

# Get the repository URI
export ECR_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME
echo "ECR URI: $ECR_URI"
```

---

## Step 3: Build and Push Docker Image

**IMPORTANT**: If you're on Apple Silicon (M1/M2/M3), you must build for `linux/amd64` platform since Fargate runs on x86_64.

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build the image (use --platform for Apple Silicon)
docker build --platform linux/amd64 -t $SERVICE_NAME -f docker/Dockerfile .

# Tag for ECR
docker tag $SERVICE_NAME:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest
```

---

## Step 4: Configure Secrets

### Database credentials

If using an **RDS-managed secret** (automatically created with RDS), note that it only contains `username` and `password`. You must provide `host`, `dbname`, and `sslmode` separately as environment variables (see Step 8).

```bash
# Find your RDS-managed secret ARN
aws secretsmanager list-secrets --query "SecretList[?contains(Name, 'rds')].{Name:Name,ARN:ARN}" --output table

# Set the ARN (note: RDS secrets often have special characters like ! in the name)
export DB_SECRET_ARN="arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:rds!db-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-XXXXXX"
echo "DB Secret ARN: $DB_SECRET_ARN"
```

Or create your own secret with all fields:

```bash
aws secretsmanager create-secret \
  --name cusip/db \
  --description "CusipService database credentials" \
  --secret-string '{
    "host": "your-rds.xxxxxx.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "dbname": "cusip",
    "username": "cusip_app",
    "password": "YOUR_SECURE_PASSWORD"
  }'

export DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id cusip/db --query ARN --output text)
```

### API token (Parameter Store)

```bash
# Create API token as a SecureString parameter
aws ssm put-parameter \
  --name /cusip/api-token \
  --description "CusipService API bearer token" \
  --type SecureString \
  --value "$(openssl rand -base64 32)"

# Get the ARN
export API_TOKEN_PARAM_ARN=arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/cusip/api-token
echo "API Token Parameter ARN: $API_TOKEN_PARAM_ARN"
```

---

## Step 5: Create IAM Roles

### Task Execution Role (used by ECS to pull images, get secrets)

```bash
# Create the trust policy file
echo '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}' > /tmp/ecs-trust-policy.json

# Create the role
aws iam create-role \
  --role-name ${SERVICE_NAME}-execution-role \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

# Attach the AWS managed policy for ECS task execution
aws iam attach-role-policy \
  --role-name ${SERVICE_NAME}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create policy for Parameter Store access (for API token injection)
aws iam put-role-policy \
  --role-name ${SERVICE_NAME}-execution-role \
  --policy-name ssm-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["ssm:GetParameters"],
        "Resource": ["arn:aws:ssm:'$AWS_REGION':'$AWS_ACCOUNT_ID':parameter/cusip/*"]
      }
    ]
  }'

export EXECUTION_ROLE_ARN=arn:aws:iam::$AWS_ACCOUNT_ID:role/${SERVICE_NAME}-execution-role
echo "Execution Role ARN: $EXECUTION_ROLE_ARN"
```

### Task Role (used by the application at runtime)

```bash
# Create the role (same trust policy)
aws iam create-role \
  --role-name ${SERVICE_NAME}-task-role \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

# Create policy for application permissions
# NOTE: Update the DB_SECRET_ARN with your actual RDS secret ARN
aws iam put-role-policy \
  --role-name ${SERVICE_NAME}-task-role \
  --policy-name app-permissions \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "SecretsManagerAccess",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Resource": ["'$DB_SECRET_ARN'"]
      },
      {
        "Sid": "S3Access",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:ListBucket"],
        "Resource": [
          "arn:aws:s3:::'$S3_BUCKET'",
          "arn:aws:s3:::'$S3_BUCKET'/*"
        ]
      }
    ]
  }'

export TASK_ROLE_ARN=arn:aws:iam::$AWS_ACCOUNT_ID:role/${SERVICE_NAME}-task-role
echo "Task Role ARN: $TASK_ROLE_ARN"
```

---

## Step 6: Create ECS Cluster

```bash
# Create Fargate cluster
aws ecs create-cluster \
  --cluster-name $CLUSTER_NAME \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy \
    capacityProvider=FARGATE,weight=1,base=1

# Verify
aws ecs describe-clusters --clusters $CLUSTER_NAME
```

---

## Step 7: Create CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name /ecs/$SERVICE_NAME

# Optional: set retention
aws logs put-retention-policy \
  --log-group-name /ecs/$SERVICE_NAME \
  --retention-in-days 30
```

---

## Step 8: Create Task Definition

**IMPORTANT**:
- If using RDS-managed secrets, you MUST include `CUSIP_DB_HOST`, `CUSIP_DB_NAME`, and `CUSIP_DB_SSLMODE` as the RDS secret only contains username/password.
- Avoid using heredocs (`<< EOF`) as they can mangle special characters. Use inline JSON or a file.

```bash
# Write task definition to file (avoids shell interpolation issues)
cat > /tmp/task-definition.json << 'TASKDEF'
{
  "family": "cusip-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "EXECUTION_ROLE_ARN_PLACEHOLDER",
  "taskRoleArn": "TASK_ROLE_ARN_PLACEHOLDER",
  "containerDefinitions": [
    {
      "name": "cusip-service",
      "image": "ECR_URI_PLACEHOLDER:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "CUSIP_DB_SECRET_ARN", "value": "DB_SECRET_ARN_PLACEHOLDER"},
        {"name": "CUSIP_DB_HOST", "value": "DB_HOST_PLACEHOLDER"},
        {"name": "CUSIP_DB_NAME", "value": "DB_NAME_PLACEHOLDER"},
        {"name": "CUSIP_DB_SSLMODE", "value": "DB_SSLMODE_PLACEHOLDER"},
        {"name": "CUSIP_FILE_SOURCE", "value": "s3"},
        {"name": "CUSIP_S3_BUCKET", "value": "S3_BUCKET_PLACEHOLDER"},
        {"name": "CUSIP_S3_PREFIX", "value": "S3_PREFIX_PLACEHOLDER"}
      ],
      "secrets": [
        {
          "name": "CUSIP_API_TOKEN",
          "valueFrom": "API_TOKEN_PARAM_ARN_PLACEHOLDER"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/cusip-service",
          "awslogs-region": "AWS_REGION_PLACEHOLDER",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
TASKDEF

# Replace placeholders with actual values
sed -i.bak \
  -e "s|EXECUTION_ROLE_ARN_PLACEHOLDER|$EXECUTION_ROLE_ARN|g" \
  -e "s|TASK_ROLE_ARN_PLACEHOLDER|$TASK_ROLE_ARN|g" \
  -e "s|ECR_URI_PLACEHOLDER|$ECR_URI|g" \
  -e "s|DB_SECRET_ARN_PLACEHOLDER|$DB_SECRET_ARN|g" \
  -e "s|DB_HOST_PLACEHOLDER|$DB_HOST|g" \
  -e "s|DB_NAME_PLACEHOLDER|$DB_NAME|g" \
  -e "s|DB_SSLMODE_PLACEHOLDER|$DB_SSLMODE|g" \
  -e "s|S3_BUCKET_PLACEHOLDER|$S3_BUCKET|g" \
  -e "s|S3_PREFIX_PLACEHOLDER|$S3_PREFIX|g" \
  -e "s|API_TOKEN_PARAM_ARN_PLACEHOLDER|$API_TOKEN_PARAM_ARN|g" \
  -e "s|AWS_REGION_PLACEHOLDER|$AWS_REGION|g" \
  /tmp/task-definition.json

# Verify the file looks correct
cat /tmp/task-definition.json

# Register the task definition
aws ecs register-task-definition --cli-input-json file:///tmp/task-definition.json

# Get the revision
export TASK_DEF_ARN=$(aws ecs describe-task-definition \
  --task-definition $SERVICE_NAME \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)
echo "Task Definition ARN: $TASK_DEF_ARN"
```

---

## Step 9: Create Application Load Balancer (Optional)

Skip this if using VPN access to private IPs.

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name ${SERVICE_NAME}-alb \
  --subnets $SUBNET_1 $SUBNET_2 \
  --security-groups $SECURITY_GROUP \
  --scheme internet-facing \
  --type application

export ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names ${SERVICE_NAME}-alb \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

export ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names ${SERVICE_NAME}-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "ALB ARN: $ALB_ARN"
echo "ALB DNS: $ALB_DNS"

# Create target group
aws elbv2 create-target-group \
  --name ${SERVICE_NAME}-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

export TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups \
  --names ${SERVICE_NAME}-tg \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

echo "Target Group ARN: $TARGET_GROUP_ARN"

# Create listener (HTTP - use HTTPS in production with ACM cert)
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN
```

---

## Step 10: Create ECS Service

### Private access only (via VPN)

```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $SERVICE_NAME \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}"
```

### With ALB

```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $SERVICE_NAME \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=$SERVICE_NAME,containerPort=8000"
```

---

## Step 11: Verify Deployment

### Check service status

```bash
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,pending:pendingCount}'
```

### Get private IP (for VPN access)

```bash
# One-liner to get private IP
PRIVATE_IP=$(aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --query 'taskArns[0]' --output text) \
  --query 'tasks[0].attachments[0].details[?name==`privateIPv4Address`].value' \
  --output text)
echo "Private IP: $PRIVATE_IP"
```

### Test health endpoint

```bash
curl http://$PRIVATE_IP:8000/health
```

Expected response:
```json
{"status":"healthy","database":"connected","version":"0.1.0"}
```

### View logs

```bash
aws logs tail /ecs/$SERVICE_NAME --follow
```

---

## Step 12: Run Database Migrations

Run migrations as a one-off ECS task:

```bash
# Write migration task definition
cat > /tmp/migration-task.json << 'MIGRATIONDEF'
{
  "family": "cusip-service-migration",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "EXECUTION_ROLE_ARN_PLACEHOLDER",
  "taskRoleArn": "TASK_ROLE_ARN_PLACEHOLDER",
  "containerDefinitions": [
    {
      "name": "migration",
      "image": "ECR_URI_PLACEHOLDER:latest",
      "essential": true,
      "command": ["uv", "run", "alembic", "upgrade", "head"],
      "environment": [
        {"name": "CUSIP_DB_SECRET_ARN", "value": "DB_SECRET_ARN_PLACEHOLDER"},
        {"name": "CUSIP_DB_HOST", "value": "DB_HOST_PLACEHOLDER"},
        {"name": "CUSIP_DB_NAME", "value": "DB_NAME_PLACEHOLDER"},
        {"name": "CUSIP_DB_SSLMODE", "value": "DB_SSLMODE_PLACEHOLDER"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/cusip-service",
          "awslogs-region": "AWS_REGION_PLACEHOLDER",
          "awslogs-stream-prefix": "migration"
        }
      }
    }
  ]
}
MIGRATIONDEF

# Replace placeholders
sed -i.bak \
  -e "s|EXECUTION_ROLE_ARN_PLACEHOLDER|$EXECUTION_ROLE_ARN|g" \
  -e "s|TASK_ROLE_ARN_PLACEHOLDER|$TASK_ROLE_ARN|g" \
  -e "s|ECR_URI_PLACEHOLDER|$ECR_URI|g" \
  -e "s|DB_SECRET_ARN_PLACEHOLDER|$DB_SECRET_ARN|g" \
  -e "s|DB_HOST_PLACEHOLDER|$DB_HOST|g" \
  -e "s|DB_NAME_PLACEHOLDER|$DB_NAME|g" \
  -e "s|DB_SSLMODE_PLACEHOLDER|$DB_SSLMODE|g" \
  -e "s|AWS_REGION_PLACEHOLDER|$AWS_REGION|g" \
  /tmp/migration-task.json

aws ecs register-task-definition --cli-input-json file:///tmp/migration-task.json

# Run the migration task
aws ecs run-task \
  --cluster $CLUSTER_NAME \
  --task-definition ${SERVICE_NAME}-migration \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}"

# Watch migration logs
aws logs tail /ecs/$SERVICE_NAME --log-stream-name-prefix migration --follow
```

---

## Step 13: Deploy PostgREST (Optional)

PostgREST provides automatic REST API endpoints for database views and tables. Skip this if FastAPI is sufficient for your needs.

### Prerequisites

PostgREST requires database roles to be set up. Run these SQL commands against your database:

```sql
-- Create authenticator role (PostgREST connects as this)
CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'your-secure-password';

-- Create anonymous role for read-only access
CREATE ROLE web_anon NOLOGIN;
GRANT web_anon TO authenticator;

-- Grant permissions to web_anon
GRANT USAGE ON SCHEMA public TO web_anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO web_anon;
```

### Store PostgREST database password

```bash
aws ssm put-parameter \
  --name /cusip/postgrest-db-password \
  --description "PostgREST authenticator role password" \
  --type SecureString \
  --value "your-secure-password"

export POSTGREST_DB_PASSWORD_ARN=arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/cusip/postgrest-db-password
```

### Update execution role for PostgREST secrets

```bash
aws iam put-role-policy \
  --role-name ${SERVICE_NAME}-execution-role \
  --policy-name ssm-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["ssm:GetParameters"],
        "Resource": [
          "arn:aws:ssm:'$AWS_REGION':'$AWS_ACCOUNT_ID':parameter/cusip/*"
        ]
      }
    ]
  }'
```

### Create PostgREST task definition

```bash
cat > /tmp/postgrest-task.json << 'POSTGRESTDEF'
{
  "family": "cusip-postgrest",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "EXECUTION_ROLE_ARN_PLACEHOLDER",
  "containerDefinitions": [{
    "name": "postgrest",
    "image": "postgrest/postgrest:v12.2.3",
    "essential": true,
    "portMappings": [{"containerPort": 3000, "protocol": "tcp"}],
    "environment": [
      {"name": "PGRST_DB_URI", "value": "postgres://authenticator@DB_HOST_PLACEHOLDER:5432/DB_NAME_PLACEHOLDER"},
      {"name": "PGRST_DB_SCHEMAS", "value": "public"},
      {"name": "PGRST_DB_ANON_ROLE", "value": "web_anon"},
      {"name": "PGRST_SERVER_PORT", "value": "3000"},
      {"name": "PGRST_DB_MAX_ROWS", "value": "10000"},
      {"name": "PGRST_OPENAPI_SERVER_PROXY_URI", "value": "http://localhost:3000"}
    ],
    "secrets": [
      {
        "name": "PGRST_DB_PASSWORD",
        "valueFrom": "POSTGREST_DB_PASSWORD_ARN_PLACEHOLDER"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/cusip-service",
        "awslogs-region": "AWS_REGION_PLACEHOLDER",
        "awslogs-stream-prefix": "postgrest"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "wget -q --spider http://localhost:3000/ || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 30
    }
  }]
}
POSTGRESTDEF

# Replace placeholders
sed -i.bak \
  -e "s|EXECUTION_ROLE_ARN_PLACEHOLDER|$EXECUTION_ROLE_ARN|g" \
  -e "s|DB_HOST_PLACEHOLDER|$DB_HOST|g" \
  -e "s|DB_NAME_PLACEHOLDER|$DB_NAME|g" \
  -e "s|POSTGREST_DB_PASSWORD_ARN_PLACEHOLDER|$POSTGREST_DB_PASSWORD_ARN|g" \
  -e "s|AWS_REGION_PLACEHOLDER|$AWS_REGION|g" \
  /tmp/postgrest-task.json

aws ecs register-task-definition --cli-input-json file:///tmp/postgrest-task.json
```

### Create PostgREST service

```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name cusip-postgrest \
  --task-definition cusip-postgrest \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}"
```

### Get PostgREST private IP

```bash
POSTGREST_IP=$(aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name cusip-postgrest --query 'taskArns[0]' --output text) \
  --query 'tasks[0].attachments[0].details[?name==`privateIPv4Address`].value' \
  --output text)
echo "PostgREST IP: $POSTGREST_IP"
```

### Test PostgREST

```bash
# Health check (returns OpenAPI spec)
curl http://$POSTGREST_IP:3000/

# Query a view
curl "http://$POSTGREST_IP:3000/v_issuer?limit=10"

# Full-text search (if configured)
curl -X POST "http://$POSTGREST_IP:3000/rpc/search_securities" \
  -H "Content-Type: application/json" \
  -d '{"search_query": "APPLE"}'
```

### PostgREST Query Examples

```bash
# Filter with ilike (case-insensitive)
curl "http://$POSTGREST_IP:3000/v_issuer?issuer_name=ilike.*KEURIG*"

# Exact match
curl "http://$POSTGREST_IP:3000/v_issue?cusip=eq.037833100"

# Multiple conditions
curl "http://$POSTGREST_IP:3000/v_issue?issue_status=eq.A&security_type=eq.COM"

# Pagination
curl "http://$POSTGREST_IP:3000/v_issuer?limit=100&offset=200"

# Select specific columns
curl "http://$POSTGREST_IP:3000/v_issuer?select=issuer_id,issuer_name,city,state"

# Order results
curl "http://$POSTGREST_IP:3000/v_issuer?order=issuer_name.asc"
```

---

## Common Operations

### Update service with new image

```bash
# Build for correct platform and push
docker build --platform linux/amd64 -t $SERVICE_NAME -f docker/Dockerfile .
docker tag $SERVICE_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest

# Force new deployment
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment
```

### Scale the service

```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --desired-count 4
```

### View logs

```bash
# Tail logs
aws logs tail /ecs/$SERVICE_NAME --follow

# Recent logs
aws logs tail /ecs/$SERVICE_NAME --since 5m

# Search logs for errors
aws logs filter-log-events \
  --log-group-name /ecs/$SERVICE_NAME \
  --filter-pattern "ERROR"
```

### Stop the service

```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --desired-count 0
```

### Delete everything

```bash
# Delete service
aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --desired-count 0
aws ecs delete-service --cluster $CLUSTER_NAME --service $SERVICE_NAME

# Delete cluster
aws ecs delete-cluster --cluster $CLUSTER_NAME

# Delete ALB (if created)
aws elbv2 delete-listener --listener-arn $LISTENER_ARN
aws elbv2 delete-target-group --target-group-arn $TARGET_GROUP_ARN
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN

# Delete ECR repository (and all images)
aws ecr delete-repository --repository-name $ECR_REPO_NAME --force

# Delete secrets/parameters
aws ssm delete-parameter --name /cusip/api-token
# Only delete if you created it (don't delete RDS-managed secrets)
# aws secretsmanager delete-secret --secret-id cusip/db --force-delete-without-recovery

# Delete IAM roles
aws iam delete-role-policy --role-name ${SERVICE_NAME}-execution-role --policy-name ssm-access
aws iam detach-role-policy --role-name ${SERVICE_NAME}-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role --role-name ${SERVICE_NAME}-execution-role

aws iam delete-role-policy --role-name ${SERVICE_NAME}-task-role --policy-name app-permissions
aws iam delete-role --role-name ${SERVICE_NAME}-task-role

# Delete log group
aws logs delete-log-group --log-group-name /ecs/$SERVICE_NAME
```

---

## Troubleshooting

### Image platform mismatch

**Error**: `CannotPullContainerError: image Manifest does not contain descriptor matching platform 'linux/amd64'`

**Fix**: Rebuild with correct platform:
```bash
docker build --platform linux/amd64 -t $SERVICE_NAME -f docker/Dockerfile .
```

### Task role not valid

**Error**: `Role is not valid`

**Fix**: Check the role ARNs are correctly set:
```bash
echo "EXECUTION_ROLE_ARN: $EXECUTION_ROLE_ARN"
echo "TASK_ROLE_ARN: $TASK_ROLE_ARN"
aws iam get-role --role-name ${SERVICE_NAME}-execution-role
aws iam get-role --role-name ${SERVICE_NAME}-task-role
```

### Secrets Manager access denied

**Error**: `AccessDeniedException when calling GetSecretValue`

**Fix**:
1. Verify the task role has the correct secret ARN in its policy
2. RDS-managed secret ARNs often contain `!` - verify the full ARN:
```bash
aws secretsmanager list-secrets --query "SecretList[?contains(Name, 'rds')].ARN"
```

### Database connection failed / unhealthy

**Error**: `{"status":"unhealthy","database":"disconnected"}`

**Causes**:
1. Missing environment variables - ensure `CUSIP_DB_HOST`, `CUSIP_DB_NAME`, `CUSIP_DB_SSLMODE` are set
2. Security group doesn't allow traffic on port 5432
3. Wrong credentials in secret

**Debug**:
```bash
# Check what env vars are set in task definition
aws ecs describe-task-definition --task-definition cusip-service \
  --query 'taskDefinition.containerDefinitions[0].environment'

# Check logs for specific error
aws logs tail /ecs/$SERVICE_NAME --since 5m
```

### Task fails to start

```bash
# Check stopped task reason
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER_NAME --desired-status STOPPED --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN \
  --query 'tasks[0].{stoppedReason:stoppedReason,containers:containers[*].{name:name,reason:reason,exitCode:exitCode}}'
```

### Container can't pull image

- Check execution role has `ecr:GetAuthorizationToken` and `ecr:BatchGetImage`
- Verify security group allows outbound HTTPS (443) to ECR
- If using private subnets, ensure VPC endpoints exist for ECR

### Health check failing

```bash
# Exec into container to debug (requires ECS Exec enabled)
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --enable-execute-command

# Then exec in
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --query 'taskArns[0]' --output text)
aws ecs execute-command \
  --cluster $CLUSTER_NAME \
  --task $TASK_ARN \
  --container $SERVICE_NAME \
  --interactive \
  --command "/bin/sh"
```

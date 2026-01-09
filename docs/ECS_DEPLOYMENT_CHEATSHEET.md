# ECS Fargate Deployment Cheatsheet

Step-by-step guide for manually deploying CusipService to AWS ECS Fargate without CDK/Terraform.

## Prerequisites

- AWS CLI v2 installed
- Docker installed
- AWS SSO configured with appropriate permissions

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

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build the image
docker build -t $SERVICE_NAME -f docker/Dockerfile .

# Tag for ECR
docker tag $SERVICE_NAME:latest $ECR_URI:latest
docker tag $SERVICE_NAME:latest $ECR_URI:$(git rev-parse --short HEAD)

# Push to ECR
docker push $ECR_URI:latest
docker push $ECR_URI:$(git rev-parse --short HEAD)
```

---

## Step 4: Create Secrets in Secrets Manager

### Database credentials (for RDS)

```bash
# Create the DB secret (or use existing RDS-managed secret)
aws secretsmanager create-secret \
  --name cusip/db \
  --description "CusipService database credentials" \
  --secret-string '{
    "host": "cusip-db.xxxxxx.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "dbname": "cusip",
    "username": "cusip_app",
    "password": "YOUR_SECURE_PASSWORD"
  }'

# Get the ARN
export DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id cusip/db --query ARN --output text)
echo "DB Secret ARN: $DB_SECRET_ARN"
```

### API token

```bash
# Create API token secret
aws secretsmanager create-secret \
  --name cusip/api-token \
  --description "CusipService API bearer token" \
  --secret-string "$(openssl rand -base64 32)"

# Get the ARN
export API_TOKEN_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id cusip/api-token --query ARN --output text)
echo "API Token Secret ARN: $API_TOKEN_SECRET_ARN"
```

---

## Step 5: Create IAM Roles

### Task Execution Role (used by ECS to pull images, get secrets)

```bash
# Create the trust policy
cat > /tmp/ecs-task-execution-trust.json << 'EOF'
{
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
}
EOF

# Create the role
aws iam create-role \
  --role-name ${SERVICE_NAME}-execution-role \
  --assume-role-policy-document file:///tmp/ecs-task-execution-trust.json

# Attach the AWS managed policy for ECS task execution
aws iam attach-role-policy \
  --role-name ${SERVICE_NAME}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create policy for Secrets Manager access (for ECS secrets injection)
cat > /tmp/ecs-secrets-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "$API_TOKEN_SECRET_ARN"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${SERVICE_NAME}-execution-role \
  --policy-name secrets-access \
  --policy-document file:///tmp/ecs-secrets-policy.json

export EXECUTION_ROLE_ARN=arn:aws:iam::$AWS_ACCOUNT_ID:role/${SERVICE_NAME}-execution-role
echo "Execution Role ARN: $EXECUTION_ROLE_ARN"
```

### Task Role (used by the application at runtime)

```bash
# Create the role (same trust policy)
aws iam create-role \
  --role-name ${SERVICE_NAME}-task-role \
  --assume-role-policy-document file:///tmp/ecs-task-execution-trust.json

# Create policy for application permissions
cat > /tmp/ecs-task-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "$DB_SECRET_ARN"
      ]
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cusip-pip-files",
        "arn:aws:s3:::cusip-pip-files/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${SERVICE_NAME}-task-role \
  --policy-name app-permissions \
  --policy-document file:///tmp/ecs-task-policy.json

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

```bash
cat > /tmp/task-definition.json << EOF
{
  "family": "${SERVICE_NAME}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${SERVICE_NAME}",
      "image": "${ECR_URI}:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "CUSIP_DB_SECRET_ARN", "value": "${DB_SECRET_ARN}"},
        {"name": "CUSIP_FILE_SOURCE", "value": "s3"},
        {"name": "CUSIP_S3_BUCKET", "value": "cusip-pip-files"},
        {"name": "CUSIP_S3_PREFIX", "value": "pip/"}
      ],
      "secrets": [
        {
          "name": "CUSIP_API_TOKEN",
          "valueFrom": "${API_TOKEN_SECRET_ARN}"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${SERVICE_NAME}",
          "awslogs-region": "${AWS_REGION}",
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
EOF

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

Skip this if you already have an ALB or are using a different ingress method.

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

### Without ALB (internal service)

```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $SERVICE_NAME \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}"
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

```bash
# Check service status
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --query 'services[0].{status:status,runningCount:runningCount,desiredCount:desiredCount}'

# List running tasks
aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME

# Get task details
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN

# View logs
aws logs tail /ecs/$SERVICE_NAME --follow

# Test the endpoint (if using ALB)
curl http://$ALB_DNS/health
```

---

## Step 12: Run Database Migrations

Run migrations as a one-off ECS task:

```bash
# Create a migration task definition (same as service but with different command)
cat > /tmp/migration-task.json << EOF
{
  "family": "${SERVICE_NAME}-migration",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "migration",
      "image": "${ECR_URI}:latest",
      "essential": true,
      "command": ["uv", "run", "alembic", "upgrade", "head"],
      "environment": [
        {"name": "CUSIP_DB_SECRET_ARN", "value": "${DB_SECRET_ARN}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${SERVICE_NAME}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "migration"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/migration-task.json

# Run the migration task
aws ecs run-task \
  --cluster $CLUSTER_NAME \
  --task-definition ${SERVICE_NAME}-migration \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}"

# Watch migration logs
aws logs tail /ecs/$SERVICE_NAME --log-stream-name-prefix migration --follow
```

---

## Common Operations

### Update service with new image

```bash
# Build and push new image
docker build -t $SERVICE_NAME -f docker/Dockerfile .
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
# Scale to 4 tasks
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --desired-count 4
```

### View logs

```bash
# Tail logs
aws logs tail /ecs/$SERVICE_NAME --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /ecs/$SERVICE_NAME \
  --filter-pattern "ERROR"
```

### Stop the service

```bash
# Scale to 0
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

# Delete ALB
aws elbv2 delete-listener --listener-arn $LISTENER_ARN
aws elbv2 delete-target-group --target-group-arn $TARGET_GROUP_ARN
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN

# Delete ECR repository (and all images)
aws ecr delete-repository --repository-name $ECR_REPO_NAME --force

# Delete secrets
aws secretsmanager delete-secret --secret-id cusip/db --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id cusip/api-token --force-delete-without-recovery

# Delete IAM roles
aws iam delete-role-policy --role-name ${SERVICE_NAME}-execution-role --policy-name secrets-access
aws iam detach-role-policy --role-name ${SERVICE_NAME}-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role --role-name ${SERVICE_NAME}-execution-role

aws iam delete-role-policy --role-name ${SERVICE_NAME}-task-role --policy-name app-permissions
aws iam delete-role --role-name ${SERVICE_NAME}-task-role

# Delete log group
aws logs delete-log-group --log-group-name /ecs/$SERVICE_NAME
```

---

## Troubleshooting

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

### Container can't access Secrets Manager

- Check task role has `secretsmanager:GetSecretValue` for the secret ARN
- Verify security group allows outbound HTTPS (443)

### Container can't connect to RDS

- Check security group allows outbound to RDS port (5432)
- Verify RDS security group allows inbound from ECS security group
- Check the secret contains correct host/credentials

### Health check failing

```bash
# Exec into container to debug (requires ECS Exec enabled)
aws ecs execute-command \
  --cluster $CLUSTER_NAME \
  --task $TASK_ARN \
  --container $SERVICE_NAME \
  --interactive \
  --command "/bin/sh"
```

Enable ECS Exec on service:

```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --enable-execute-command
```

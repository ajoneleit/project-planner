# AWS Infrastructure Setup

## Prerequisites
- AWS CLI installed and configured
- Appropriate IAM permissions for ECR and App Runner

## 1. Create ECR Repository

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name planner-bot \
    --region us-east-1

# Get repository URI (save this for later)
aws ecr describe-repositories \
    --repository-names planner-bot \
    --region us-east-1 \
    --query 'repositories[0].repositoryUri' \
    --output text
```

## 2. Create App Runner Service

Create `apprunner-service.json`:
```json
{
  "ServiceName": "planner-bot-service",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "YOUR_ECR_URI:latest",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "ENVIRONMENT": "production",
          "LOG_LEVEL": "INFO"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true
  },
  "InstanceConfiguration": {
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 20,
    "Timeout": 5,
    "HealthyThreshold": 3,
    "UnhealthyThreshold": 3
  }
}
```

```bash
# Create the service
aws apprunner create-service \
    --cli-input-json file://apprunner-service.json \
    --region us-east-1

# Get service ARN (save this for GitHub secrets)
aws apprunner list-services \
    --region us-east-1 \
    --query 'ServiceSummaryList[?ServiceName==`planner-bot-service`].ServiceArn' \
    --output text
```

## 3. IAM Role for App Runner

Create IAM role trust policy (`app-runner-trust-policy.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Create IAM role permissions policy (`app-runner-permissions.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    }
  ]
}
```

```bash
# Create IAM role
aws iam create-role \
    --role-name AppRunnerECRAccessRole \
    --assume-role-policy-document file://app-runner-trust-policy.json

# Attach permissions policy
aws iam put-role-policy \
    --role-name AppRunnerECRAccessRole \
    --policy-name ECRAccessPolicy \
    --policy-document file://app-runner-permissions.json
```

## 4. GitHub Secrets Setup

Add these secrets to your GitHub repository:

- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key  
- `APP_RUNNER_SERVICE_ARN`: The App Runner service ARN from step 2

## 5. Environment Variables

For production, add these environment variables to your App Runner service:

```bash
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o-mini
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key
```

## 6. Health Check Endpoint

Add health check endpoint to your FastAPI application (`app/main.py`):

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
```

## 7. Deploy Command

After setting up AWS infrastructure:

```bash
# Push to main branch to trigger deployment
git push origin main

# Or manually deploy
docker build -t planner-bot .
docker tag planner-bot:latest YOUR_ECR_URI:latest
docker push YOUR_ECR_URI:latest
```

## Troubleshooting

### Common Issues

1. **ECR Push Fails**: Ensure AWS credentials are properly configured
2. **App Runner Service Won't Start**: Check health check endpoint and environment variables
3. **Deployment Timeout**: Increase timeout in GitHub Actions or check App Runner logs

### Useful Commands

```bash
# Check App Runner service status
aws apprunner describe-service --service-arn YOUR_SERVICE_ARN

# View App Runner logs
aws logs tail /aws/apprunner/planner-bot-service --follow

# List ECR images
aws ecr list-images --repository-name planner-bot
```
# Deployment Guide

This guide covers deployment of the Project Planner Bot backend to AWS App Runner.

## Quick Start

### Automated Deployment (Recommended)

Use the deployment script for one-command deployment:

```bash
# Deploy to production
./deploy-backend.sh

# Preview what will be deployed
./deploy-backend.sh --dry-run

# Deploy with verbose output
./deploy-backend.sh --verbose
```

### Using Make

```bash
# Deploy backend
make deploy

# Preview deployment
make deploy-dry-run
```

## Prerequisites

Before deploying, ensure you have:

1. **Docker installed and running**
   ```bash
   docker --version
   ```

2. **AWS CLI configured**
   ```bash
   aws --version
   aws sts get-caller-identity --profile 348204830428_SoftwareEngineering
   ```

3. **ECR repository access**
   - Repository: `348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot`

4. **App Runner service created**
   - Service ARN: `arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9`

## Manual Deployment Steps

If you prefer to deploy manually or troubleshoot the automated script:

### 1. Build Docker Image

```bash
docker build -t planner-bot .
```

### 2. Tag for ECR

```bash
docker tag planner-bot:latest 348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
```

### 3. Login to ECR

```bash
aws ecr get-login-password --region us-east-1 --profile 348204830428_SoftwareEngineering | docker login --username AWS --password-stdin 348204830428.dkr.ecr.us-east-1.amazonaws.com
```

### 4. Push to ECR

```bash
docker push 348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
```

### 5. Deploy to App Runner

```bash
aws apprunner start-deployment \
  --service-arn arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9 \
  --region us-east-1 \
  --profile 348204830428_SoftwareEngineering
```

## Deployment Configuration

### Environment Variables

The following environment variables are configured in AWS App Runner:

**Required:**
- `OPENAI_API_KEY` - From AWS Secrets Manager
- `LANGCHAIN_API_KEY` - From AWS Secrets Manager
- `ENVIRONMENT=production`

**Optional:**
- `DEFAULT_MODEL=gpt-4o-mini`
- `LANGCHAIN_TRACING_V2=true`
- `LOG_LEVEL=INFO`

### AWS Secrets Manager

API keys are stored in AWS Secrets Manager as JSON:

```json
{
  "OPENAI_API_KEY": "sk-proj-...",
  "LANGCHAIN_API_KEY": "lsv2_sk_..."
}
```

The backend automatically parses this JSON format in production.

### CORS Configuration

The backend includes environment-aware CORS configuration:

- **Development**: Allows localhost origins and local network IPs
- **Production**: Restricts to specific domains or same-origin requests

## Monitoring Deployment

### 1. AWS Console

Monitor deployment progress in the AWS App Runner console:
- URL: https://console.aws.amazon.com/apprunner/
- Go to your service → Activity tab

### 2. Health Check

Once deployed, verify the service is healthy:
```bash
curl https://fbm26vyfbw.us-east-1.awsapprunner.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "planner-bot",
  "version": "1.0.0",
  "environment": "production",
  "cors_origins": ["*"],
  "langsmith_enabled": true,
  "default_model": "gpt-4o-mini"
}
```

### 3. API Documentation

Access the interactive API documentation:
- URL: https://fbm26vyfbw.us-east-1.awsapprunner.com/docs

### 4. CLI Monitoring

Check deployment status via CLI:
```bash
aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9 \
  --region us-east-1 \
  --profile 348204830428_SoftwareEngineering
```

## Troubleshooting

### Common Issues

1. **ECR Login Failed**
   ```bash
   # Refresh AWS credentials
   aws sso login --profile 348204830428_SoftwareEngineering
   ```

2. **Docker Build Failed**
   ```bash
   # Clean Docker cache
   docker system prune -f
   docker build --no-cache -t planner-bot .
   ```

3. **App Runner Deployment Failed**
   - Check AWS Console for detailed error messages
   - Verify ECR image was pushed successfully
   - Check App Runner service configuration

4. **CORS Errors**
   - Verify CORS configuration in health endpoint response
   - Check browser developer tools for specific CORS errors
   - Use CORS test files: `test-cors.html` or `test-cors-console.js`

### Deployment Script Troubleshooting

The deployment script includes comprehensive error checking:

- **Pre-flight checks**: Verifies Docker, AWS CLI, and credentials
- **Step-by-step validation**: Stops on any error with clear messages
- **Verbose mode**: Use `--verbose` flag for detailed output
- **Dry run**: Use `--dry-run` to preview without executing

### Logs and Debugging

1. **View App Runner logs**:
   - AWS Console → App Runner → Your service → Logs tab

2. **Local Docker testing**:
   ```bash
   docker build -t planner-bot .
   docker run -p 8000:8000 -e OPENAI_API_KEY=your-key planner-bot
   ```

3. **API testing**:
   ```bash
   # Test health endpoint
   curl https://fbm26vyfbw.us-east-1.awsapprunner.com/health
   
   # Test projects endpoint
   curl https://fbm26vyfbw.us-east-1.awsapprunner.com/api/projects
   ```

## Deployment Timeline

Typical deployment takes:
- **Build & Push**: 2-5 minutes
- **App Runner Deployment**: 5-10 minutes
- **Total**: 7-15 minutes

## Security Considerations

1. **API Keys**: Stored in AWS Secrets Manager, not in code
2. **CORS**: Production configuration restricts origins
3. **Container**: Runs as non-root user
4. **Network**: App Runner provides managed TLS/HTTPS
5. **Logs**: Sensitive data filtered from application logs

## Rollback

To rollback to a previous version:

1. **Find previous image tag** in ECR console
2. **Update App Runner** to use previous image
3. **Or redeploy** from a previous git commit:
   ```bash
   git checkout <previous-commit>
   ./deploy-backend.sh
   git checkout main
   ```

## Production Checklist

Before deploying to production:

- [ ] Environment variables configured
- [ ] API keys stored in Secrets Manager
- [ ] CORS origins properly configured
- [ ] Health check endpoint accessible
- [ ] Monitoring and logging enabled
- [ ] Error handling tested
- [ ] Performance testing completed
- [ ] Security review completed
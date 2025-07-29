#!/bin/bash

# Deploy Backend Script for Project Planner Bot
# Builds, tags, pushes Docker image to ECR and deploys to AWS App Runner

set -e  # Exit on any error

# Configuration
SERVICE_ARN="arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9"
ECR_REPOSITORY="348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot"
AWS_PROFILE="348204830428_SoftwareEngineering"
AWS_REGION="us-east-1"
IMAGE_NAME="planner-bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed or not in PATH"
        exit 1
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    print_status "Checking AWS credentials..."
    if ! aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
        print_error "AWS credentials not configured for profile: $AWS_PROFILE"
        print_warning "Run: aws configure sso --profile $AWS_PROFILE"
        exit 1
    fi
    print_success "AWS credentials verified"
}

# Function to check git status
check_git_status() {
    print_status "Checking git status..."
    if [[ -n $(git status --porcelain) ]]; then
        print_warning "You have uncommitted changes. Consider committing them first."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    print_success "Git status checked"
}

# Main deployment function
deploy_backend() {
    print_status "🚀 Starting backend deployment to AWS App Runner..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Pre-flight checks
    print_status "Running pre-flight checks..."
    check_command "docker"
    check_command "aws"
    check_command "git"
    
    check_git_status
    check_aws_credentials
    
    echo
    print_status "📦 Building Docker image..."
    if docker build -t $IMAGE_NAME .; then
        print_success "Docker image built successfully"
    else
        print_error "Docker build failed"
        exit 1
    fi
    
    echo
    print_status "🏷️  Tagging image for ECR..."
    if docker tag $IMAGE_NAME:latest $ECR_REPOSITORY:latest; then
        print_success "Image tagged for ECR"
    else
        print_error "Docker tag failed"
        exit 1
    fi
    
    echo
    print_status "🔐 Logging into ECR..."
    if aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | docker login --username AWS --password-stdin $ECR_REPOSITORY; then
        print_success "ECR login successful"
    else
        print_error "ECR login failed"
        exit 1
    fi
    
    echo
    print_status "⬆️  Pushing image to ECR..."
    if docker push $ECR_REPOSITORY:latest; then
        print_success "Image pushed to ECR successfully"
    else
        print_error "Docker push failed"
        exit 1
    fi
    
    echo
    print_status "🚀 Deploying to AWS App Runner..."
    OPERATION_ID=$(aws apprunner start-deployment \
        --service-arn $SERVICE_ARN \
        --region $AWS_REGION \
        --profile $AWS_PROFILE \
        --output text \
        --query 'OperationId')
    
    if [[ -n "$OPERATION_ID" ]]; then
        print_success "Deployment initiated successfully!"
        echo
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_status "📋 Deployment Details:"
        echo "   Operation ID: $OPERATION_ID"
        echo "   Service ARN:  $SERVICE_ARN"
        echo "   ECR Image:    $ECR_REPOSITORY:latest"
        echo
        print_status "🌐 Endpoints:"
        echo "   API Base:     https://fbm26vyfbw.us-east-1.awsapprunner.com"
        echo "   Health Check: https://fbm26vyfbw.us-east-1.awsapprunner.com/health"
        echo "   API Docs:     https://fbm26vyfbw.us-east-1.awsapprunner.com/docs"
        echo
        print_status "⏱️  Deployment Status:"
        echo "   • Deployment typically takes 5-10 minutes"
        echo "   • Monitor progress in AWS App Runner Console"
        echo "   • Check health endpoint when deployment completes"
        echo
        print_status "🔍 Monitor deployment:"
        echo "   AWS Console: https://console.aws.amazon.com/apprunner/"
        echo "   CLI Command: aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION --profile $AWS_PROFILE"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_success "🎉 Backend deployment process completed successfully!"
    else
        print_error "Failed to start App Runner deployment"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "Backend Deployment Script for Project Planner Bot"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --verbose  Enable verbose output"
    echo "  --dry-run      Show what would be deployed without actually deploying"
    echo
    echo "Environment Variables:"
    echo "  SERVICE_ARN    AWS App Runner service ARN (default: configured)"
    echo "  ECR_REPOSITORY ECR repository URL (default: configured)"
    echo "  AWS_PROFILE    AWS profile to use (default: $AWS_PROFILE)"
    echo
    echo "Examples:"
    echo "  $0                    # Deploy with default settings"
    echo "  $0 --dry-run          # Show deployment plan"
    echo "  $0 --verbose          # Deploy with verbose output"
}

# Function for dry run
dry_run() {
    print_status "🔍 Dry run - showing what would be deployed:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Service ARN:     $SERVICE_ARN"
    echo "ECR Repository:  $ECR_REPOSITORY"
    echo "AWS Profile:     $AWS_PROFILE"
    echo "AWS Region:      $AWS_REGION"
    echo "Image Name:      $IMAGE_NAME"
    echo
    echo "Steps that would be executed:"
    echo "1. Build Docker image: $IMAGE_NAME"
    echo "2. Tag for ECR: $ECR_REPOSITORY:latest"
    echo "3. Login to ECR"
    echo "4. Push image to ECR"
    echo "5. Deploy to App Runner"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Parse command line arguments
VERBOSE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            set -x  # Enable verbose mode
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
if [[ "$DRY_RUN" == "true" ]]; then
    dry_run
else
    deploy_backend
fi
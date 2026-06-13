#!/usr/bin/env bash
#
# Deploy the Flight Delay Predictor to AWS:
#   1. build the Docker image, 2. push it to ECR,
#   3. create/update the CloudFormation stack (ALB + Auto Scaling Group).
#
# Prereqs: awscli v2 (configured), docker.
# Usage:   VPC_ID=vpc-xxx SUBNET_IDS=subnet-a,subnet-b ./deploy/deploy.sh
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-flight-delay-predictor}"
ECR_REPO="${ECR_REPO:-flight-delay-predictor}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
TEMPLATE="$(dirname "$0")/cloudformation.yaml"

: "${VPC_ID:?Set VPC_ID (e.g. vpc-0abc123)}"
: "${SUBNET_IDS:?Set SUBNET_IDS as a comma-separated list (e.g. subnet-a,subnet-b)}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"
echo "==> Region=${AWS_REGION}  Stack=${STACK_NAME}  Image=${IMAGE_URI}"

echo "==> Ensuring ECR repository '${ECR_REPO}' exists"
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION" \
       --image-scanning-configuration scanOnPush=true >/dev/null

echo "==> Logging in to ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Building image (linux/amd64 for EC2)"
docker build --platform linux/amd64 -t "$IMAGE_URI" .

echo "==> Pushing image"
docker push "$IMAGE_URI"

echo "==> Deploying CloudFormation stack"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      VpcId="$VPC_ID" \
      SubnetIds="$SUBNET_IDS" \
      EcrImageUri="$IMAGE_URI" \
  --no-fail-on-empty-changeset

ASG_NAME="$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='AutoScalingGroupName'].OutputValue" --output text)"
echo "==> Triggering instance refresh on ${ASG_NAME}"
aws autoscaling start-instance-refresh --region "$AWS_REGION" \
  --auto-scaling-group-name "$ASG_NAME" \
  --preferences MinHealthyPercentage=50,InstanceWarmup=90 >/dev/null 2>&1 \
  || echo "    (instance refresh skipped — fresh stack)"

API_URL="$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)"
echo ""
echo "==> Deployed. API URL: ${API_URL}"
echo "    Health: curl ${API_URL}/health   Docs: ${API_URL}/docs"

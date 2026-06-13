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

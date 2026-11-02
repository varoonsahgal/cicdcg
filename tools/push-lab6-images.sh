#!/usr/bin/env bash
# Build the four Galactic Pizza releases (Lab 6) and push them to the shared ECR repository
# pipeline-academy/galactic-pizza, which every student's task definition pulls from.
# Run once before class from the repo root (needs Docker with buildx and an admin profile):
#   tools/push-lab6-images.sh
set -euo pipefail
export AWS_PROFILE=${AWS_PROFILE:-instructor-01}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-west-2}
REPO=pipeline-academy/galactic-pizza
ACCT=$(aws sts get-caller-identity --query Account --output text)
REG=$ACCT.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com

aws ecr describe-repositories --repository-names $REPO >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name $REPO --image-tag-mutability IMMUTABLE \
      --image-scanning-configuration scanOnPush=true >/dev/null
aws ecr get-login-password | docker login --username AWS --password-stdin $REG

for R in 1.0 1.1 1.2 1.3; do
  if aws ecr describe-images --repository-name $REPO --image-ids imageTag=$R >/dev/null 2>&1; then
    echo "$REPO:$R already pushed (the repository is immutable; delete the image first to rebuild)"; continue
  fi
  # Fargate tasks in Lab 6 run on X86_64, so build for linux/amd64 even on an Apple-silicon laptop.
  docker buildx build --platform linux/amd64 --provenance=false --build-arg RELEASE=$R \
      -t $REG/$REPO:$R --push lab6-ecs-advanced/app
done
aws ecr describe-images --repository-name $REPO --query 'sort_by(imageDetails,&imageTags[0])[].[imageTags[0],imageDigest]' --output table

#!/usr/bin/env bash
# Reset ONE student's Lab 3 environment to its original broken state
# (re-plants all six bugs, re-uploads the pristine bundle, removes any IAM
# policies they attached). The pipeline will auto-run once after the reset.
#
#   ./reset-student.sh 07          # resets participant-07
#
# Do NOT run a plain `terraform apply` during class: that resets EVERY student.
set -euo pipefail
NN=${1:?usage: $0 <two-digit student number>}
STU="${STUDENT_PREFIX:-participant}-$(printf '%02d' "${NN#0}")"
cd "$(dirname "$0")"
echo ">> resetting $STU"
terraform apply -auto-approve -compact-warnings \
  -target="aws_s3_object.app[\"$STU\"]" \
  -target="aws_codedeploy_deployment_group.group[\"$STU\"]" \
  -target="aws_codepipeline.pipeline[\"$STU\"]" \
  -target="aws_codebuild_project.build[\"$STU\"]" \
  -target="aws_instance.web[\"$STU\"]" \
  -target="aws_iam_role_policy.codebuild[\"$STU\"]" \
  -target="aws_iam_role_policies_exclusive.codebuild[\"$STU\"]" \
  -target="aws_iam_role_policy_attachments_exclusive.codebuild[\"$STU\"]" \
  -target="aws_iam_role_policies_exclusive.ec2[\"$STU\"]" \
  -target="aws_iam_role_policy_attachments_exclusive.ec2[\"$STU\"]"
echo ">> $STU reset. Their pipeline will run again within a minute."

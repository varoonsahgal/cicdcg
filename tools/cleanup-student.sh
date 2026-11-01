#!/usr/bin/env bash
# Delete everything a student created by hand in Labs 1, 2 and 4 (including the Lab 1 missions and Lab 2 level-ups).
#   tools/cleanup-student.sh 01 02 07          # specific students
#   tools/cleanup-student.sh $(seq -w 1 15)    # a whole class
# Needs an admin profile (students cannot delete IAM roles). Idempotent: missing resources are skipped.
# Lab 3 and Lab 5 are Terraform-managed: use `terraform destroy` there instead.
set -u
export AWS_PROFILE=${AWS_PROFILE:-instructor-01}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-west-2}
ACCT=$(aws sts get-caller-identity --query Account --output text)

empty_and_delete_bucket() {
  local b=$1
  aws s3api head-bucket --bucket "$b" 2>/dev/null || { echo "   bucket $b: absent"; return; }
  aws s3api list-object-versions --bucket "$b" --output json \
    | jq -c '{Objects: ([.Versions[]?, .DeleteMarkers[]?] | map({Key, VersionId})), Quiet: true} | select(.Objects | length > 0)' \
    | while read -r batch; do aws s3api delete-objects --bucket "$b" --delete "$batch" >/dev/null; done
  aws s3 rb "s3://$b" >/dev/null && echo "   bucket $b: deleted"
}

delete_role() {
  local r=$1
  aws iam get-role --role-name "$r" >/dev/null 2>&1 || { echo "   role $r: absent"; return; }
  for p in $(aws iam list-attached-role-policies --role-name "$r" --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$r" --policy-arn "$p"
    [[ $p == arn:aws:iam::${ACCT}:policy/* ]] && aws iam delete-policy --policy-arn "$p" 2>/dev/null
  done
  for p in $(aws iam list-role-policies --role-name "$r" --query 'PolicyNames[]' --output text); do aws iam delete-role-policy --role-name "$r" --policy-name "$p"; done
  for ip in $(aws iam list-instance-profiles-for-role --role-name "$r" --query 'InstanceProfiles[].InstanceProfileName' --output text); do
    aws iam remove-role-from-instance-profile --instance-profile-name "$ip" --role-name "$r"; aws iam delete-instance-profile --instance-profile-name "$ip"
  done
  aws iam delete-role --role-name "$r" && echo "   role $r: deleted"
}

delete_sg() {
  local name=$1
  local id; id=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$name" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
  [ "$id" = "None" ] || [ -z "$id" ] && return
  for i in 1 2 3 4 5 6; do aws ec2 delete-security-group --group-id "$id" 2>/dev/null && { echo "   security group $name: deleted"; return; }; sleep 20; done
  echo "   security group $name: still in use, delete later"
}

for NN in "$@"; do
  STU="participant-$NN"
  echo "== $STU"
  ## Lab 2: pipeline, CodeDeploy, EC2
  aws codepipeline delete-pipeline --name "$STU-pipeline" 2>/dev/null && echo "   pipeline deleted"
  for rule in $(aws events list-rule-names-by-target --target-arn "arn:aws:codepipeline:$AWS_DEFAULT_REGION:$ACCT:$STU-pipeline" --query 'RuleNames[]' --output text); do
    for t in $(aws events list-targets-by-rule --rule "$rule" --query 'Targets[].Id' --output text); do aws events remove-targets --rule "$rule" --ids "$t" >/dev/null; done
    aws events delete-rule --name "$rule" && echo "   eventbridge rule $rule deleted"
  done
  aws deploy delete-application --application-name "$STU-webapp" 2>/dev/null && echo "   codedeploy app deleted"
  IDS=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=$STU-webserver" Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)
  if [ -n "$IDS" ]; then aws ec2 terminate-instances --instance-ids $IDS >/dev/null; echo "   terminating $IDS"; aws ec2 wait instance-terminated --instance-ids $IDS; fi
  delete_sg "$STU-webserver-sg"
  ## Lab 2 level-ups: the pipeline's Build stage project
  aws codebuild delete-project --name "$STU-pipeline-build" >/dev/null 2>&1 && echo "   pipeline-build project deleted"
  aws logs delete-log-group --log-group-name "/aws/codebuild/$STU-pipeline-build" 2>/dev/null && echo "   log group deleted"
  ## Lab 1: CodeBuild
  aws codebuild delete-project --name "$STU-codebuild-demo" >/dev/null 2>&1 && echo "   codebuild project deleted"
  aws logs delete-log-group --log-group-name "/aws/codebuild/$STU-codebuild-demo" 2>/dev/null && echo "   log group deleted"
  for rg in $(aws codebuild list-report-groups --query 'reportGroups[]' --output text | tr '\t' '\n' | grep -E "$STU-(codebuild-demo|image-build|pipeline-build)"); do aws codebuild delete-report-group --arn "$rg" --delete-reports >/dev/null && echo "   report group deleted"; done
  ## Lab 1 missions / Lab 2 missions: secret, alerts topic, EventBridge rule
  aws secretsmanager delete-secret --secret-id "$STU/lab1/deploy-token" --force-delete-without-recovery >/dev/null 2>&1 && echo "   secret deleted"
  for rule in "$STU-build-failed"; do
    if aws events describe-rule --name "$rule" >/dev/null 2>&1; then
      for t in $(aws events list-targets-by-rule --rule "$rule" --query 'Targets[].Id' --output text); do aws events remove-targets --rule "$rule" --ids "$t" >/dev/null; done
      aws events delete-rule --name "$rule" && echo "   eventbridge rule $rule deleted"
    fi
  done
  for t in $(aws sns list-topics --query "Topics[?ends_with(TopicArn, ':$STU-alerts')].TopicArn" --output text); do aws sns delete-topic --topic-arn "$t" && echo "   sns topic deleted"; done
  ## Lab 4: ECS service/cluster, ALB, ECR, CodeBuild
  if aws ecs describe-services --cluster "$STU-cluster" --services "$STU-svc" --query 'services[?status!=`INACTIVE`].serviceName' --output text 2>/dev/null | grep -q .; then
    aws ecs update-service --cluster "$STU-cluster" --service "$STU-svc" --desired-count 0 >/dev/null
    aws ecs delete-service --cluster "$STU-cluster" --service "$STU-svc" --force >/dev/null && echo "   ecs service deleted (draining)"
    aws ecs wait services-inactive --cluster "$STU-cluster" --services "$STU-svc"
  fi
  aws ecs delete-cluster --cluster "$STU-cluster" >/dev/null 2>&1 && echo "   ecs cluster deleted"
  for td in $(aws ecs list-task-definitions --family-prefix "$STU-mission-control" --query 'taskDefinitionArns[]' --output text); do aws ecs deregister-task-definition --task-definition "$td" >/dev/null; done
  TDS=$(aws ecs list-task-definitions --family-prefix "$STU-mission-control" --status INACTIVE --query 'taskDefinitionArns[]' --output text); [ -n "$TDS" ] && aws ecs delete-task-definitions --task-definitions $TDS >/dev/null 2>&1 && echo "   task definitions deleted"
  ALB=$(aws elbv2 describe-load-balancers --names "$STU-mission-alb" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null)
  if [ -n "$ALB" ] && [ "$ALB" != "None" ]; then aws elbv2 delete-load-balancer --load-balancer-arn "$ALB" && echo "   alb deleted"; sleep 20; fi
  TG=$(aws elbv2 describe-target-groups --names "$STU-mission-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null)
  [ -n "$TG" ] && [ "$TG" != "None" ] && for i in 1 2 3 4; do aws elbv2 delete-target-group --target-group-arn "$TG" 2>/dev/null && { echo "   target group deleted"; break; }; sleep 15; done
  delete_sg "$STU-mission-sg"; delete_sg "$STU-alb-sg"
  aws ecr delete-repository --repository-name "$STU-mission-control" --force >/dev/null 2>&1 && echo "   ecr repository deleted"
  aws codebuild delete-project --name "$STU-image-build" >/dev/null 2>&1 && echo "   image-build project deleted"
  for lg in "/aws/codebuild/$STU-image-build" "/ecs/$STU-mission-control"; do aws logs delete-log-group --log-group-name "$lg" 2>/dev/null && echo "   log group $lg deleted"; done
  for p in "/$STU/mission-control/motd" "/$STU/mission-control/launch-code"; do aws ssm delete-parameter --name "$p" 2>/dev/null && echo "   parameter $p deleted"; done
  ## Buckets
  empty_and_delete_bucket "cicd-lab1-$STU"
  empty_and_delete_bucket "cicd-lab2-$STU"
  empty_and_delete_bucket "cicd-lab4-$STU"
  ## IAM
  delete_role "$STU-ec2-codedeploy-role"
  delete_role "$STU-codedeploy-service-role"
  delete_role "codebuild-$STU-codebuild-demo-service-role"
  delete_role "codebuild-$STU-pipeline-build-service-role"
  delete_role "codebuild-$STU-image-build-service-role"
  delete_role "$STU-task-role"
  delete_role "$STU-task-execution-role"
  delete_role "AWSCodePipelineServiceRole-$AWS_DEFAULT_REGION-$STU-pipeline"
  delete_role "cwe-role-$AWS_DEFAULT_REGION-$STU-pipeline"
done
echo "Shared leftovers created by the Lab 2 pipeline wizard, once no pipelines remain: the codepipeline-$AWS_DEFAULT_REGION-* artifact bucket and the 'codepipeline-source-trail' CloudTrail trail."

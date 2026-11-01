############################################################
# Shared · extra permissions students need for Lab 4 (ECS/ECR) and
# Lab 5 (EKS + CloudShell), plus the ECS task execution role they select.
#
# The students' group policy (dc-ec2-policy) has no ecs/ecr/eks/cloudshell
# at all, and the instructor cannot modify that group. So this attaches ONE
# customer-managed policy directly to each participant user.
############################################################
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile
  default_tags { tags = { Lab = "cicd-labs-shared", ManagedBy = "terraform" } }
}

variable "region" { default = "us-west-2" }
variable "aws_profile" { default = "instructor-01" }
variable "student_count" { default = 15 }
variable "student_prefix" { default = "participant" }

# Set to true (the instructor, before class) to attach the policy to the participant users.
# Creating the policy and role does not change anyone's access; the attachment does.
variable "attach_to_users" {
  type    = bool
  default = false
}

data "aws_caller_identity" "current" {}

locals {
  students = toset([for i in range(1, var.student_count + 1) : format("%s-%02d", var.student_prefix, i)])
  account  = data.aws_caller_identity.current.account_id
}

# ── The policy ──────────────────────────────────────────────
data "aws_iam_policy_document" "containers" {
  statement {
    sid       = "Containers"
    actions   = ["ecr:*", "ecs:*", "elasticloadbalancing:*", "application-autoscaling:*", "servicediscovery:*"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.region]
    }
  }
  statement {
    sid       = "EcrPublicLogin"
    actions   = ["ecr-public:GetAuthorizationToken", "sts:GetServiceBearerToken"]
    resources = ["*"]
  }
  statement {
    sid       = "Eks"
    actions   = ["eks:DescribeCluster", "eks:ListClusters", "eks:AccessKubernetesApi", "eks:ListAccessEntries", "eks:DescribeAccessEntry", "eks:ListNodegroups", "eks:DescribeNodegroup", "eks:ListAddons", "eks:DescribeAddon"]
    resources = ["*"]
  }
  statement {
    sid       = "CloudShell"
    actions   = ["cloudshell:*"]
    resources = ["*"]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:*"]
    resources = ["*"]
  }
  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "iam:AWSServiceName"
      values   = ["ecs.amazonaws.com", "elasticloadbalancing.amazonaws.com", "ecs.application-autoscaling.amazonaws.com", "eks.amazonaws.com", "eks-nodegroup.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "containers" {
  name        = "cicd-labs-containers-student"
  description = "Lab 4/5 student permissions: ECR, ECS, ELB, EKS read + Kubernetes API, CloudShell"
  policy      = data.aws_iam_policy_document.containers.json
}

resource "aws_iam_user_policy_attachment" "students" {
  for_each   = var.attach_to_users ? local.students : toset([])
  user       = each.key
  policy_arn = aws_iam_policy.containers.arn
}

# ── ECS task execution role students select in their task definitions ──
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "cicd-lab4-task-execution-role"
  description        = "Pulls images from ECR and writes container logs for Lab 4 tasks"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

output "policy_arn" { value = aws_iam_policy.containers.arn }
output "task_execution_role" { value = aws_iam_role.task_execution.name }
output "attached_to" { value = var.attach_to_users ? sort(tolist(local.students)) : [] }
output "attach_command" { value = "terraform apply -var attach_to_users=true   # grants Lab 4/5 permissions to ${var.student_prefix}-01..${format("%02d", var.student_count)}" }

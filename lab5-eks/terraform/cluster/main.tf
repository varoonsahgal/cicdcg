############################################################
# Lab 5 · one shared EKS cluster for the whole class.
# Students get a namespace each (see ../students) and reach the
# cluster from AWS CloudShell with kubectl.
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
  default_tags { tags = { Lab = "cicd-lab5", ManagedBy = "terraform" } }
}

variable "region" { default = "us-west-2" }
variable "aws_profile" { default = "instructor-01" }
variable "cluster_name" { default = "cicd-lab5-eks" }
variable "kubernetes_version" { default = "1.33" }
variable "node_instance_type" { default = "t3.large" }
variable "node_count" { default = 4 } # 2 is ~95 % of CPU requests for 15 students × 2 Pods; 4 leaves room to scale
variable "student_count" { default = 15 }
variable "student_prefix" { default = "participant" }

data "aws_caller_identity" "current" {}
data "aws_vpc" "default" { default = true }
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

locals {
  students = toset([for i in range(1, var.student_count + 1) : format("%s-%02d", var.student_prefix, i)])
}

# ── IAM: cluster role ───────────────────────────────────────
resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-cluster-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# ── IAM: node role ──────────────────────────────────────────
resource "aws_iam_role" "node" {
  name = "${var.cluster_name}-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly", # pull students' Lab 4 images from ECR
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

# Public subnets need this tag so `Service: type LoadBalancer` can place an
# internet-facing load balancer. Removed again on destroy.
resource "aws_ec2_tag" "elb" {
  for_each    = toset(data.aws_subnets.public.ids)
  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

# ── The cluster ─────────────────────────────────────────────
resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = data.aws_subnets.public.ids
    endpoint_public_access  = true
    endpoint_private_access = true
  }

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true # the instructor profile is cluster-admin
  }

  depends_on = [aws_iam_role_policy_attachment.cluster, aws_ec2_tag.elb]
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "general"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = data.aws_subnets.public.ids
  instance_types  = [var.node_instance_type]
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = var.node_count
    min_size     = var.node_count
    max_size     = var.node_count + 1
  }
  update_config { max_unavailable = 1 }

  depends_on = [aws_iam_role_policy_attachment.node]
}

# Managed add-ons (versions default to the latest compatible).
resource "aws_eks_addon" "core" {
  for_each                    = toset(["vpc-cni", "coredns", "kube-proxy", "metrics-server"])
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.value
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.default]
}

# ── One access entry per student ───────────────────────────
# Maps the IAM user to a Kubernetes group of the same name; the ../students
# module binds that group to a Role inside the student's namespace.
resource "aws_eks_access_entry" "student" {
  for_each          = local.students
  cluster_name      = aws_eks_cluster.this.name
  principal_arn     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/${each.key}"
  kubernetes_groups = [each.key]
  type              = "STANDARD"
  tags              = { Student = each.key }
}

output "cluster_name" { value = aws_eks_cluster.this.name }
output "cluster_endpoint" { value = aws_eks_cluster.this.endpoint }
output "kubeconfig_command" { value = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.this.name}" }
output "students" { value = sort(tolist(local.students)) }

############################################################
# Lab 5 · per-student Kubernetes namespaces, RBAC and quotas.
# Apply AFTER ../cluster.  Uses the kubernetes provider authenticated
# through the instructor's AWS profile (cluster creator = admin).
############################################################
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
}

variable "region" { default = "us-west-2" }
variable "aws_profile" { default = "instructor-01" }
variable "cluster_name" { default = "cicd-lab5-eks" }
variable "student_count" { default = 15 }
variable "student_prefix" { default = "participant" }

provider "aws" {
  region  = var.region
  profile = var.aws_profile
}

data "aws_eks_cluster" "this" { name = var.cluster_name }

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.region, "--profile", var.aws_profile]
  }
}

locals {
  students = toset([for i in range(1, var.student_count + 1) : format("%s-%02d", var.student_prefix, i)])
}

# ── One namespace per student ───────────────────────────────
resource "kubernetes_namespace_v1" "student" {
  for_each = local.students
  metadata {
    name   = each.key
    labels = { student = each.key, lab = "cicd-lab5" }
  }
}

# Full control inside the namespace (the "edit" verbs plus logs/exec/port-forward).
resource "kubernetes_role_v1" "owner" {
  for_each = local.students
  metadata {
    name      = "namespace-owner"
    namespace = kubernetes_namespace_v1.student[each.key].metadata[0].name
  }
  rule {
    api_groups = ["", "apps", "batch", "autoscaling", "networking.k8s.io", "policy", "metrics.k8s.io"]
    resources  = ["*"]
    verbs      = ["*"]
  }
}

resource "kubernetes_role_binding_v1" "owner" {
  for_each = local.students
  metadata {
    name      = "namespace-owner"
    namespace = kubernetes_namespace_v1.student[each.key].metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.owner[each.key].metadata[0].name
  }
  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = each.key # the kubernetes_groups value on the student's EKS access entry
  }
}

# Cluster-wide read-only on a few harmless things so `kubectl get nodes` works.
resource "kubernetes_cluster_role_v1" "viewer" {
  metadata { name = "cicd-lab5-viewer" }
  rule {
    api_groups = [""]
    resources  = ["nodes", "namespaces"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["metrics.k8s.io"]
    resources  = ["nodes", "pods"]
    verbs      = ["get", "list"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "viewer" {
  metadata { name = "cicd-lab5-viewer" }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.viewer.metadata[0].name
  }
  dynamic "subject" {
    for_each = local.students
    content {
      api_group = "rbac.authorization.k8s.io"
      kind      = "Group"
      name      = subject.value
    }
  }
}

# Guard-rails: nobody can take the cluster down by scaling to 500 replicas.
resource "kubernetes_resource_quota_v1" "student" {
  for_each = local.students
  metadata {
    name      = "lab-quota"
    namespace = kubernetes_namespace_v1.student[each.key].metadata[0].name
  }
  spec {
    hard = {
      "pods"                   = "12"
      "services.loadbalancers" = "2"
      "requests.cpu"           = "2"
      "requests.memory"        = "3Gi"
      "limits.cpu"             = "4"
      "limits.memory"          = "6Gi"
    }
  }
}

# Default requests/limits so pods without them still count against the quota.
resource "kubernetes_limit_range_v1" "student" {
  for_each = local.students
  metadata {
    name      = "lab-defaults"
    namespace = kubernetes_namespace_v1.student[each.key].metadata[0].name
  }
  spec {
    limit {
      type            = "Container"
      default         = { cpu = "250m", memory = "256Mi" }
      default_request = { cpu = "100m", memory = "128Mi" }
    }
  }
}

output "namespaces" { value = sort([for n in kubernetes_namespace_v1.student : n.metadata[0].name]) }

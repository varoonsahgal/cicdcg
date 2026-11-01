terraform {
  required_version = ">= 1.5"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = {
      Lab       = "cicd-lab3"
      ManagedBy = "terraform"
    }
  }
}

# Second provider WITHOUT default_tags. Used only for the S3 source object:
# CodePipeline's S3 source action fails with "The provided role does not have
# permissions to perform this action" when the source object carries tags.
provider "aws" {
  alias   = "notags"
  region  = var.region
  profile = var.aws_profile
}

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

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  # participant-01 .. participant-NN
  students = toset([for i in range(1, var.student_count + 1) : format("%s-%02d", var.student_prefix, i)])
  prefix   = "cicd-lab3"
}

# The (deliberately broken) application bundle every student starts from.
data "archive_file" "app" {
  type        = "zip"
  source_dir  = "${path.module}/app"
  output_path = "${path.module}/.build/app.zip"
}

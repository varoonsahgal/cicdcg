# Explicit log group so `terraform destroy` removes it (CodeBuild would otherwise
# auto-create one that outlives the lab).
resource "aws_cloudwatch_log_group" "codebuild" {
  for_each          = local.students
  name              = "/aws/codebuild/${local.prefix}-${each.key}-build"
  retention_in_days = 7
  tags              = { Student = each.key }
}

resource "aws_codebuild_project" "build" {
  for_each      = local.students
  name          = "${local.prefix}-${each.key}-build"
  description   = "Lab 3 build for ${each.key} - reads buildspec.yml from the source bundle"
  service_role  = aws_iam_role.codebuild[each.key].arn
  build_timeout = 10

  artifacts { type = "CODEPIPELINE" }

  environment {
    compute_type = "BUILD_GENERAL1_SMALL"
    image        = "aws/codebuild/amazonlinux-x86_64-standard:5.0"
    type         = "LINUX_CONTAINER"
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "buildspec.yml"
  }

  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.codebuild[each.key].name
    }
  }

  tags = { Student = each.key }
}

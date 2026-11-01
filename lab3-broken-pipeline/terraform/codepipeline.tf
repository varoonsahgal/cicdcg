resource "aws_codepipeline" "pipeline" {
  for_each      = local.students
  name          = "${local.prefix}-${each.key}-pipeline"
  role_arn      = aws_iam_role.codepipeline[each.key].arn
  pipeline_type = "V2"

  artifact_store {
    location = aws_s3_bucket.lab[each.key].bucket
    type     = "S3"
  }

  stage {
    name = "Source"
    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "S3"
      version          = "1"
      output_artifacts = ["SourceArtifact"]
      configuration = {
        S3Bucket             = aws_s3_bucket.lab[each.key].bucket
        S3ObjectKey          = aws_s3_object.app[each.key].key
        PollForSourceChanges = "true" # simple + no CloudTrail dependency
      }
    }
  }

  stage {
    name = "Build"
    action {
      name             = "Build"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["SourceArtifact"]
      output_artifacts = ["BuildArtifact"]
      configuration = {
        ProjectName = aws_codebuild_project.build[each.key].name
      }
    }
  }

  stage {
    name = "Deploy"
    action {
      name            = "Deploy"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "CodeDeploy"
      version         = "1"
      input_artifacts = ["BuildArtifact"]
      configuration = {
        ApplicationName     = aws_codedeploy_app.app[each.key].name
        DeploymentGroupName = aws_codedeploy_deployment_group.group[each.key].deployment_group_name
      }
    }
  }

  tags = { Student = each.key }

  depends_on = [aws_iam_role_policy.codepipeline]
}

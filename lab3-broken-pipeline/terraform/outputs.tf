output "student_environments" {
  description = "Everything a student needs, keyed by IAM user name."
  value = {
    for s in local.students : s => {
      bucket         = aws_s3_bucket.lab[s].bucket
      source_object  = "s3://${aws_s3_bucket.lab[s].bucket}/source/app.zip"
      pipeline       = aws_codepipeline.pipeline[s].name
      pipeline_url   = "https://${var.region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${aws_codepipeline.pipeline[s].name}/view?region=${var.region}"
      codebuild      = aws_codebuild_project.build[s].name
      codedeploy_app = aws_codedeploy_app.app[s].name
      deployment_grp = aws_codedeploy_deployment_group.group[s].deployment_group_name
      instance_id    = aws_instance.web[s].id
      instance_name  = aws_instance.web[s].tags["Name"]
      web_url        = "http://${aws_instance.web[s].public_ip}/"
      ec2_role       = aws_iam_role.ec2[s].name
      codebuild_role = aws_iam_role.codebuild[s].name
    }
  }
}

output "handout_table" {
  description = "Markdown table to paste into the class chat."
  value = join("\n", concat(
    ["| Student | Pipeline | Web URL | Bucket |", "|---|---|---|---|"],
    [for s in sort(tolist(local.students)) :
      "| ${s} | [${aws_codepipeline.pipeline[s].name}](https://${var.region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${aws_codepipeline.pipeline[s].name}/view?region=${var.region}) | http://${aws_instance.web[s].public_ip}/ | ${aws_s3_bucket.lab[s].bucket} |"
    ]
  ))
}

resource "aws_codedeploy_app" "app" {
  for_each         = local.students
  name             = "${local.prefix}-${each.key}-app"
  compute_platform = "Server"
  tags             = { Student = each.key }
}

resource "aws_codedeploy_deployment_group" "group" {
  for_each               = local.students
  app_name               = aws_codedeploy_app.app[each.key].name
  deployment_group_name  = "${local.prefix}-${each.key}-group"
  service_role_arn       = aws_iam_role.codedeploy[each.key].arn
  deployment_config_name = "CodeDeployDefault.AllAtOnce"

  # BUG 3: the EC2 instance is tagged Name = "<prefix>-<student>-web",
  # but this filter looks for "...-server". Zero instances match.
  ec2_tag_set {
    ec2_tag_filter {
      key   = "Name"
      type  = "KEY_AND_VALUE"
      value = "${local.prefix}-${each.key}-server"
    }
  }

  deployment_style {
    deployment_option = "WITHOUT_TRAFFIC_CONTROL"
    deployment_type   = "IN_PLACE"
  }

  auto_rollback_configuration {
    enabled = false
  }

  tags = { Student = each.key }
}

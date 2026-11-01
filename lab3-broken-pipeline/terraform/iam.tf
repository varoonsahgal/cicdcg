############################################################
# IAM for Lab 3.  Two of the six planted bugs live here:
#   BUG 2 - CodeBuild role may read the bucket but not write (no s3:PutObject)
#   BUG 4 - EC2 instance role cannot read S3 (CodeDeploy agent cannot DownloadBundle)
#
# The *_exclusive resources are the "reset" mechanism: a `terraform apply`
# removes any policy a student attached while fixing bugs 2 and 4, so the
# environment goes back to its broken starting state.
############################################################

############################################
# EC2 instance role  (BUG 4 lives here)
############################################
data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  for_each           = local.students
  name               = "${local.prefix}-${each.key}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  tags               = { Student = each.key }
}

# BUG 4: the instance can talk to Systems Manager, but it has NO permission to
# read from S3 - so the CodeDeploy agent cannot download the deployment bundle.
# (The fix students apply: attach AmazonEC2RoleforAWSCodeDeploy - or
#  AmazonS3ReadOnlyAccess - to this role.)
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  for_each   = local.students
  role       = aws_iam_role.ec2[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Reset helpers: exactly this set of managed policies, and no inline policies.
resource "aws_iam_role_policy_attachments_exclusive" "ec2" {
  for_each    = local.students
  role_name   = aws_iam_role.ec2[each.key].name
  policy_arns = [aws_iam_role_policy_attachment.ec2_ssm[each.key].policy_arn]
}

resource "aws_iam_role_policies_exclusive" "ec2" {
  for_each     = local.students
  role_name    = aws_iam_role.ec2[each.key].name
  policy_names = []
}

resource "aws_iam_instance_profile" "ec2" {
  for_each = local.students
  name     = "${local.prefix}-${each.key}-ec2-profile"
  role     = aws_iam_role.ec2[each.key].name
}

############################################
# CodeDeploy service role (correct)
############################################
data "aws_iam_policy_document" "codedeploy_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codedeploy.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codedeploy" {
  for_each           = local.students
  name               = "${local.prefix}-${each.key}-codedeploy-role"
  assume_role_policy = data.aws_iam_policy_document.codedeploy_trust.json
  tags               = { Student = each.key }
}

resource "aws_iam_role_policy_attachment" "codedeploy" {
  for_each   = local.students
  role       = aws_iam_role.codedeploy[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSCodeDeployRole"
}

############################################
# CodeBuild service role  (BUG 2 lives here)
############################################
data "aws_iam_policy_document" "codebuild_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild" {
  for_each           = local.students
  name               = "${local.prefix}-${each.key}-codebuild-role"
  assume_role_policy = data.aws_iam_policy_document.codebuild_trust.json
  tags               = { Student = each.key }
}

# BUG 2: CodeBuild may READ the source artifact but may not WRITE the output
# artifact back to the bucket (no s3:PutObject). The build itself succeeds,
# then the UPLOAD_ARTIFACTS phase fails with AccessDenied.
data "aws_iam_policy_document" "codebuild" {
  for_each = local.students

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/codebuild/${local.prefix}-${each.key}-*"]
  }

  statement {
    sid = "ReadArtifacts"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetBucketAcl",
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.lab[each.key].arn,
      "${aws_s3_bucket.lab[each.key].arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "codebuild" {
  for_each = local.students
  name     = "${local.prefix}-${each.key}-codebuild-policy"
  role     = aws_iam_role.codebuild[each.key].id
  policy   = data.aws_iam_policy_document.codebuild[each.key].json
}

# Reset helpers: only our inline policy, no managed policies.
resource "aws_iam_role_policies_exclusive" "codebuild" {
  for_each     = local.students
  role_name    = aws_iam_role.codebuild[each.key].name
  policy_names = [aws_iam_role_policy.codebuild[each.key].name]
}

resource "aws_iam_role_policy_attachments_exclusive" "codebuild" {
  for_each    = local.students
  role_name   = aws_iam_role.codebuild[each.key].name
  policy_arns = []
}

############################################
# CodePipeline service role (correct)
############################################
data "aws_iam_policy_document" "codepipeline_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codepipeline.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codepipeline" {
  for_each           = local.students
  name               = "${local.prefix}-${each.key}-codepipeline-role"
  assume_role_policy = data.aws_iam_policy_document.codepipeline_trust.json
  tags               = { Student = each.key }
}

data "aws_iam_policy_document" "codepipeline" {
  for_each = local.students

  statement {
    sid = "ArtifactBucket"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetObjectTagging",
      "s3:GetObjectVersionTagging",
      "s3:GetBucketVersioning",
      "s3:GetBucketAcl",
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:PutObject",
      "s3:PutObjectAcl",
    ]
    resources = [
      aws_s3_bucket.lab[each.key].arn,
      "${aws_s3_bucket.lab[each.key].arn}/*",
    ]
  }

  statement {
    sid       = "Build"
    actions   = ["codebuild:BatchGetBuilds", "codebuild:StartBuild", "codebuild:BatchGetBuildBatches", "codebuild:StartBuildBatch"]
    resources = [aws_codebuild_project.build[each.key].arn]
  }

  statement {
    sid = "Deploy"
    actions = [
      "codedeploy:CreateDeployment",
      "codedeploy:GetApplication",
      "codedeploy:GetApplicationRevision",
      "codedeploy:GetDeployment",
      "codedeploy:GetDeploymentConfig",
      "codedeploy:RegisterApplicationRevision",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "codepipeline" {
  for_each = local.students
  name     = "${local.prefix}-${each.key}-codepipeline-policy"
  role     = aws_iam_role.codepipeline[each.key].id
  policy   = data.aws_iam_policy_document.codepipeline[each.key].json
}

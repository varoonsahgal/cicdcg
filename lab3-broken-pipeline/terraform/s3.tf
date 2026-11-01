# One bucket per student. It holds the pipeline *source* (source/app.zip)
# and the pipeline's intermediate *artifacts* (written by CodePipeline).
resource "aws_s3_bucket" "lab" {
  for_each      = local.students
  bucket        = "${local.prefix}-${each.key}-${local.account_id}"
  force_destroy = true
  tags          = { Student = each.key }
}

# S3 as a pipeline source REQUIRES versioning.
resource "aws_s3_bucket_versioning" "lab" {
  for_each = local.students
  bucket   = aws_s3_bucket.lab[each.key].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "lab" {
  for_each                = local.students
  bucket                  = aws_s3_bucket.lab[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# NOTE: uploaded via the "notags" provider on purpose (see main.tf).
resource "aws_s3_object" "app" {
  provider = aws.notags
  for_each = local.students
  bucket   = aws_s3_bucket.lab[each.key].id
  key      = "source/app.zip"
  source   = data.archive_file.app.output_path
  etag     = data.archive_file.app.output_md5

  depends_on = [aws_s3_bucket_versioning.lab]
}

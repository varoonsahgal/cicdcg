# Lab 3 · "The Pipeline Repair Shop" — instructor Terraform

Creates one deliberately broken CI/CD environment per student:

```
S3 (source/app.zip) → CodePipeline → CodeBuild → CodeDeploy → EC2 (Amazon Linux 2023, CodeDeploy agent pre-installed)
```

Every resource is named `cicd-lab3-<student>-…` and tagged `Student=<student>`, `Lab=cicd-lab3`.

## The six planted bugs (answer key)

| # | Where | What | Student fix |
|---|---|---|---|
| 1 | `app/buildspec.yml` | `grep -q "Build #${…}"` – the ` #` starts a YAML comment, so CodeBuild runs a truncated command | quote the command |
| 2 | `iam.tf` CodeBuild role | no `s3:PutObject` → `UPLOAD_ARTIFACTS` AccessDenied | add `s3:PutObject` to the inline policy |
| 3 | `codedeploy.tf` | tag filter `Name = …-server`, instance is `…-web` → "no instances were found" | edit the deployment group tag value |
| 4 | `iam.tf` EC2 role | only SSM; agent cannot read S3 → `DownloadBundle` AccessDenied | attach `AmazonEC2RoleforAWSCodeDeploy` |
| 5 | `app/scripts/start_server.sh` | `systemctl start htpd` → `ApplicationStart` ScriptFailed | `httpd` |
| 6 | `app/buildspec.yml` `artifacts.files` | `index.html` missing → deployment "succeeds", site shows Apache's test page | add `- index.html` |

The bugs surface in exactly this order; each one hides the next.

## Usage

```bash
cd lab3-broken-pipeline/terraform
cp terraform.tfvars.example terraform.tfvars      # set student_count, profile, region
terraform init
terraform apply                                     # ~6 min for 15 students
terraform output -raw handout_table                 # paste into the class chat
```

Each pipeline runs once automatically after creation and should stop at **Build** (bug 1). If a pipeline shows **Source** failed instead, see "Known behaviours" and start it once by hand:

```bash
aws codepipeline start-pipeline-execution --name cicd-lab3-participant-NN-pipeline
```

### Reset one student (re-plant all six bugs)

```bash
./reset-student.sh 07
```

This re-uploads the pristine `app.zip`, restores the broken tag filter and IAM policies, and removes any policies the student attached. Their pipeline re-runs within a minute.

### Teardown

```bash
terraform destroy
```

Buckets are created with `force_destroy = true`, so the pipeline artifacts inside them do not block the destroy. Students cannot delete IAM roles in this account, so leave teardown to Terraform.

## Known behaviours (read before class)

- **Do not run a plain `terraform apply` while students are working.** It resets *every* environment to the broken state (that is the point of the `*_exclusive` IAM resources). Use `reset-student.sh` for one student.
- **`-target` pulls in dependencies.** Targeting one pipeline also re-applies its deployment group, S3 object and role, which undoes a student's fixes 2–3. `reset-student.sh` relies on this; nothing else should use `-target`.
- **The source object must not carry S3 object tags.** CodePipeline's S3 source action fails with *"The provided role does not have permissions to perform this action"* if `source/app.zip` has tags. The provider's `default_tags` would add them, so the object is uploaded through the `aws.notags` provider alias. Removing tags from an existing object does not create a new version, so pipelines that already failed need a manual start (`aws codepipeline start-pipeline-execution --name …`).
- **Polling, not events.** The pipelines use `PollForSourceChanges = true` so no CloudTrail/EventBridge setup is needed; a new upload is noticed within ~60 s. Do not turn it off with `update-pipeline`; Terraform will turn it back on at the next apply anyway.
- **First-run timing.** All 15 pipelines start together; CodeBuild on-demand capacity handles that fine (observed: 15 builds completed within ~90 s).
- **Costs.** 15 × t3.micro ≈ US$0.16/hour, plus pennies for CodeBuild minutes and S3. Destroy the same day.

## Files

| File | Purpose |
|---|---|
| `main.tf` | providers (including the `notags` alias), default VPC/subnet lookup, AMI lookup, the zip of `app/` |
| `variables.tf` · `terraform.tfvars.example` | `student_count`, `student_prefix`, `region`, `aws_profile`, `instance_type` |
| `iam.tf` | the four roles per student; bugs 2 and 4; the `*_exclusive` reset helpers |
| `s3.tf` | per-student versioned bucket and the pristine `source/app.zip` |
| `codebuild.tf` · `codedeploy.tf` · `codepipeline.tf` · `ec2.tf` | the pipeline itself; bug 3 is in `codedeploy.tf` |
| `user_data.sh` | installs the CodeDeploy agent on first boot |
| `app/` | the student bundle; bugs 1, 5 and 6 live here. **Do not fix them.** |
| `outputs.tf` | `student_environments` (all names per student) and `handout_table` (Markdown) |
| `reset-student.sh` | targeted re-apply for one student |

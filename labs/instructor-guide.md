# Instructor guide · Pipeline Academy (AWS CI/CD labs)

> *Everything the person running the class needs: what to create, what students can and cannot do in this account, the answer keys, the timings we measured, and the teardown.*

| | |
|---|---|
| **Audience** | The instructor and TAs. Students should not see this page. |
| **Account** | Shared training account, alias `dc-lab`, region **us-west-2**. Students sign in as IAM users `participant-01` … `participant-25`. |
| **Tested** | Every lab below was run end to end in this account with the `instructor-01` profile (Labs 1–5 on 2026-10-31; Labs 1–2 again with the new missions and level-ups on 2026-11-01); the screenshots in the guides come from those runs. Lab 3 was deployed for 15 students simultaneously. |
| **Teardown** | One Terraform destroy (Lab 3) + one script (Labs 1–2). Both are below. |

---

## 1 · Schedule that fits

| Block | Lab | Core | With challenges | Notes |
|---|---|---|---|---|
| Morning 1 | Handout "Why CI/CD" walkthrough | 30 min | – | Use the index page; the animated pipeline strip is a good hook |
| Morning 2 | **Lab 1 · CodeBuild** | 45 min | 95–135 min (8 missions) | The planted failure (Java 11 vs 17) costs novices ~10 min. Missions A–H are 10–15 min each; D, E, G are the ones to insist on |
| Afternoon 1 | **Lab 2 · CodePipeline + CodeDeploy** | 70 min | 110 min (exercises) · 160–175 min (+ level-ups + pager) | Longest setup; the "site goes down" exercise is the emotional peak. Parts 9–11 fit a second block or a second day |
| Afternoon 2 | **Lab 3 · Broken pipeline** | 75 min | 100 min | Can be run the next morning as a warm-up instead |
| Day 2 | **Lab 4 · ECS/ECR** | 90 min (Parts 1–9) | 135 min with exercises A–E · +60–90 min for challenges F–K | Part 9 (task role) is the new core piece; the circuit-breaker exercise has a 10-minute wait; see §7 |
| Day 2 | **Lab 5 · EKS** | 80 min (Parts 1–7) | 125 min with challenges A–D · ~175 min with all ten | Cluster must be applied ~20 min before; the shared fallback image must be rebuilt from the new `app.zip`; see §8 |

Measured machine time per pipeline round in Lab 3: **~2 minutes** (poll ≤ 60 s, build ≈ 30 s, deploy ≈ 35 s). Six rounds ≈ 12 minutes of waiting; the rest is reading.

---

## 2 · The student permission model (read this first)

Students are in IAM group **`AWS_Cloud_Foundations`**, which carries the customer-managed **`dc-ec2-policy`** and **`dc-capital-training`** plus `IAMReadOnlyAccess`, `AWSCloudShellFullAccess`, `AWSCloudTrail_FullAccess`, `SecretsManagerReadWrite`, `AWSKeyManagementServicePowerUser`, `AWSStepFunctionsFullAccess`. Relevant facts, verified with the IAM policy simulator:

| Students **can** | Students **cannot** |
|---|---|
| Create S3 buckets, CodeBuild projects, CodeDeploy apps/groups, CodePipelines (us-west-2), EC2 instances + security groups | Create resources in other regions (EC2 is limited to us-west-2/us-west-1/us-east-1/ap-south-1; CodePipeline/CodeDeploy to us-west-2) |
| Create IAM roles, attach managed policies, add inline policies, create instance profiles, pass roles | **Delete** roles, **detach** policies, delete inline policies → cleanup is yours |
| Read CloudWatch Logs, use Systems Manager Session Manager, use CloudShell | Change their own group's policies |
| Create CloudTrail trails / EventBridge rules (the pipeline wizard needs this); ECR, ECS, ELB, EKS API access (via `dc-capital-training`) | Modify EKS access entries or the cluster itself (instructor-only) |

The instructor user (`instructor-01`) has `AdministratorAccess` **except** an explicit deny on `iam:*` against the `AWS_Cloud_Foundations` group itself. You can attach policies to individual users, not to that group.

> [!IMPORTANT]
> Because students cannot delete IAM roles, every Lab 1/2 run leaves 4–6 roles per student (one more if they do Lab 2 Part 9). Run `tools/cleanup-student.sh` after class; the account is at ~560 of 1 000 roles.

---

## 3 · Pre-flight checklist (15 minutes, the day before)

- [ ] Each student has a working console password for `participant-NN` and knows their number.
- [ ] Sign-in URL to share: `https://dc-lab.signin.aws.amazon.com/console` (account alias `dc-lab`).
- [ ] Everyone will work in **us-west-2**. Say it three times.
- [ ] S3 bucket count is under ~70 (hard limit 100 unless raised): `aws s3api list-buckets --query 'length(Buckets)'`. Labs 1–3 add up to 3 buckets per student.
- [ ] Quotas are fine (checked: On-Demand vCPU quota 2 500; Fargate 4 000 vCPU).
- [ ] Students have a laptop/VM that can zip (terminal, Finder or Explorer; the guides explain). Locked-down laptops: Labs 1–2 offer a CloudShell route (`curl` the zip from the Pages site, edit with `nano`, `aws s3 cp`).
- [ ] Windows students edit `.sh` files in VS Code with **LF** line endings (Lab 2 warns them). A CRLF hook script fails on the server with `/bin/bash^M: bad interpreter`; the repo's `.gitattributes` keeps clones LF.
- [ ] Publish the handout site (the `docs/` folder on GitHub Pages) and the lab Markdown (wiki or repo).
- [ ] Lab 3 only: `terraform apply` the night before or 15 minutes before (§6).

---

## 4 · Lab 1 · CodeBuild — facilitator notes

**Student creates:** bucket `cicd-lab1-participant-NN`, project `participant-NN-codebuild-demo` (+ its auto-created service role).

**Planted failure:** `buildspec.yml` asks for `corretto11`; `pom.xml` targets Java 17 → `invalid target release: 17`. Fix: `java: corretto17` in the buildspec, re-zip, re-upload, rebuild.

**Where students get stuck**

| Symptom | Cause | Say this |
|---|---|---|
| `YAML_FILE_ERROR: … buildspec.yml not found` | zip has a top-level folder | "Zip the three items, not the folder." Show `unzip -l` |
| Build still fails after the fix | they rebuilt without re-uploading | "CodeBuild builds what is in S3, not what is on your disk." |
| `Access denied` reading S3 | bucket in another region, or wrong key path `input/MessageUtil.zip` | Check region + key |
| Can't find the test report | they look at the failed build | Reports only exist once Maven ran the tests (green build, or Challenge A) |
| *Role already exists* when creating the project | the role survived an earlier attempt or an earlier cohort (students cannot delete roles) | Choose **Existing service role**, pick it. Running `tools/cleanup-student.sh` between cohorts avoids this |

**The missions (Part 6).** Eight self-contained missions; answers are in the student guide's hidden sections. What each one creates and what we measured on 2026-11-01 with the `amazonlinux-x86_64-standard:6.0` image:

| Mission | Student creates / changes | Measured behaviour | Watch for |
|---|---|---|---|
| A · failing test | edits the test | `BUILD` red, report shows 1 failed | they look at the failed build's missing report instead of the new one |
| B · env var | project env var `GREETING` | greeting + `CODEBUILD_BUILD_NUMBER` in the log | typing the variable into the buildspec instead of the project; writing `echo "… build #$CODEBUILD_BUILD_NUMBER"` unquoted, so YAML cuts it at ` #` and the shell reports an unterminated quote (the solution single-quotes the whole line; a nice preview of Lab 3) |
| C · extra artifact | `build-info.txt` | two files in the output zip | forgetting to add the file to `artifacts.files` |
| D · disabled test | removes `@Ignore` | `expected:<Hi![]Robert> but was:<Hi![Hi!]Robert>`; fix is in `MessageUtil.salutationMessage()` | students "fix" the test instead of the code; push back |
| E · Secrets Manager | secret `participant-NN/lab1/deploy-token`, inline policy `read-lab1-secret` on the service role | build 1 fails in **DOWNLOAD_SOURCE** with `secretsmanager:GetSecretValue` AccessDenied; after the policy the log prints `Deploy token is ***` (masked) | the secret ARN ends in six random characters; copy it from the secret page. Policy JSON typos. Students granting `SecretsManagerReadWrite`: make them narrow it |
| F · S3 cache | project cache `s3://cicd-lab1-participant-NN/cache`, `cache.paths` in buildspec | `Downloading from central:` lines 242 → **0**; BUILD phase 16 s → **10 s**; one 18 MB object under `cache/` | the first cached build logs `Unable to download cache: AccessDenied … s3:ListBucket` (role lacks ListBucket; harmless; guide explains). Edit page is one long form: Artifacts → *Additional configuration* |
| G · EventBridge → SNS | topic `participant-NN-alerts` + e-mail subscription, rule `participant-NN-build-failed` | rule *TriggeredRules* = 1 and SNS *NumberOfMessagesPublished* = 1 within the minute of a failed build | unconfirmed subscription (spam folder); pattern on `SUCCEEDED`; project name typo; the console adds the topic policy, the CLI does not |
| H · Logs Insights | nothing | `FAILURE 3 · SUCCESS 5`; `[ERROR]` lines with their `@logStream` | the console now redirects to **Log Analytics**; the query goes after the generated `SOURCE … |` line. Classic page still works via *Opt out* |

**Cleanup:** students delete the project and bucket; roles, the secret (7-day recovery window unless forced), the topic and the rule are removed by `tools/cleanup-student.sh`.

---

## 5 · Lab 2 · CodePipeline + CodeDeploy — facilitator notes

**Student creates:** 2 IAM roles, 1 EC2 instance (+ SG), bucket `cicd-lab2-participant-NN` (versioned), CodeDeploy app + group, pipeline (+ wizard-created role, artifact bucket, CloudTrail trail, EventBridge rule).

**Pre-brief (5 min, before they click):** the "three robots, three roles" picture from the handout. Half of the help requests in this lab are one of the three roles being wrong.

**Where students get stuck**

| Symptom | Cause | Fix |
|---|---|---|
| Deployment group: *0 unique matched instances* | tag typo / instance in another region / not yet running | Fix tag; wait for *2/2 checks passed* |
| Wizard demands a load balancer | "Enable load balancing" left ticked | Untick it |
| Deploy fails `DownloadBundle` | EC2 role missing `AmazonEC2RoleforAWSCodeDeploy` | Attach, retry |
| Deploy stays *Pending* for minutes then fails | agent not running (user data missing/garbled) | Session Manager → `systemctl status codedeploy-agent`; relaunch with user data if absent |
| Pipeline wizard: S3 source rejected | bucket versioning off | Enable versioning |
| Upload does not trigger the pipeline | EventBridge box unticked, or they uploaded to a different key. Possible but not observed: all wizards edit the **one shared** `codepipeline-source-trail`, so two students finishing the wizard in the same second could overwrite each other's data-event selector | Release change manually; check the key is exactly `SampleApp.zip`. If the key is right, check the trail's data events include their bucket; *Edit → Source → Done → Save* on the pipeline re-adds it |
| Hook fails with `bad interpreter` / `^M` | Windows CRLF line endings in a `.sh` file (usually the new `validate_service.sh`) | Re-save with LF (VS Code status bar) or `sed -i 's/\r$//' scripts/*.sh` in CloudShell |
| Parts 9–11: pipeline sits at *Approve* forever | they kept Challenge D's manual-approval stage | Approve, or delete the stage (the guide tells them) |
| Site down after a failed deploy | expected (Exercise A) | Discuss, then fix and redeploy |

**Shared side effects to know about:** the wizard creates **one** CloudTrail trail `codepipeline-source-trail` and **one** `codepipeline-us-west-2-…` artifact bucket for the whole account; all students share them. They are harmless; delete them once no pipelines remain.

**Verified in this run:** EventBridge trigger within ~12 s of upload; failed `ApplicationStart` leaves Apache stopped (site down); automatic rollback redeploys the previous revision; a `ValidateService` smoke test fails a deployment and triggers rollback; manual approval stage pauses the pipeline.

**Level-ups (Parts 9–11), verified 2026-11-01:**

| Part | Student creates / changes | Measured | Watch for |
|---|---|---|---|
| 9 · Build stage | CodeBuild project `participant-NN-pipeline-build` (+ role, created from inside the pipeline editor); Deploy input → `BuildArtifact` | Build ≈ 30 s; whole execution ≈ 70 s; page shows `Build #N · built …` | **Deploy input left on SourceArtifact** → green pipeline, unstamped page (the guide warns; it is the best "green ≠ correct" moment of the day). Zip without `buildspec.yml` → `YAML_FILE_ERROR`. If they edit the buildspec: a bare ` #` starts a YAML comment (we hit it; the shipped file quotes that line) |
| 9 · Exercise E (gate) | `start_servr.sh` typo in appspec | Build red in ≈ 30 s, `MISSING scripts/start_servr.sh`, Deploy never runs, site untouched | they expect the site to go down as in Exercise A; let the surprise land |
| 10 · second server | second instance with the same Name tag and the existing SG; deployment config `OneAtATime`; `AfterInstall` stamp hook; `ValidateService` with `sleep 20` | group shows *2 unique matched instances* with no edit; rollout ≈ 2 min; pages show different `ip-172-31-…` hostnames and the same deployment id | choosing *Create security group* again (a second SG with the same name fails); forgetting to raise the sleep, so the mid-flight window is too short to see |
| 10 · Exercise F (blast radius) | `htpd` typo, rollback on | deployment fails with `HEALTH_CONSTRAINTS`; the first server *Failed* at ApplicationStart, the second **Skipped**; rollback (also OneAtATime) restores Version 6 on the failed server; the skipped one never left Version 6. Which server goes first is CodeDeploy's choice, so the guide says *first/second*, not *1/2* | "why is the second server Skipped and not Succeeded?" → minimum-healthy-hosts rule; good discussion |
| 11 · triggers | deployment-group trigger `participant-NN-deploy-alerts` → topic `participant-NN-alerts` on *fails* and *rolls back* | SNS publishes two messages per broken deploy (failure + rollback) | topic in another region; unconfirmed subscription. CodeDeploy's role already has `sns:Publish` |

Both instances share the Name tag, so `tools/cleanup-student.sh` terminates them together; it also deletes the `participant-NN-pipeline-build` project, its role and log group.

---

## 6 · Lab 3 · The broken pipeline — setup, answer key, operations

Everything is Terraform: [`lab3-broken-pipeline/terraform/`](../lab3-broken-pipeline/terraform/) (its own README has the file map).

```bash
cd lab3-broken-pipeline/terraform
cp terraform.tfvars.example terraform.tfvars   # student_count = 15
terraform init && terraform apply              # measured: ~6 min for 15 students (≈300 resources)
terraform output -raw handout_table            # paste into chat: pipeline link, web URL, bucket per student
```

Each student's pipeline runs once automatically and stops at **Build** (bug 1). Verify with:

```bash
for i in $(seq -w 1 15); do aws codepipeline get-pipeline-state --name cicd-lab3-participant-$i-pipeline \
  --query 'stageStates[].[stageName,latestExecution.status]' --output text | tr '\n' ' '; echo; done
```

### Answer key

| # | Symptom students see | Root cause | Fix | Concept |
|---|---|---|---|---|
| 1 | Build red · `BUILD` phase · `grep -q "Build` + *unexpected EOF* | ` #` starts a YAML comment; command truncated | quote the command in `buildspec.yml` | YAML vs shell |
| 2 | Build red · `UPLOAD_ARTIFACTS` · AccessDenied `s3:PutObject` | CodeBuild role can read but not write | add `s3:PutObject` to the inline policy | read the principal/action/resource |
| 3 | Deploy red in seconds · *no instances were found* | tag filter `…-server` vs instance `…-web` | edit deployment group tag value (or re-tag) | tags as contracts |
| 4 | Deploy red · `DownloadBundle` · AccessDenied `s3:GetObjectVersion` | EC2 role has only SSM | attach `AmazonEC2RoleforAWSCodeDeploy` | third robot's identity |
| 5 | Deploy red · `ApplicationStart` · *Unit htpd.service not found* | typo in `start_server.sh` | `httpd` | syntax ≠ semantics |
| 6 | All green · Apache test page | `index.html` not in `artifacts.files` | add it | green ≠ correct |

Note for Stop 1: a pristine environment's first build shows **two** red phases (BUILD and UPLOAD_ARTIFACTS). Students must learn to fix the first one first; the guide says so.

### Operating the lab

- **Reset one student:** `./reset-student.sh 07` (re-plants all six bugs; their pipeline re-runs within a minute).
- **Never run a bare `terraform apply` mid-class** — it resets everyone.
- **A student deleted something?** `reset-student.sh` recreates it (it targets the pipeline, which pulls in its dependencies).
- **Kick a pipeline** (for example after an IAM change that did not create a new S3 version): `aws codepipeline start-pipeline-execution --name cicd-lab3-participant-NN-pipeline`.
- **Peek at a student's server:** Systems Manager → Session Manager works on every instance (role has `AmazonSSMManagedInstanceCore`).

### Gotcha we hit while building this (already fixed in the Terraform)

CodePipeline's S3 source action fails with *"The provided role does not have permissions to perform this action"* when the **source object carries S3 object tags**. Terraform's provider `default_tags` tag every object, so `source/app.zip` is uploaded through a second provider alias with no default tags. If you ever see Source red on a fresh environment, check `aws s3api get-object-tagging` on `source/app.zip`.

### Teardown

```bash
terraform destroy          # ~4 min; buckets are force_destroy
```

---

## 7 · Lab 4 · ECR + CodeBuild + ECS Fargate — facilitator notes

**Permissions:** verified with the IAM policy simulator that `participant-NN` users already have everything Lab 4 and Lab 5 need (`ecr:*`, `ecs:*`, `elasticloadbalancing:*`, `eks:*` reads + `eks:AccessKubernetesApi`, `cloudshell:*`, `logs:*`) through the group's `dc-capital-training` and `AWSCloudShellFullAccess` policies. The optional Terraform in `shared/terraform/student-access/` creates an equivalent customer-managed policy for accounts where that is not the case (`terraform apply -var attach_to_users=true` attaches it per user).

**Student creates:** ECR repo `participant-NN-mission-control` · bucket `cicd-lab4-participant-NN` · CodeBuild `participant-NN-image-build` (+ role) · ECS cluster `participant-NN-cluster`, task definition family `participant-NN-mission-control`, service `participant-NN-svc`, security group `participant-NN-mission-sg` · log groups `/aws/codebuild/…` and `/ecs/…` · Parameter Store `/participant-NN/mission-control/motd` (Part 9) and `…/launch-code` (Challenge J) · IAM roles `participant-NN-task-role` (Part 9) and `participant-NN-task-execution-role` (Challenge J) · optionally ALB `participant-NN-mission-alb`, target group, SG.

**Task execution role:** `ecsTaskExecutionRole` already exists in the account (console default). Students can pass it (`iam:PassRole` on `role/*`).

**Planted failures and measured behaviour (participant-01 run, 2026-10-31):**

| Step | What happens | Time |
|---|---|---|
| First build | `PRE_BUILD` fails: `ecr:GetAuthorizationToken` AccessDenied for the new CodeBuild role | ~30 s |
| Fix: attach `AmazonEC2ContainerRegistryPowerUser` | Build 2 pushes `v2` + `latest` (49 MB) | 35 s |
| Service create (2 × Fargate 0.25 vCPU) | both tasks Running + healthy | ~75 s |
| Rolling update to `:v3` | 2 new tasks up, 2 old drained, never below 2 healthy | ~2 min |
| Deploy `:v99` | tasks stop with `CannotPullContainerError … not found`; circuit breaker opens after ~10 launches and rolls back to the previous revision | 8–12 min (tell students to go on with Exercise B meanwhile) |
| `/crash` | task stops (exit 1, *Essential container exited*), service launches a replacement | <1 min |
| ALB challenge | 3 healthy IP targets; hostname rotates per request | ~3 min |

**New in the 2026-11-01 revision (verified locally, not yet run in the account; do a dry run before class):**

| Step | What should happen | How it was verified |
|---|---|---|
| Part 7b · CLI from CloudShell | `describe-services` / `describe-tasks` / `describe-images` queries print tables | JMESPath checked; read-only calls students are allowed |
| Part 8b · dial at min 50 / max 100 | one old task stops before the first new one starts; running count dips to 1 twice | documented ECS behaviour; watch the Tasks tab during the dry run |
| Part 9 · task role | revision with `MOTD_PARAMETER` and no role → page shows `NoCredentialsError`; role without policy → `AccessDeniedException … ssm:GetParameter`; inline policy → green panel on refresh with no redeploy; parameter edit shows on refresh | the app's SSM path was run in Docker with no credentials (0.3 s failure) and with real IAM credentials against a throwaway parameter; the three error/success states are exactly what boto3 returns. `AWS_EC2_METADATA_DISABLED=true` in the image keeps the no-role case fast and deterministic |
| Exercise D · `/hog` | stopped reason `OutOfMemoryError: Container killed due to memory usage`, exit code 137, replacement task | Docker `-m 256m`: OOMKilled=true, ExitCode=137 |
| Exercise E · immutable tags | `docker push …:latest` fails with `tag invalid: The image tag 'latest' already exists … cannot be overwritten because the repository is immutable`; deleting the two `latest` lines fixes it; task definition accepts `repo@sha256:…` | documented ECR behaviour (every build has a different digest because `APP_VERSION` is baked in) |
| Challenge G · Logs Insights | JSON fields (`event`, `path`, `status`, `hostname`, `version`) are auto-discovered | app now logs one JSON object per request (verified) |
| Challenge H · lifecycle policy | two rules, preview shows nothing to expire yet | console flow as of 2026-11; JSON given for the CLI |
| Challenge J · `ValueFrom` secret | with `ecsTaskExecutionRole`: `ResourceInitializationError … ssm:GetParameters`; with their own execution role + `ssm:GetParameters`: page shows the masked launch code | expected error text from the ECS agent; the `aws/ssm` default key needs no extra KMS grant |
| Challenge K · ECS Exec | `enableExecuteCommand` + `--force-new-deployment`, task role with `ssmmessages:*Channel`, shell as user `mission`; `/tmp` file gone in the replacement | CloudShell should carry the Session Manager plugin; the guide gives the `yum install` fallback. Have one student try it before announcing it |
| Page rows (memory/CPU limits, readiness badge, `Running as`) | on Fargate the Memory row should read the task's 512 MiB; if the cgroup shows no limit the page says so and Exercise D still works | cgroup v1 and v2 paths both handled; verified in Docker (v2) and minikube |

**Where students get stuck**

| Symptom | Cause | Fix |
|---|---|---|
| Build fails at `docker build`: *Cannot connect to the Docker daemon* | **Privileged** flag not ticked | Edit project → Environment → Additional configuration → Privileged |
| Build fails: `REPO_NAME` empty / `docker push` to a wrong URI | env var missing or typo | Project → Environment → Environment variables |
| Task definition save fails on the health-check command | they pasted an older Python one-liner with commas | Use `CMD-SHELL, curl -fsS http://127.0.0.1:8080/health \|\| exit 1` (the image now has curl) |
| Part 9b page panel says `NoCredentialsError` after they attached the role | the role was attached to a new revision but the service still runs the old one, or they attached it as the *execution* role | Deployments tab: which revision is PRIMARY? Task role vs task execution role dropdowns |
| `AccessDeniedException` persists after the inline policy | policy on the wrong role, resource ARN typo (`parameter/` prefix, no leading slash after it), or they refreshed within 2 s | Compare the ARN in the error with the policy; wait 10 s |
| Challenge J: tasks never start, `ResourceInitializationError … ssm:GetParameters` | expected once; afterwards: still using `ecsTaskExecutionRole`, or `GetParameter` (singular) in the policy | Own execution role with `ssm:GetParameters` (plural) |
| Challenge K: `SessionManagerPlugin is not found` | CloudShell image without the plugin | `yum install` line in the guide |
| Challenge K: `execute command was not enabled when the task was run` | task predates `--enable-execute-command` | wait for the forced deployment, re-read `$TASK` |
| Tasks stop at once with `ResourceInitializationError … unable to pull secrets or registry auth` | execution role missing, or public IP turned off (no route to ECR from the default VPC without a public IP) | Select `ecsTaskExecutionRole`; **Public IP: Turned on** |
| Page does not load, tasks healthy | security group rule missing 8080, or they used the private IP | Check SG; use the task's *Public IP* |
| "Our tags are v2/v3 but the guide says…" | first build failed → numbering starts at 2 | Expected; the guide says so |

**Cost:** 2 Fargate tasks ≈ US$0.02/hour per student; 15 students ≈ US$0.30/hour. An ALB adds US$0.02/hour each. ECR storage is negligible. Make sure services are deleted at the end of the day.

**Cleanup students cannot do:** the CodeBuild service role, the task role, the task execution role (and anything they forget). `tools/cleanup-student.sh NN` removes every Lab 1, 2 and 4 resource for a student, in dependency order, including the ECS service/cluster, task definitions, ALB/target group, security groups, ECR repository (force, so immutable repositories go too), CodeBuild projects, log groups, Parameter Store parameters, buckets and roles.

---

## 8 · Lab 5 · EKS — shared cluster, per-student namespaces

Two Terraform modules, applied in order:

```bash
cd lab5-eks/terraform/cluster  && terraform init && terraform apply     # ~14 min: cluster, 2 × t3.large node group, add-ons, 15 access entries
cd ../students                  && terraform init && terraform apply     # ~1 min: namespaces, Role/RoleBinding, ClusterRole, ResourceQuota, LimitRange
```

What students get (RBAC and quotas verified by impersonation with `kubectl --as=participant-01 --as-group=participant-01`, plus a full run of the guide against the participant-01 namespace; the IAM-user → access-entry → group mapping was verified by inspecting the entries, **not** by logging in as a student, so have one participant run Part 1 before class):

- `kubectl get nodes` works (read-only ClusterRole); `kubectl get pods -n participant-02` and `-n kube-system` are **Forbidden**.
- Full rights in their own namespace: Deployments, Services (LoadBalancer type works; the public subnets carry the `kubernetes.io/role/elb` tag), ConfigMaps, Secrets, Jobs (`batch`), PodDisruptionBudgets (`policy`), HPA (metrics-server add-on installed), logs, exec, port-forward. The Role's API groups cover every object the revised lab uses.
- Quota: 12 pods, 2 load balancers, 2 CPU / 3 GiB requests. Scaling to 20 stops at 12 with `exceeded quota: lab-quota` events. LimitRange defaults 100m/128Mi requests, 250m/256Mi limits.
- Measured on EKS (2026-10-31): Deployment ready in ~15 s; Classic LB answering in ~90 s; rolling update ~20 s; `ImagePullBackOff` visible within 30 s; `rollout undo` ~15 s; HPA 2 → 6 replicas within ~60 s of load.
- Measured on a local minikube 1.37 cluster with the revised manifests and the revised image (2026-11-01; not yet re-run on EKS): ConfigMap file visible inside the Pod ~85 s after the edit, env var unchanged until `rollout restart`; `/ready/off` removes the Pod from Endpoints within 10 s with `RESTARTS 0`; `/hog` → `OOMKilled`, exit code 137, restart in place; selector typo → `ENDPOINTS <none>`; smoke-test Job `Complete` in 8 s; PDB `ALLOWED DISRUPTIONS 1`; `kubectl exec`/`port-forward`/`run busybox` DNS all fine; `rollout status` exits with `exceeded its progress deadline` 120 s into the `:v99` exercise; readiness-path typo → `0/1 Running`, `statuscode: 404`; HPA 2 → 6 about 105 s after the load generator starts and back to 2 about 2.5 min after it is deleted (60 s stabilization window); Secret → masked launch code on the page. The `kubectl run --rm -i` attach form was flaky with a mismatched client/server pair, so Challenge G uses run → `wait` → `logs` → delete instead.
- **The image matters.** The revised lab needs an image built from the revised `app.zip` (`/ready`, `/hog`, JSON logs, the ConfigMap file). An image from the previous revision answers 404 on `/ready`, so every Pod stays `0/1`. Rebuild the shared fallback `participant-01-mission-control` before class and tell anyone who kept an old Lab 4 image to rebuild.

**Capacity:** two `t3.large` nodes (2 vCPU / 8 GiB each) hold about 15 × 2 Pods comfortably (requests 100m each). If the whole class runs the HPA challenge at once (15 × 6 Pods × 100m = 9 vCPU requested) the scheduler will leave Pods `Pending`; raise `node_count` to 4 in `cluster/main.tf` for a large class, or run the challenge in two waves.

**CloudShell:** already allowed for students (`AWSCloudShellFullAccess` on the group). First launch takes ~60 s; `kubectl` (v1.36 at the time of writing) and the AWS CLI are pre-installed. If a student's CloudShell shows the wrong region, the region picker in the console controls it. Note for anyone verifying with a *federated* console session (GetFederationToken): such sessions have no access entry and get `You must be logged in to the server`; that is expected and does not affect IAM users.

**Where students get stuck**

| Symptom | Cause | Fix |
|---|---|---|
| `error: You must be logged in to the server (Unauthorized)` | they ran `update-kubeconfig` before the instructor applied the cluster module (no access entry yet), or wrong region | Re-run `aws eks update-kubeconfig --region us-west-2 --name cicd-lab5-eks` |
| Every command says Forbidden | namespace not set, or a typo in it | `kubectl config set-context --current --namespace participant-NN` |
| `EXTERNAL-IP <pending>` for minutes | LB being created; or quota `services.loadbalancers` exhausted (2) | Wait 2 min; `kubectl describe svc` → Events |
| Pods `Pending` with *Insufficient cpu* | nodes full (see Capacity) | Scale someone's HPA down; add nodes |
| `ImagePullBackOff` when it should work | image URI typo; or they deleted their Lab 4 repository | Use the shared `participant-01-mission-control:v3` image kept for this purpose (rebuilt from the revised app) |
| Pods `0/1 Running` right after Part 3, `statuscode: 404` in the events | an image from before this revision (no `/ready` endpoint) | rebuild from the current `app.zip`, or use the shared image |
| `kubectl rollout status` prints `exceeded its progress deadline` | `progressDeadlineSeconds: 120` in the manifest; expected in troubleshooting exercise 1 | `kubectl rollout undo` |
| `kubectl edit configmap` opens vi and they are stuck | CloudShell's default editor | `:q!` to escape; the guide gives the `kubectl patch` one-liner instead |
| Challenge A: HPA stays at 2 and `kubectl top` says `error: Metrics API not available` | metrics-server add-on not Ready | `kubectl -n kube-system get deploy metrics-server` as the instructor |
| Challenge H: `kubectl apply -f 01-deployment.yaml` fails with `secret "mission-secret" not found` on the Pods | they added the `secretRef` before creating the Secret | create it, Pods start by themselves |

**Cost:** the EKS control plane bills per hour, plus 2 × t3.large and one Classic LB per student namespace that creates a Service. Destroy the same day.

**Namespace cleanup:** the revised Part 9 deletes everything the lab creates (ConfigMap, Secret, Job, PDB, HPA, load generator, Service, Deployment); `kubectl get all,cm,secret,pdb,hpa,job -n participant-NN` should show only `kube-root-ca.crt`.

**Teardown (order matters):**

```bash
# 1. students must delete their Services first (each one owns an AWS load balancer), or do it for them:
for ns in $(kubectl get ns -l lab=cicd-lab5 -o name); do kubectl -n ${ns#namespace/} delete svc --all; done
# 2. then
terraform -chdir=lab5-eks/terraform/students destroy
terraform -chdir=lab5-eks/terraform/cluster  destroy      # ~10 min
```

If a load balancer is left behind, the cluster destroy fails on the security group / ENI; delete the orphaned Classic LB in EC2 → Load balancers and re-run.

---

## 9 · Teardown for the whole course

```bash
# Lab 5 (students' Services first, see §8), then the cluster
terraform -chdir=lab5-eks/terraform/students destroy
terraform -chdir=lab5-eks/terraform/cluster destroy
# Lab 3
terraform -chdir=lab3-broken-pipeline/terraform destroy

# Everything students created by hand in Labs 1–2 (including missions and level-ups: secrets, SNS topics,
# EventBridge rules, the pipeline-build project, both web servers) and Lab 4, for students 01..15
tools/cleanup-student.sh $(seq -w 1 15)
```

Then, once no pipelines remain in the account: delete the shared `codepipeline-us-west-2-*` artifact bucket and the `codepipeline-source-trail` trail (both created by the Lab 2 wizard).

---

## 10 · Regenerating screenshots or pages

- Lab guides are Markdown in `labs/`; `cd tools && npm install && npm run build` renders them into `docs/labN.html` with the site shell (hints and solutions become collapsible, GitHub alerts become callouts, screenshots zoom on click).
- Screenshots were taken with Playwright against a federated console session (`sts get-federation-token` → sign-in URL). The harness is not part of the repo; any retake just needs to land in `docs/images/` under the same file name.
- Diagrams are hand-written SVG in `docs/images/diagrams/`.

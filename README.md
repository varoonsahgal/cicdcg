# Pipeline Academy · AWS CI/CD and container labs

Five hands-on labs for a class of ~15 students sharing one AWS account, plus a GitHub-Pages handout that explains the concepts (why CI/CD, security, consistency, triage, containers).

| # | Lab | Students build | Planted failures | Guide |
|---|---|---|---|---|
| 1 | **CodeBuild** | A build project that compiles and tests a Java app and publishes a jar · then eight missions: failing test, env vars, multi-file artifact, a disabled test hiding a real bug, Secrets Manager injection, S3 build cache, EventBridge → SNS failure e-mails, Logs Insights | Java 11 vs 17 runtime mismatch; a failing unit test; a `@Ignore`d test that exposes a state bug; the build role refused `secretsmanager:GetSecretValue` | [labs/lab1-codebuild.md](labs/lab1-codebuild.md) |
| 2 | **CodePipeline + CodeDeploy** | EC2 + CodeDeploy + a two-stage pipeline that redeploys on every S3 upload · then a CodeBuild stage that lints hook scripts, checks appspec references and stamps the build number · a second server with OneAtATime rollouts and per-server page signing · CodeDeploy triggers → SNS | A start-script typo that takes the site down; the same with automatic rollback on; an appspec that names a missing script (caught by the Build stage); the typo again on a two-server fleet (50 % blast radius) | [labs/lab2-codepipeline-codedeploy.md](labs/lab2-codepipeline-codedeploy.md) |
| 3 | **The broken pipeline** (Terraform, one environment per student) | Nothing; they repair | Six bugs: YAML comment, build-role permission, tag filter, instance-role permission, script typo, missing artifact file | [labs/lab3-broken-pipeline.md](labs/lab3-broken-pipeline.md) |
| 4 | **ECR + CodeBuild + ECS Fargate** | A container image built by CodeBuild, pushed to ECR, run as an ECS service, rolled to a new version | Build role cannot log in to ECR; deploy of a non-existent tag (circuit breaker); a crashed container | [labs/lab4-ecs-ecr.md](labs/lab4-ecs-ecr.md) |
| 5 | **EKS** (one shared cluster, a namespace per student) | Deployments, Services, rolling updates and rollbacks with kubectl from CloudShell | Bad image tag (ImagePullBackOff); quota exceeded; RBAC denial when peeking at a neighbour | [labs/lab5-eks.md](labs/lab5-eks.md) |

Instructor material: [labs/instructor-guide.md](labs/instructor-guide.md) (permissions model, timings, answer keys, teardown).

## Layout

```
labs/                       the lab guides (Markdown; hidden hints/solutions via <details>)
docs/                       the handout site for GitHub Pages
  index.html                concepts handout (hand-written)
  lab1.html … lab5.html     built from labs/*.md by tools/build-site.mjs
  images/                   screenshots from the verification run + SVG diagrams
  downloads/                zips students download (copied by the build)
lab1-codebuild/             sample Java app (three tests, one @Ignored on purpose) + MessageUtil.zip
lab2-codepipeline-codedeploy/  sample web app + appspec + buildspec (Part 9) + hook scripts + SampleApp.zip
lab3-broken-pipeline/terraform/ one broken pipeline per student (see its README for the bug list)
lab4-ecs/                   Mission Control container app + buildspec + app.zip
lab5-eks/terraform/cluster  the shared EKS cluster  ·  lab5-eks/terraform/students  namespaces, RBAC, quotas
lab5-eks/manifests/         Deployment, Service, HPA, load generator
shared/terraform/student-access/  optional extra IAM policy for Labs 4–5 (not needed in the current account)
tools/                      build-site.mjs, cleanup-student.sh
```

## Publishing the handout

```bash
cd tools && npm install && npm run build      # renders labs/*.md → docs/labN.html
# GitHub Pages serves the docs/ folder of the main branch:
#   https://varoonsahgal.github.io/cicdcg/
```

## Running a class

See the instructor guide. Short version: `terraform apply` in `lab3-broken-pipeline/terraform` and `lab5-eks/terraform/{cluster,students}` before class; share the pipeline table; at the end `terraform destroy` both and run `tools/cleanup-student.sh $(seq -w 1 15)` for everything students created by hand.

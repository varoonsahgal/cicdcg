# Lab 2 · From a zip in S3 to a live web page — CodePipeline + CodeDeploy

> *In Lab 1 a robot built your code. In this lab a second robot puts it on a server, and a third robot decides when the first two should run. You will watch a deployment succeed, watch one take your site down, and then teach the robots to roll back on their own.*

| | |
|---|---|
| **Time** | Core path ≈ 70 min · Exercises ≈ 40 min · Level-ups (Parts 9–10) ≈ 50 min · Pager mission ≈ 15 min. Pick what fits; a full run is a half day. |
| **Difficulty** | Beginner → Intermediate. Do Lab 1 first. |
| **AWS services** | EC2, IAM, S3, CodeDeploy, CodePipeline, (EventBridge + CloudTrail created for you), Systems Manager · then CodeBuild inside the pipeline and SNS |
| **You will build** | One EC2 web server · a CodeDeploy application · a two-stage pipeline that redeploys automatically whenever you upload a new zip · then a Build stage that lints and stamps the bundle · then a second server and one-at-a-time rollouts · then deployment alerts by e-mail |
| **You will break & fix** | A deployment whose start script is wrong (and discover it takes the site *down*) · the same with automatic rollback on · a bundle that names a missing script (caught before any server sees it) · the same typo on a two-server fleet (half the blast radius) |
| **Handout** | **"Delivery vs deployment"**, **"Three robots, three identities"** and **"CodeDeploy lifecycle hooks"** in the [class handout](../docs/index.html) |

> [!IMPORTANT]
> **Your number.** Everywhere you see `NN`, type your own two digits (participant-07 → `07`). Fifteen people share this account: every name below must contain your number, including the **security group** and **IAM roles**.
>
> **Your region.** **US West (Oregon) · `us-west-2`** for everything except IAM (IAM is global and shows "Global" in the region picker; that is normal).

---

## Part 0 · The idea in five minutes

> [!NOTE]
> **How this lab is laid out.** Parts 1–7 are the core path: by the end of it an upload becomes a live web page. Part 8 breaks it four ways. Parts 9 and 10 are *level-ups* that turn the toy into something closer to a real fleet. Part 11 is a short mission. Stop wherever the clock says so; every part ends in a working state.

### CI gave you an artifact. Now what?

Lab 1 ended with a `.zip` in S3. A customer cannot use a zip in S3. **Continuous Delivery (CD)** is the practice of getting every good build to a place where it *could* be released, automatically and safely; **Continuous Deployment** goes one step further and releases it without a human in the loop. Both need two things CI does not provide:

1. Something that knows how to **put files on servers and restart things in the right order** → *AWS CodeDeploy*.
2. Something that **notices a new version and runs the steps in sequence** → *AWS CodePipeline*.

![Pipeline flow](../docs/images/diagrams/lab2-pipeline-flow.svg)

### Three robots, three identities

This is the part beginners find confusing, so here it is up front. Three different AWS services do work for you, and **each one needs its own IAM role** because each one touches different things:

| Robot | Role you will create | What it needs to do |
|---|---|---|
| **The EC2 instance** (really, the CodeDeploy *agent* running on it) | `participant-NN-ec2-codedeploy-role` | Download the deployment bundle from S3; talk to Systems Manager so you can open a shell without SSH keys |
| **CodeDeploy** (the service) | `participant-NN-codedeploy-service-role` | Find your instances by tag and tell the agent on them what to do |
| **CodePipeline** | created by the wizard: `AWSCodePipelineServiceRole-us-west-2-participant-NN-pipeline` | Read the source zip, copy artifacts into its own bucket, start CodeDeploy deployments |

![Roles map](../docs/images/diagrams/iam-roles-map.svg)

> [!TIP]
> When something fails in CD, the first question is always: **which robot was acting, and did *that* robot have permission?** Lab 3 is built almost entirely around this question.

### How CodeDeploy thinks: `appspec.yml` and lifecycle hooks

CodeDeploy does not know what your app is. You tell it two things in a file called **`appspec.yml`** at the root of the bundle:

- **`files:`** – which files to copy where on the server.
- **`hooks:`** – scripts to run at specific moments: `ApplicationStop` (stop the old version), `BeforeInstall` (install prerequisites), `AfterInstall`, `ApplicationStart` (start the new version), `ValidateService` (prove it works).

![CodeDeploy lifecycle](../docs/images/diagrams/codedeploy-hooks.svg)

| Word | Meaning in this lab |
|---|---|
| **Revision / bundle** | One versioned zip containing your app, `appspec.yml` and hook scripts |
| **Application** | A CodeDeploy container for deployments of one app |
| **Deployment group** | *Which* servers (chosen by **tag**) and *how* (all at once, one at a time, with/without rollback) |
| **CodeDeploy agent** | A small program on each server that polls CodeDeploy, downloads bundles and runs hooks. No agent, no deployment. |
| **Stage / action** | A pipeline is a sequence of stages (Source → Deploy); each stage holds one or more actions |
| **Artifact store** | An S3 bucket CodePipeline creates to pass files from one stage to the next |

---

## Part 1 · Meet the app

Download **[`SampleApp.zip`](../lab2-codepipeline-codedeploy/SampleApp.zip)** and keep it as it is: it is your first upload in Part 4. Unzip a copy and rename the folder to **`sample-app`**: that is your working copy, exactly as in Lab 1. (The same files are in the repository folder [`lab2-codepipeline-codedeploy/sample-app/`](../lab2-codepipeline-codedeploy/sample-app/).) Lab 1's CloudShell route works here too; just use `SampleApp.zip` and the Lab 2 bucket.

```
sample-app/
├── appspec.yml                      ← CodeDeploy's instructions
├── buildspec.yml                    ← CodeBuild's instructions – ignored until Part 9
├── index.html                       ← the web page (one line says "Version 1")
└── scripts/
    ├── install_dependencies.sh      ← BeforeInstall: dnf install -y httpd
    ├── start_server.sh              ← ApplicationStart: systemctl enable/start httpd
    ├── stop_server.sh               ← ApplicationStop: systemctl stop httpd || true
    └── stamp_server.sh              ← not wired up yet – Part 10
```

`appspec.yml`, annotated:

```yaml
version: 0.0
os: linux
files:
  - source: /index.html          # from the bundle…
    destination: /var/www/html/  # …to Apache's web root on the server
hooks:
  BeforeInstall:                 # runs BEFORE files are copied
    - location: scripts/install_dependencies.sh
      timeout: 300
      runas: root
  ApplicationStart:              # runs AFTER files are copied
    - location: scripts/start_server.sh
      timeout: 300
      runas: root
  ApplicationStop:               # runs FIRST – but against the PREVIOUS revision's scripts
    - location: scripts/stop_server.sh
      timeout: 300
      runas: root
```

> [!NOTE]
> **Why `|| true` in `stop_server.sh`?** On the very first deployment Apache is not installed yet, so `systemctl stop httpd` would fail and sink the whole deployment. A hook script's exit code *is* the verdict: non-zero = failed hook = failed deployment.

> [!WARNING]
> **Windows users: line endings.** The `.sh` files run on Linux. If an editor saves them with Windows line endings (CRLF), the hook fails on the server with `/bin/bash^M: bad interpreter`. Edit them in **VS Code** (check the bottom-right corner says **LF**, not CRLF; click it to switch) or in CloudShell, never in Word or WordPad. This matters most when you create a *new* script (Challenge C).

---

## Part 2 · Create the two IAM roles

Console → **IAM** → **Roles** → **Create role**.

### 2a · The EC2 instance role

1. Trusted entity type: **AWS service**. Use case: **EC2** → **Next**.

   ![Create role – trusted entity](../docs/images/lab2-iam-create-role-trusted-entity.png)

2. Permissions – search and tick **both**:
   - `AmazonEC2RoleforAWSCodeDeploy` (lets the agent read bundles from S3)
   - `AmazonSSMManagedInstanceCore` (lets you open a browser shell to the server later – no SSH key needed)
3. **Next** → Role name: **`participant-NN-ec2-codedeploy-role`** → **Create role**.

![EC2 role permissions](../docs/images/lab2-iam-ec2-role-policies.png)

### 2b · The CodeDeploy service role

1. **Create role** → **AWS service** → Use case: scroll the dropdown to **CodeDeploy** → pick **CodeDeploy** (the plain EC2/on-premises one, not ECS or Lambda) → **Next**.
2. The policy `AWSCodeDeployRole` is pre-selected → **Next**.
3. Role name: **`participant-NN-codedeploy-service-role`** → **Create role**.

![CodeDeploy service role](../docs/images/lab2-iam-codedeploy-service-role.png)

> ✅ **Checkpoint** — IAM → Roles → search `participant-NN` shows both roles. The EC2 one has an *Instance profile ARN* on its summary card (that is what lets EC2 use it).

---

## Part 3 · Launch the web server (with the CodeDeploy agent pre-installed)

Console → **EC2** → **Instances** → **Launch instances**.

1. **Name:** `participant-NN-webserver`. *(This exact tag is how CodeDeploy will find the server. Typos here are the #1 cause of "no instances found".)*

   ![Launch – name](../docs/images/lab2-ec2-launch-top.png)

2. **AMI:** Amazon Linux 2023 (the default Quick Start choice). **Instance type:** `t3.micro`.
3. **Key pair:** choose **Proceed without a key pair**. We will never SSH; Systems Manager gives us a shell if we need one.
4. **Network settings** → **Edit**:
   - Auto-assign public IP: **Enable**
   - Firewall: **Create security group** · name **`participant-NN-webserver-sg`** · description anything
   - Rules: **untick** *Allow SSH*; **tick** *Allow HTTP traffic from the internet*.

   ![Launch – network settings (shown before editing; change them as listed above)](../docs/images/lab2-ec2-launch-network.png)

5. Expand **Advanced details**:
   - **IAM instance profile:** `participant-NN-ec2-codedeploy-role`

   ![Launch – IAM profile](../docs/images/lab2-ec2-launch-iam-profile.png)

   - Scroll to the bottom → **User data** → paste this script exactly. It runs once at first boot and installs the CodeDeploy agent:

   ```bash
   #!/bin/bash
   dnf install -y ruby wget
   cd /home/ec2-user
   wget https://aws-codedeploy-us-west-2.s3.us-west-2.amazonaws.com/latest/install
   chmod +x ./install
   ./install auto
   systemctl enable codedeploy-agent
   systemctl start codedeploy-agent
   ```

   ![Launch – user data](../docs/images/lab2-ec2-launch-user-data.png)

6. **Launch instance**. Open the instance; wait for *Instance state: Running* and *Status checks: 2/2 passed* (2–3 minutes).

![Instance details](../docs/images/lab2-ec2-instance-details.png)

> ✅ **Checkpoint** — The instance summary shows your **Public IPv4 address** (write it down) and *IAM role: participant-NN-ec2-codedeploy-role*. Browsing to the IP now gives nothing: Apache is not installed yet. CodeDeploy will install it.

<details>
<summary>🔍 Optional: prove the agent is running (Session Manager)</summary>

Instance → **Connect** → **Session Manager** tab → **Connect**. A browser terminal opens on the server. Run:

```bash
sudo systemctl status codedeploy-agent
sudo tail -n 5 /var/log/aws/codedeploy-agent/codedeploy-agent.log
```

`active (running)` means the user-data script worked. If Session Manager says the instance is not connected, wait a minute: the SSM agent needs the instance role and a little time.
</details>

---

## Part 4 · The source bucket (versioning is not optional)

1. **S3** → **Create bucket** → name **`cicd-lab2-participant-NN`**, region Oregon.
2. Scroll to **Bucket Versioning** → **Enable**. *(CodePipeline refuses an S3 source without versioning – every pipeline run is pinned to one exact object version, which is what makes rollbacks possible.)*
3. Keep *Block all public access* on. **Create bucket**.
4. Open the bucket → **Upload** → `SampleApp.zip` (at the root, not in a folder) → **Upload**.

> ✅ **Checkpoint** — Bucket → **Properties** → *Bucket Versioning: Enabled*. Objects tab shows `SampleApp.zip`.

---

## Part 5 · CodeDeploy: application + deployment group

### 5a · Application

1. Console → **CodeDeploy** → **Applications** → **Create application**.
2. Application name **`participant-NN-webapp`** · Compute platform **EC2/On-premises** → **Create application**.

![Create application](../docs/images/lab2-codedeploy-create-application.png)

### 5b · Deployment group

1. On the application page → **Create deployment group**.

   ![Create deployment group – top](../docs/images/lab2-codedeploy-create-deployment-group-top.png)

2. Deployment group name **`participant-NN-webapp-group`**.
3. Service role: pick **`participant-NN-codedeploy-service-role`**.
4. Deployment type: **In-place**.
5. **Environment configuration** → tick **Amazon EC2 instances** → Tag group 1: Key **`Name`**, Value **`participant-NN-webserver`**. The line under the checkbox should now say **1 unique matched instance**. If it says 0, fix the tag or the value before going on.

   ![Deployment group – environment](../docs/images/lab2-codedeploy-dg-matched-instance.png)

6. **Agent configuration with AWS Systems Manager** → **Never** (we installed the agent ourselves).
7. Deployment settings: **CodeDeployDefault.AllAtOnce** (we have one server).
8. **Load balancer** → **untick Enable load balancing**. (It is ticked by default. With one server and no load balancer, leaving it on makes the wizard demand one.)

   ![Deployment group – load balancer](../docs/images/lab2-codedeploy-dg-loadbalancer.png)

9. Expand **Advanced – optional** → **Rollbacks**: leave **Disable rollbacks** ticked *for now*. You will turn rollbacks on in Exercise B and feel the difference.

   ![Deployment group – rollbacks](../docs/images/lab2-codedeploy-dg-rollbacks.png)

10. **Create deployment group**.

![Deployment group created](../docs/images/lab2-codedeploy-deployment-group.png)

> ✅ **Checkpoint** — The group page shows *Environment configuration: Amazon EC2 instances · Name = participant-NN-webserver* and *Rollback enabled: False*.

---

## Part 6 · The pipeline

Console → **CodePipeline** → **Pipelines** → **Create pipeline**.

1. **Step 1 – Creation option:** **Build custom pipeline** → **Next**.

   ![Wizard step 1](../docs/images/lab2-pipeline-wizard-step1-options.png)

2. **Step 2 – Pipeline settings:** name **`participant-NN-pipeline`**. Execution mode: leave the default. Service role: **New service role** (accept the generated name). → **Next**.

   ![Wizard step 2](../docs/images/lab2-pipeline-wizard-step2-settings.png)

3. **Step 3 – Source:** provider **Amazon S3** · Bucket **`cicd-lab2-participant-NN`** · S3 object key **`SampleApp.zip`** · keep **Create EventBridge rule to automatically detect source changes** ticked → **Next**.

   ![Wizard step 3](../docs/images/lab2-pipeline-wizard-step3-source.png)

   > [!NOTE]
   > That checkbox is what makes this *continuous*. Behind the scenes the wizard creates a CloudTrail trail that records writes to your object and an EventBridge rule that starts the pipeline when one happens. You did not have to build any of that.

4. **Step 4 – Build:** click **Skip build stage** and confirm **Skip**. (There is nothing to compile yet. Part 9 adds a Build stage that does something more interesting than compiling.)

   ![Wizard step 4](../docs/images/lab2-pipeline-wizard-step4-build-skip.png)

   ![Confirm skipping the build stage](../docs/images/lab2-pipeline-wizard-skip-confirm.png)

5. **Step 5 – Test:** **Skip test stage**.
6. **Step 6 – Deploy:** provider **AWS CodeDeploy** · Region **US West (Oregon)** · Input artifact **SourceArtifact** · Application name **`participant-NN-webapp`** · Deployment group **`participant-NN-webapp-group`** → **Next**.

   ![Wizard step 6](../docs/images/lab2-pipeline-wizard-step6-deploy.png)

7. **Step 7 – Review** → **Create pipeline**.

   ![Wizard step 7](../docs/images/lab2-pipeline-wizard-step7-review.png)

The pipeline starts immediately. Watch the Source card go green, then the Deploy card turn blue (*In progress*) and finally green.

![Pipeline running](../docs/images/lab2-pipeline-created-running.png)

![Pipeline succeeded](../docs/images/lab2-pipeline-succeeded.png)

> ✅ **Checkpoint** — Both stages green. Now open **`http://<your instance public IP>`** in a new tab.

![Version 1 live](../docs/images/lab2-webpage-v1.png)

### What just happened (click along)

Click **AWS CodeDeploy** in the Deploy card, then the deployment ID. The page lists every lifecycle event on your instance with its duration. Expand the instance row.

![Deployment succeeded](../docs/images/lab2-codedeploy-deployment-succeeded.png)

`ApplicationStop → DownloadBundle → BeforeInstall → Install → AfterInstall → ApplicationStart → ValidateService` – and in `BeforeInstall` your script installed Apache. That is why the page now exists.

---

## Part 7 · Ship version 2 (the "continuous" part)

1. Edit `index.html`: change `Version 1` to **`Version 2`** (change a colour too if you like).
2. Re-zip **from inside `sample-app/`** so `appspec.yml` stays at the root:
   ```bash
   zip -r SampleApp.zip appspec.yml buildspec.yml index.html scripts/
   ```
3. S3 → `cicd-lab2-participant-NN` → **Upload** the new `SampleApp.zip`.
4. Go straight to the pipeline page. **Do not click Release change.** Within about a minute a new execution starts on its own. (Nothing after two minutes? Check you uploaded to the bucket root with the exact name `SampleApp.zip`, then click **Release change** and tell your instructor.)
5. When it is green, refresh your web page.

> [!NOTE]
> **Version numbers.** From here on, each upload bumps the version on the page so you can always tell what is live. The guide assumes you do every part in order: Exercise A = 3, B = 4, Part 9 = 5, Part 10 = 6, Exercise F = 7, Part 11 = 8. If you skip a part, just keep counting up; what matters is that every upload shows a number you have not seen yet. (The screenshots come from a test run with its own numbering, so their version numbers will not match yours.)

![Version 2 live](../docs/images/lab2-webpage-v2.png)

Now look at two places that explain *how* this worked:

- S3 → bucket → **Show versions** toggle. Every upload became a new version with its own ID; the pipeline's Source card shows which version it deployed.

  ![Object versions](../docs/images/lab2-s3-object-versions.png)

- Pipeline → **Executions / History**. The *Trigger* column says **CloudWatchEvent** (EventBridge) – nobody clicked anything.

  ![Execution history](../docs/images/lab2-pipeline-execution-history.png)

> [!TIP]
> **This is the whole point of CD.** Releasing stopped being an event and became a side effect of uploading. In a real team the "upload" is a `git push`, but everything downstream is identical.

---

## Part 8 · Exercises

### Exercise A · Break the deployment, read the diagnostics, discover the blast radius

**Setup:** in `scripts/start_server.sh` change `systemctl start httpd` to `systemctl start htpd` (drop one *t*). Also bump the page to `Version 3` so you can tell what is live. Re-zip, upload, wait.

**Questions to answer before opening the hints:**

1. Which lifecycle event failed, and what did the script print?
2. Open your website now. What do you see, and *why*?

![Deploy failed in pipeline](../docs/images/lab2-pipeline-deploy-failed.png)

<details>
<summary>💡 Hint 1 — where the message is</summary>

Pipeline → Deploy card → **View details** / the CodeDeploy link → the deployment page opens with a **What failed** panel at the top. It names the lifecycle event, the script, the exit code, and shows the script's last output lines.
</details>

<details>
<summary>💡 Hint 2 — the site</summary>

Think about the *order* of hooks. Which ones ran successfully before the failure, and what did the first one do?
</details>

<details>
<summary>✅ Solution & explanation</summary>

![What failed](../docs/images/lab2-codedeploy-deployment-failed.png)

- Event **ApplicationStart**, error **ScriptFailed**, exit code 5, stderr: `Failed to start htpd.service: Unit htpd.service not found.`
- **Your site is down** (the browser reports *connection refused*; nothing is listening on port 80). Sequence: `ApplicationStop` ran first and **stopped Apache**; `Install` copied the Version-3 page; `ApplicationStart` failed, so nothing started Apache again. A failed in-place deployment without rollback leaves the server in whatever half-state it reached. The lifecycle view makes the order explicit:

  ![Lifecycle events of the failed deployment](../docs/images/lab2-codedeploy-deployment-failed-events.png)

Fix the typo, re-zip, upload. The next deployment succeeds and the site returns – showing **Version 3**.

**Lesson:** "the deployment failed" is rarely the worst news; "the deployment failed *and the old version is gone*" is. That is what rollbacks and (later) blue/green deployments exist to prevent.
</details>

### Exercise B · Turn on automatic rollback, then break it again

1. CodeDeploy → Applications → `participant-NN-webapp` → Deployment groups → your group → **Edit** → **Advanced** → **Rollbacks** → untick *Disable rollbacks*, tick **Roll back when a deployment fails** → **Save changes**.
2. Re-introduce the `htpd` typo and bump the page to `Version 4`. Zip, upload, wait.
3. Watch the pipeline **and** the CodeDeploy *Deployments* list. Then open the website.

<details>
<summary>💡 Hint</summary>

CodeDeploy → **Deployments** shows *two* deployments created seconds apart: your failed one, and a second one whose *Initiating event* is **CodeDeploy rollback**. Open the second one and read its description.
</details>

<details>
<summary>✅ Solution & explanation</summary>

![Deployments list with rollback](../docs/images/lab2-codedeploy-deployments-list-rollback.png)

![Rollback deployment](../docs/images/lab2-codedeploy-rollback-deployment.png)

The failed deployment triggered an automatic second deployment of the **last known good revision** (the Version-3 zip, pulled from the artifact store by its exact S3 version ID). Your site is up and shows **Version 3**, not 4. The pipeline execution is still marked *Failed* – correct, because the thing you asked for did not ship – but your users never noticed.

Fix the typo, upload once more, and Version 4 goes live cleanly.

**Lesson:** rollback is not "undo"; it is a *forward* deployment of an older artifact. It only works because every artifact is immutable and versioned. Delete old versions and you delete your safety net.
</details>

### Challenge C · Add a real smoke test (ValidateService)

Right now CodeDeploy calls a deployment "successful" as soon as `start_server.sh` exits 0. Apache could be running and serving a blank page. Make the deployment **fail unless the live page actually contains the word `Version`**.

<details>
<summary>💡 Hint 1</summary>

There is a lifecycle hook that runs *after* `ApplicationStart`: `ValidateService`. It takes a script just like the others.
</details>

<details>
<summary>💡 Hint 2</summary>

Inside the script, call the server on `localhost` with `curl -sf` and `grep` for the word. Give Apache a second or two to come up first. Remember that a non-zero exit code is how a hook reports failure.
</details>

<details>
<summary>✅ Solution</summary>

`scripts/validate_service.sh`:

```bash
#!/bin/bash
set -e
sleep 2
curl -sf http://localhost/ | grep -q "Version"
echo "Smoke test passed: page contains 'Version'"
```

Add to `appspec.yml` under `hooks:`:

```yaml
  ValidateService:
    - location: scripts/validate_service.sh
      timeout: 60
      runas: root
```

Zip (the `scripts/` folder is already in the zip command, so the new script goes along; on macOS/Linux also run `chmod +x scripts/*.sh` first; on Windows make sure the new file is saved with **LF** line endings), upload, and watch the `ValidateService` event now take ~2 seconds instead of 0.

![ValidateService in the lifecycle events](../docs/images/lab2-codedeploy-validate-service-events.png)

To prove it bites, temporarily change `grep -q "Version"` to `grep -q "Banana"` – the deployment fails at ValidateService and, with rollback on, the previous version comes back.

**Lesson:** a deployment is not done when the process starts; it is done when the *behaviour* is verified. In mature pipelines ValidateService is where health checks, canary requests and synthetic transactions live.
</details>

### Challenge D · Put a human in the loop (Continuous *Delivery*)

Some teams want every build ready to ship but a person to press the button. Add a **manual approval** between Source and Deploy.

<details>
<summary>💡 Hint</summary>

Pipeline → **Edit** → **+ Add stage** after Source → name it `Approve` → **+ Add action group** → Action provider **Manual approval**. Save, then **Release change**.
</details>

<details>
<summary>✅ Solution</summary>

After saving, release a change: the pipeline runs Source, then pauses at `Approve` with a **Review** button. Click it, type a comment, **Approve** → Deploy runs. **Reject** stops the execution.

![Waiting for approval](../docs/images/lab2-pipeline-approval-waiting.png)

**Lesson:** the difference between Continuous *Delivery* and Continuous *Deployment* is exactly one stage. Everything before the approval is identical, which is why teams can move from one to the other without re-architecting.

**Before you go on:** while the `Approve` stage exists, *every* upload stops and waits for you, including the ones in Parts 9–11. Either delete the stage (Edit → the stage's **Delete** button → Save) or remember to click **Review → Approve** each time.
</details>

### Optional · Look at the agent's own diary

Instance → **Connect** → **Session Manager**, then:

```bash
sudo tail -n 40 /var/log/aws/codedeploy-agent/codedeploy-agent.log
sudo ls /opt/codedeploy-agent/deployment-root/
```

Every deployment ID you saw in the console has a folder here with the downloaded bundle and each hook's log. When the console's "What failed" panel is not enough, this is the next layer down.

---

## Part 9 · Level up: a Build stage in the middle

Exercise A proved something uncomfortable: a broken bundle sails straight through Source and only fails *on the server*, taking the site with it. Real pipelines put a gate in between. You will add one now, and it is the same service you met in Lab 1.

![Build stage](../docs/images/diagrams/lab2-build-stage.svg)

### 9a · Read the recipe

Open `buildspec.yml` in the sample app. It does three small things to the bundle (shown here trimmed: the real file also prints a `1/3 … 3/3` heading before each step):

```yaml
version: 0.2
phases:
  build:
    commands:
      - for f in scripts/*.sh; do bash -n "$f" && echo "     ok  $f"; done        # 1 syntax-check every hook script
      - for s in $(grep -oE 'scripts/[A-Za-z0-9_]+\.sh' appspec.yml); do test -f "$s" || { echo "     MISSING $s"; exit 1; }; done   # 2 every script appspec names must exist
      - 'sed -i "s|</body>|<p class=\"stamp\">Build #$CODEBUILD_BUILD_NUMBER · built $(date -u +%Y-%m-%dT%H:%M:%SZ)</p></body>|" index.html'   # 3 stamp the page
artifacts:
  files:
    - '**/*'                                                                      # the whole bundle goes on to Deploy
```

`bash -n` parses a script without running it. The second line is the one that would have caught a famous CodeDeploy failure (*ScriptMissing*). The third is Lab 1's "self-describing artifact" idea applied to a web page.

> [!NOTE]
> Why is the third command wrapped in single quotes? Because of the ` #` in `Build #`. In YAML a space followed by `#` starts a comment, and the command would be cut off there. We found that out the hard way while building this lab. Lab 3 makes you find it yourself.

### 9b · Create the project from inside the pipeline

1. Pipeline → **Edit** → directly after *Source* click **+ Add stage** → Stage name **`Build`** → **Add stage**. (If you kept Challenge D's `Approve` stage, put Build *before* it, so you approve a bundle that has already passed the checks.)
2. In the new stage → **+ Add action group**:
   - Action name **`Build`** · Action provider **AWS CodeBuild** · Region Oregon · Input artifacts **SourceArtifact**.
   - Project name → **Create project**. A CodeBuild window opens (if nothing appears, allow pop-ups for the console and click again):
     - Project name **`participant-NN-pipeline-build`**
     - Environment: Managed image · Amazon Linux · Standard · the newest `aws/codebuild/amazonlinux-x86_64-standard:…` image · **New service role**
     - Buildspec: **Use a buildspec file** (blank name → `buildspec.yml`)
     - Logs: CloudWatch logs on → **Continue to CodePipeline**
   - Back in the action: Output artifacts **`BuildArtifact`** → **Done**.
3. Now the important part: open the *Deploy* stage → **Edit stage** → pencil on the Deploy action → **Input artifacts**: remove *SourceArtifact*, choose **BuildArtifact** → **Done** → **Done**.
4. **Save** (top-right) → confirm.

> [!IMPORTANT]
> Step 3 is where most people slip. If Deploy still reads *SourceArtifact*, the build runs, stamps the page, and the server receives the **unstamped** original. The pipeline is green and lying. Always check which artifact each stage consumes.

### 9c · Ship through the gate

1. Bump `index.html` to **Version 5**. Re-zip (make sure `buildspec.yml` is in the zip!) and upload.
2. Watch three cards go green in turn: Source → Build → Deploy.

   ![Three stages](../docs/images/lab2-pipeline-three-stages.png)

3. Refresh the site. Under the version pill a grey line reads **Build #1 · built 2026-…** (the number is this project's own build counter; it climbs with every execution).

   ![Stamped page](../docs/images/lab2-webpage-stamped.png)

4. Click the build link in the Build card and read its log: one `ok` line per hook script, then the stamp.

   ![Build stage log](../docs/images/lab2-build-stage-succeeded-log.png)

> ✅ **Checkpoint** — Three green stages; the page shows Version 5 and a build stamp; the Deploy action's input artifact is *BuildArtifact*.

> [!TIP]
> **Robot number four.** The pipeline now has a CodeBuild project with its *own* service role (the wizard created `codebuild-participant-NN-pipeline-build-service-role`). It can read and write the pipeline's artifact bucket and write logs, nothing else. Four robots, four identities, same rule: each one gets what its job needs.

### 🔧 Exercise E · Prove the gate works

In `appspec.yml` change `scripts/start_server.sh` to **`scripts/start_servr.sh`** (drop the *e*). Leave everything else alone. Zip, upload.

**Predict before you look:** how far does this execution get? What does the website show while it is red?

<details>
<summary>💡 Hint</summary>

Compare with Exercise A, where the server itself discovered the problem. This time something *before* the server reads `appspec.yml`.
</details>

<details>
<summary>✅ Solution &amp; explanation</summary>

![Build gate failed](../docs/images/lab2-pipeline-build-gate-failed.png)

The **Build** stage goes red in about thirty seconds; the log ends with `MISSING scripts/start_servr.sh`. Deploy never ran. Your website still shows Version 5, stamped, untouched. Nothing happened to any server.

![The MISSING line](../docs/images/lab2-build-gate-failed-log.png)

That is what people mean by **"shift left"**: the same class of mistake that caused an outage in Exercise A now costs one red card and thirty seconds. Fix the file name, upload, green.

**But notice the limit.** Re-read the three checks. Would any of them catch `systemctl start htpd`? No: `htpd` is a perfectly well-formed word in a perfectly well-formed script. Syntax checks catch *malformed*; only a **behavioural** check (Challenge C's `ValidateService`, or real tests) catches *wrong*. Gates stack; none of them is complete.
</details>

---

## Part 10 · Level up: two servers, one at a time

One server is a demo. Two servers are a fleet, and a fleet has a question a single server never asks: **in what order, and how many at once?**

![Fleet rollout](../docs/images/diagrams/lab2-fleet-rollout.svg)

### 10a · A second, identical server

1. EC2 → **Launch instances** exactly as in Part 3, with one difference in step 4: under *Firewall*, choose **Select existing security group** → `participant-NN-webserver-sg`. Everything else identical, including the **Name `participant-NN-webserver`** (yes, the same name: that tag is how CodeDeploy finds it), the IAM instance profile and the **user data** script (without it there is no CodeDeploy agent, and without the agent nothing can be deployed to this server).
2. Wait for *2/2 checks passed*. Write down its public IP as **server 2**. Your first server is **server 1**.

   ![Two instances](../docs/images/lab2-ec2-two-instances.png)

3. CodeDeploy → your application → your deployment group → **Edit**. *Environment configuration* now says **2 unique matched instances** without you changing anything: the tag did the work.

   ![Two matched instances](../docs/images/lab2-codedeploy-dg-two-instances.png)

4. Scroll to **Deployment settings** → change the deployment configuration to **`CodeDeployDefault.OneAtATime`** → **Save changes**.
5. Browse to server 2's IP: *nothing*, not even an error page. Matching the tag does not deploy anything by itself; server 2 gets the app at the **next** deployment, which you are about to trigger.

### 10b · Make each server sign its page

`scripts/stamp_server.sh` is already in the bundle:

```bash
sed -i "s|</body>|<p class=\"stamp\">Served by $(hostname) · deployment $DEPLOYMENT_ID</p></body>|" /var/www/html/index.html
```

CodeDeploy sets `DEPLOYMENT_ID`, `DEPLOYMENT_GROUP_NAME`, `APPLICATION_NAME` and `LIFECYCLE_EVENT` as environment variables for every hook. Wire the script in **after** the files are copied, and slow the rollout down enough to watch. Add these under `hooks:` in `appspec.yml` (if `ValidateService` is already there from Challenge C, do not add it twice; just change the sleep):

```yaml
  AfterInstall:
    - location: scripts/stamp_server.sh
      timeout: 60
      runas: root
  ValidateService:
    - location: scripts/validate_service.sh   # from Challenge C; change its sleep 2 to sleep 20
      timeout: 60
      runas: root
```

(If you skipped Challenge C, create `scripts/validate_service.sh` from its solution now; the 20-second pause gives you time to see the rollout mid-flight.)

### 10c · Watch a rolling deployment

1. Bump to **Version 6**, zip, upload.
2. Open **both** IPs in two browser tabs and keep refreshing while the pipeline runs. CodeDeploy picks one server to go first (it may be either). For roughly half a minute that server shows **Version 6** while the other one still shows what it had before: **Version 5** on server 1, *nothing* on server 2. That is a rolling deployment: at no point were both servers being changed. (If you refresh at exactly the wrong second you may catch server 1 refusing the connection: that is the `ApplicationStop → ApplicationStart` gap of an in-place deployment on *that one server*. With a load balancer in front, CodeDeploy would pull the server out of rotation first; that is the "Enable load balancing" box you unticked in Part 5.)
3. Open the deployment in CodeDeploy. The instance list fills in **one row at a time**: one instance *In progress* while the other is *Pending*, then one *Succeeded* while the other starts, then both green.

   ![One at a time, mid-flight](../docs/images/lab2-codedeploy-oneatatime-inprogress.png)

4. When it is green, compare the two pages: same version, same deployment ID, **different `Served by ip-172-31-…`**. Two servers, one deployment, each one signed.

   ![Server 2's page](../docs/images/lab2-webpage-stamped-server2.png)

> ✅ **Checkpoint** — Both servers show Version 6 with different hostnames and the same deployment ID; the deployment's instance list shows two instances, finished at different times.

### 🔧 Exercise F · Blast radius

Rollback is on (Exercise B). Put the `htpd` typo back into `start_server.sh`, bump to **Version 7**, upload. Keep both tabs open.

**Predict:** which server goes down? Which stays up? Where does each one end up?

<details>
<summary>💡 Hint</summary>

OneAtATime means CodeDeploy will not *start* on the second server until the first one has *succeeded*. Think about what happens to the second server if the first one never does.
</details>

<details>
<summary>✅ Solution &amp; explanation</summary>

![Failed on one, skipped on the other](../docs/images/lab2-codedeploy-oneatatime-failed.png)

- The server CodeDeploy picked first: `ApplicationStop` stopped Apache, `ApplicationStart` failed → **down**, briefly.
- The other server: status **Skipped**, every lifecycle event *Skipped*. CodeDeploy never touched it. It served Version 6 throughout. The deployment's error code is `HEALTH_CONSTRAINTS`: with OneAtATime the rule is "all but one instance must stay healthy", and after the first server failed that rule could not be met, so CodeDeploy stopped.
- The automatic rollback redeployed Version 6 to the failed server. Both servers are back on Version 6; the pipeline is red.

Blast radius: **50 %**, for about a minute. In Exercise A, with one server, it was 100 % and stayed that way until you fixed it. With `AllAtOnce` on two servers it would have been 100 % too.

**The lesson:** a deployment configuration is a *blast-radius dial*. `OneAtATime` and `HalfAtATime` trade speed for safety; custom configurations let you say "never below 75 % healthy". Put a load balancer in front (Lab 4 does) and the user never notices the server that is mid-deployment: that is a zero-downtime deploy, and you now own every piece of it except the load balancer.

Fix the typo, upload, and Version 7 rolls out cleanly, one server at a time.
</details>

---

## Part 11 · Mission: 📟 Pager — deployment alerts by e-mail

Nobody watches a deployment list either. CodeDeploy has notifications built in; they publish to an SNS topic.

1. If you did Lab 1's Mission G, you already have topic **`participant-NN-alerts`** with your e-mail confirmed. Otherwise: SNS → Create topic (Standard, that name) → Create subscription (Email) → confirm the e-mail.
2. CodeDeploy → application → deployment group → **Edit** → expand **Advanced – optional** → **Triggers** → **Create trigger**:
   - Name **`participant-NN-deploy-alerts`**
   - Events: tick **Deployment fails** and **Deployment rolls back** (add *Deployment succeeds* if you like noise)
   - Amazon SNS topic: `participant-NN-alerts`
   - **Create trigger** → **Save changes**.

   ![Triggers](../docs/images/lab2-codedeploy-dg-triggers.png)

3. Put the `htpd` typo back one last time, bump to **Version 8**, upload. Within a minute you get **two** e-mails: one *FAILURE*, one *ROLLBACK*. Fix, upload, done.

<details>
<summary>💡 No e-mail?</summary>

Subscription confirmed? Topic in **us-west-2**? Then look at the *second robot*: CodeDeploy publishes using its **service role**. `AWSCodeDeployRole` already includes `sns:Publish`, so this one works out of the box. Compare Lab 1, where the CodeBuild robot had to be granted a new verb before it could read a secret.
</details>

<details>
<summary>🎁 Bonus: approvals that find the approver</summary>

If you added the manual approval stage (Challenge D): Edit → the *Approve* action → **SNS topic ARN** → pick `participant-NN-alerts` → Save. The next execution e-mails the approver a link the moment it pauses. Continuous *Delivery* with a doorbell.
</details>

---

## Part 12 · Clean up

Do these **in this order** (some depend on others):

1. **CodePipeline** → select `participant-NN-pipeline` → **Delete pipeline**.
2. **CodeDeploy** → Applications → `participant-NN-webapp` → **Delete application** (deletes the deployment group and its triggers too).
3. **CodeBuild** → Build projects → `participant-NN-pipeline-build` → **Delete build project** (Part 9).
4. **EC2** → Instances → select **every** instance named `participant-NN-webserver` (two if you did Part 10) → **Instance state → Terminate**. After they show *Terminated*, **Security Groups** → delete `participant-NN-webserver-sg`.
5. **S3** → empty and delete `cicd-lab2-participant-NN`. (The pipeline's own `codepipeline-us-west-2-…` artifact bucket is shared by every pipeline in the account; leave it.)
6. **SNS** → Topics → delete `participant-NN-alerts` if you created one. **EventBridge** → Rules → delete `participant-NN-build-failed` if it is still there from Lab 1.
7. IAM roles stay; the instructor removes them.

---

## Part 13 · What you learned

- **CI** produces artifacts; **CD** moves them to servers in a controlled, repeatable, observable way.
- **Three robots, three roles.** Most CD failures are one of them lacking permission or looking in the wrong place.
- **Tags are how CodeDeploy finds servers.** One wrong character = "no instances found".
- The **CodeDeploy agent** must be installed and running; user data is one way to guarantee that at launch.
- **appspec.yml** + lifecycle hooks turn "copy files" into "stop, install, copy, start, verify" – and a failed hook can leave the old version stopped.
- **Versioned, immutable artifacts** are what make automatic rollback possible.
- **Event-driven triggers** (upload → EventBridge → pipeline) are what make it *continuous*.
- A **Build stage** is a gate: cheap checks fail the bundle before any server sees it ("shift left"). Syntax gates catch *malformed*; only behavioural checks catch *wrong*.
- A **deployment configuration** is a blast-radius dial. OneAtATime on two servers turned a full outage into a half outage that healed itself.
- Hooks get **environment variables** (`DEPLOYMENT_ID`, …); use them to make every server sign its work.
- **Notifications** (CodeDeploy triggers, EventBridge rules, approval topics) are how a pipeline talks to humans.

### Quiz yourself

<details>
<summary>1. The deployment group says "0 unique matched instances". List three possible causes.</summary>

(a) Tag key/value typo (e.g. `participant-7-webserver`), (b) the instance is in another region, (c) the instance was terminated or has not finished launching. (Bonus: the group is filtering on a tag the instance does not have at all.)
</details>

<details>
<summary>2. A deployment fails at DownloadBundle. Which of the three robots is the problem, and what is the usual fix?</summary>

The EC2 instance's agent: its *instance role* cannot read S3. Attach `AmazonEC2RoleforAWSCodeDeploy` (or an S3 read policy) to the instance role. Lab 3 makes you find this one yourself.
</details>

<details>
<summary>3. Why must the source bucket have versioning enabled?</summary>

CodePipeline pins each execution to an exact object version so that reruns, retries and rollbacks deploy *the same bytes*, even if someone uploads a new zip meanwhile.
</details>

<details>
<summary>4. Rollback is enabled and a deployment fails. Is the pipeline execution green or red? Is the site up?</summary>

Red (the requested revision did not ship) and up (CodeDeploy redeployed the last good revision). Both facts are correct and useful.
</details>

<details>
<summary>5. Which robot? Match each message to CodePipeline, CodeBuild, CodeDeploy (the service) or the EC2 agent: (a) <code>MISSING scripts/start_servr.sh</code> · (b) <code>Unit htpd.service not found</code> · (c) "no instances were found" · (d) "The provided role does not have permissions to perform this action" on the Source card · (e) <code>…ec2-codedeploy-role/i-0abc… is not authorized to perform: s3:GetObject</code></summary>

(a) CodeBuild, your own check in the Build stage · (b) the EC2 agent running your hook script · (c) CodeDeploy the service, tag filter · (d) CodePipeline's role or the source object · (e) the EC2 agent's instance role.
</details>

<details>
<summary>6. You add the Build stage but forget to change Deploy's input artifact. Is the pipeline red or green, and what is on the server?</summary>

Green, and the server has the *unstamped* original: CodeBuild stamped a copy nobody consumed. Green is not the same as correct; check which artifact each stage consumes.
</details>

<details>
<summary>7. Two servers, OneAtATime, rollback on, broken start script. How long was the whole site unreachable?</summary>

Never. The second server was skipped and kept serving the previous version the entire time; only the first server was down, for about a minute, until the rollback restarted it.
</details>

**Next:** [Lab 3 – The broken pipeline: six bugs between you and a working website](lab3-broken-pipeline.md)

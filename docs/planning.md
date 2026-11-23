# Software factory — design

Status: all 13 decisions are closed. This document awaits the owner's approval.

## Intent

Build a small software factory to learn how one works: an issue goes in, a deployed change comes out, and brakes stop it when it goes wrong. The first focus is a working pipeline. Agents come after the pipeline and its brakes are proven.

## The loop in one sentence

Label an issue `ready` → a workflow picks it up and produces a branch + PR → the pipeline builds, tests, scans → a human (or policy) merges → a workflow deploys → the turn closes the issue or opens a follow-up.

## Components

- **Repo**: one public monorepo, `victormasson21/software-factory`.
  - `factory/`: config (kill switch, model routing), policies, Terraform, evals.
  - `deploy/`: Kubernetes manifests per environment.
  - `services/<name>/`: one folder per service. The first is a hello-world in Python with FastAPI and `uv`.
  - `.github/workflows/`: CI, the turn runner, the deploy workflow, the reviewer, metrics.
- **Queue**: GitHub Issues with labels `ready` → `in-progress` → `done` / `failed`.
- **Bot**: a GitHub App with no `workflows` permission. It opens branches and PRs and swaps labels.
- **Turn runner**: a workflow on `issues: labeled` that creates branch `turn/<issue-number>`, does the work (first a human, later Claude Code), and opens a PR that references the issue.
- **CI**: lint (`ruff`) → tests with coverage threshold (`pytest`) → Gitleaks → build image tagged with SHA → Trivy on image and `uv.lock` → push to GHCR. Path filters limit each run to the changed service.
- **Guard check**: fails a bot PR that touches a protected path, removes or changes an existing test, or passes the diff size limit.
- **Reviewer agent**: a separate Claude Code run that reads the issue and the diff. Its verdict is a required check.
- **CD**: a deploy workflow, started by a merge to `main`. It runs `kubectl apply` on `deploy/dev` with the image SHA, waits for the rollout, then runs the smoke test. Prod is a manual dispatch of the same workflow with a SHA.
- **Infra**: Terraform for one Hetzner VM with k3s and a firewall; one `make up` / `make down`. `make up` ends with one deploy run.
- **Metrics**: a scheduled job that reads issue and workflow history and writes turn count, lead time (label → deploy), failure rate, MTTR and cost per turn to a markdown report.

## Turn lifecycle, step by step

1. A person with write access labels an issue `ready`. The turn runner checks the kill switch, the halt state and the concurrency cap, then swaps the label to `in-progress` and assigns the bot.
2. Branch and PR created, body links the issue. Each commit on the branch runs CI.
3. CI gate: all checks must pass. Trivy fails on critical/high, Gitleaks fails on any finding, the guard check and the reviewer agent must pass.
4. Merge: the bot's PR merges itself when every required check is green. No human review, unless the guard check stops the PR.
5. The deploy workflow deploys to dev and runs the smoke test.
6. Result handling: success → label `done`, issue closed with the deploy SHA. Failure → label `failed`, failure log posted as a comment, and optionally a new `ready` issue for the fix. That optional step is the self-propagating loop. Enable it last.

## Safety and stop controls

- Branch protection on `main`: required checks, no direct push, no force-push. No review rule.
- Prod gate: a prod deploy is a manual dispatch by the owner. It is the human approval.
- `concurrency: turn-${{ github.event.issue.number }}` and a global cap of N in-progress turns. The runner refuses to start above the cap.
- Kill switch: `enabled: false` in `factory/config.yml`. The turn runner and the deploy workflow both check it. A change is a PR, so a stop is auditable.
- Failure cap: three consecutive failed turns open a `factory-halted` issue. The turn runner refuses to start while one is open. A person closes it to resume.
- Budget limit per turn for each agent run.
- Scheduled turns limited to one cron: a nightly workflow that opens one `ready` issue per outdated package, with the `deps` label.
- Hard stop: `make down` (Terraform destroy).

## Triage rule

A person adds `ready`. No agent applies it, except the nightly dependency bump.

- **The factory builds**: dependency bumps, docs, and small changes in one service with acceptance criteria in the issue.
- **A person builds**: changes to `factory/`, `deploy/`, workflows and infra; anything about secrets or security; data migrations; each issue without acceptance criteria.

An issue template asks for the acceptance criteria and the service name.

## Build order

1. Monorepo skeleton, Terraform, CI, and the hello-world service deployed to dev by the deploy workflow. Prove commit → deploy with zero manual steps.
2. Issue-triggered turn runner with the GitHub App, a human doing the change. Prove label → PR → merge → deploy → issue closed.
3. Kill switch, concurrency cap, failure cap. Prove each by tripping it on purpose.
4. Trivy and Gitleaks gates, and the guard check. Prove each with a bad commit on purpose (a leaked fake key, a known-vulnerable dependency, a deleted test).
5. Metrics job. From here each turn generates evidence.
6. Put `factory/` under the same flow: changes go through issues and CI, built by a person.
7. Benchmark set for evals.
8. Agent turns: Claude Code as builder with label routing and a budget limit, the reviewer agent, then nightly dependency issues as the first autonomous turns.
9. Failure → follow-up issue loop, now that brakes exist.
10. Add a second service under `services/` to prove reuse.

## Definition of "useful" (acceptance tests)

- Label-to-deploy lead time under 15 minutes
- Zero manual steps between `ready` and dev
- A leaked secret and a critical CVE are both blocked at PR
- A runaway loop is stopped by the failure cap without human action
- Second service to dev in under an hour
- `make down` then `make up` restores everything from git

## Non-goals

- No GitOps controller.
- No multi-repo setup.
- No triage agent.
- No production traffic. Prod is a second namespace on the same VM.

## Decisions

Decisions 1 to 10 were made on 2026-11-13, decision 11 on 2026-11-16, decisions 12 and 13 on 2026-11-17.

### Platform

1. **Hosting for the cluster** — **one Hetzner VM with k3s**
   - Why: Terraform gives a true `make up` / `make down`, and the VM's public IP lets the smoke test reach the app from GitHub's runners.
   - Constraint: the VM is public, so the Terraform includes a firewall from the first day.
   - Alternative, not chosen: local k3d. GitHub-hosted runners cannot reach it, and the factory stops when the laptop sleeps.
   - Alternative, not chosen: managed cloud Kubernetes. `make up` is slower and the cost is higher.
2. **GitHub account and visibility** — **`victormasson21`, public repo**
   - Why: branch protection, Actions minutes and GHCR are all free on public repos.
   - Constraint: the turn runner acts only when a person with write access adds `ready`.
   - Constraint: fork PRs get no secrets. Keep GitHub's defaults.
   - Alternative, not chosen: private. Branch protection needs GitHub Pro, and the cluster needs a pull credential.
3. **Repo layout** — **one monorepo**
   - Why: fast to start, and one PR can change everything.
   - Constraint: the bot can write to the whole repo, so decision 9 protects the checks by token permissions, CODEOWNERS and the guard check.
   - Constraint: workflows use path filters.
   - Alternative, not chosen: separate repos. Stronger permission boundary, but more setup and multi-repo PRs.
4. **Bot identity** — **GitHub App**
   - Why: the built-in `GITHUB_TOKEN` cannot open a PR that starts CI. An App can, with tokens that last one hour.
   - Why: its PRs have the bot as author, so the owner can approve one when the guard check requires it.
   - Constraint: the App has no `workflows` permission, so GitHub refuses its pushes to `.github/workflows/`.
   - Setup: a person creates the App in the GitHub UI and stores its private key as a repo secret.
   - Alternative, not chosen: fine-grained PAT. PRs appear as the human's, the token is long-lived, and metrics cannot separate bot from human.
5. **Deploy method** — **push-based deploy from a workflow, no GitOps controller**
   - Why: one less component to install, learn and run. The workflow result is the deploy result.
   - Constraint: GitHub holds a cluster credential. It is a service account token limited to the app namespaces, not the admin kubeconfig.
   - Constraint: the k3s API port is open to the internet, because GitHub's runners have no fixed address. Access depends on the token.
   - Known limit: nothing corrects drift. A manual change on the cluster stays until the next deploy.
   - Known limit: the deployed image SHA lives in the workflow run, not in git.
   - Alternative, not chosen: Flux or Argo CD. No credential outside the cluster and git as the full record, but one more system to run.
6. **Hello-world app stack** — **Python with FastAPI and `uv`**
   - Why: the language the owner reads fastest, so each agent change is quick to judge.
   - Alternative, not chosen: Go (CVE gate hard to trip on purpose), TypeScript (most dependency noise).

### Agent

7. **Cost: model routing** — **yes, route by issue label and escalate on failure**
   - Agent: Claude Code, run by the turn-runner workflow with an API key.
   - How: a table in `factory/config.yml` maps a label to a model. `deps` and `docs` use the small model, all others use the mid model.
   - How: a turn that fails its checks is retried once on the next model up.
   - How: each turn has a budget limit. Routing lowers the average cost, the limit caps the worst case.
   - Why: about ten lines of config, no extra model call, and each model choice is auditable.
   - Alternative, not chosen: one model with a budget limit only. Nothing to build, but mid-model prices for each dependency bump.
   - Alternative, not chosen: a classifier model that picks the model per issue. Adapts to badly labelled issues, but is hard to audit and needs evals of its own.
8. **Context** — **a minimal fixed set, the rest by search on demand**
   - Every turn: the issue title, body and acceptance criteria, and one short conventions file at the repo root.
   - On a retry only: the log of the failed step and the current diff.
   - Rule: fresh context per turn. The issue and the PR hold the state.
   - Rule: small issues. Triage rejects an issue that spans services or has no acceptance criteria.
   - Rule: trimmed logs. A retry gets the last lines of the failed step, not the full run.
   - Rule: a check fails if the conventions file passes about 100 lines.
   - Rule: a lesson from a failure enters the conventions file through a PR by a person.
   - Why: cost per turn stays flat as the repo grows, and each turn can be reproduced from the issue and the commit.
   - Alternative, not chosen: preload the whole service folder. Cost grows with each file.
   - Alternative, not chosen: a memory file carried between turns. Keeps mistakes, grows without limit, hard to audit.
9. **Verification** — **the plan's checks, a guard check, and a separate Claude reviewer agent**
   - Reviewer agent: a fresh context. It gets the issue and the diff, and never the builder's conversation.
   - Reviewer agent: it runs in its own workflow with a read-only token. Its findings are a PR comment.
   - Barrier, workflow files: the App has no `workflows` permission.
   - Barrier, thresholds and scanner config: they live in the workflow files or in `factory/`. Ignore files such as `.trivyignore` are protected paths.
   - Barrier, protected paths: `factory/`, `deploy/`, the conventions file and the lint config. CODEOWNERS names the owner.
   - Barrier, tests: the bot may add tests. A removed or changed test fails the guard check.
   - Barrier, merge: the bot merges only when every required check is green (decision 12). A PR stopped by the guard check needs the owner's approval, and the bot cannot approve its own PR.
   - Barrier, credentials: the builder's job gets the App token only. The cluster token exists only in the deploy workflow.
   - Known limit: the builder can write a weak new test that passes. The coverage threshold, the reviewer agent and human review reduce this.
   - Constraint: the metrics job records the reviewer's cost apart from the builder's cost.
   - Alternative, not chosen: the plan's checks only. Less to build, but human review is the only defence against a weakened test.
   - Alternative, not chosen: guard check with no reviewer agent. Cheaper per turn, but no check reads the logic of the change once auto-merge starts.
   - Alternative, not chosen: the builder reviews its own work in the same context. No extra run, but it repeats its own blind spots.
10. **Evals** — **a benchmark set, replayed on demand. Build deferred to step 7.**
    - What: about 10 fixed issues with known good outcomes, in `factory/evals/`. Some are trap issues, where the easy path is to weaken a test.
    - How: a workflow, started by hand, runs each issue three times against a factory branch, on a throwaway branch with no deploy.
    - Output: pass rate, cost per turn, time per turn and retries, compared against `main`.
    - Why: only fixed inputs tie a result to one change. The trap issues also test decision 9.
    - Known limit: the sample is small. It shows large effects only.
    - Until it exists: the metrics job is the only measure.
    - Alternative, not chosen: production metrics only. Nothing to build, but the issues differ each week and an answer takes days.
11. **Triage** — **a written rule, applied by a person**
    - The rule: see "Triage rule" above. It matches the protected paths in decision 9, so the guard check enforces it.
    - Why: no build work beyond an issue template, and a person stays at the point where judgement matters most.
    - Alternative, not chosen: a triage agent that proposes a label. Saves reading time only when issues are many, and needs evals to be trusted.
    - Alternative, not chosen: a triage agent that applies the label. A stranger's issue could start a turn, which breaks a constraint of decision 2.
12. **Merge policy** — **the bot merges to `main` when the checks pass; the human gate is the prod deploy** (2026-11-17)
    - How: no review rule on `main`. GitHub auto-merge completes the bot's PR when every required check is green.
    - How: a merge to `main` deploys to dev. A prod deploy is a manual dispatch by the owner.
    - Why: an automated factory needs PRs the bot can merge. One branch means no drift and no promotion PR.
    - Constraint: the guard check and the reviewer agent are the only checks that read a change before it merges.
    - Constraint: the failure cap and the automatic rollback are proven (step 3) before any agent runs.
    - Known limit: `main` can hold work the owner has not read.
    - Alternative, not chosen: a `dev` branch the bot merges into, with a reviewed promotion PR to `main`. A real diff review before prod, but large bundled reviews and one bad turn blocks the promotion.
    - Alternative, not chosen: an approval workflow for `deps` PRs only. Automates only part of the factory.
    - Alternative, not chosen: human review on every PR. The factory is then not automated.
13. **Dependency bumps** — **a nightly workflow files issues, Claude makes the change** (2026-11-17)
    - How: a scheduled workflow lists outdated packages and opens one `ready` issue per package with the `deps` label.
    - How: Claude edits the lockfile in a normal turn, so the turn runner, guard check, routing and metrics all apply.
    - Why: these turns exist to exercise the factory. They are the first autonomous turns.
    - Constraint: the workflow opens no issue for a package that already has an open one.
    - Known limit: it costs tokens for a mechanical change.
    - Alternative, not chosen: Renovate or Dependabot. Free and reliable, but they open PRs that bypass the turn runner, so they are not turns.

## Calls made by Claude, not by the owner

- The folder layout under "Components".
- The failure cap halts through an open `factory-halted` issue, not through a commit to `factory/config.yml`. A workflow cannot push to a protected `main`.
- Prod is a second namespace on the same VM.
- The guard check is built at step 4, with the other gates.
- The reviewer's verdict is a required check. Its token can read the repo and write PR comments, and nothing else.
- The reviewer agent runs on bot PRs only. On a PR by a person, its check passes without a run.
- A turn fails when its one retry also fails the checks, or when the rollout or the smoke test fails. Each failed turn counts toward the failure cap.
- A retry starts when a check fails on the turn's PR. It uses the next model up: small → mid → large. A turn on the large model retries on the large model.
- A failed rollout or smoke test triggers `kubectl rollout undo`, so dev returns to the last good version.
- Guard check override: the guard passes when the owner has approved the PR's current commit. A label cannot override it, because the bot can add labels.
- Build order: step 4 was built before steps 2 and 3, because the owner delays the VM and step 4 needs none.
- Guard, who it stops: each PR whose author is not the repository owner. On an owner PR the guard runs and reports, but does not fail.
- Guard, trusted code: the workflow runs on `pull_request_target` and the script comes from the base commit. A PR cannot change the guard that judges it.
- Guard, after an approval: the owner re-runs the guard job. No review event starts it, because a skipped job from such a run could replace a failed check.
- Guard, protected paths: `factory/`, `deploy/`, `.github/`, the root `Makefile`, and each file named `ruff.toml`, `.ruff.toml`, `conftest.py`, `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `.trivyignore`, `.gitleaksignore` or `.gitleaks.toml`.
- Guard, tests: each change to an existing file under a `tests/` folder fails, also when lines are only added. A rename counts as a removal. The bot adds tests in new files.
- Guard, size: at most 400 changed lines. Files named `uv.lock` do not count.
- Trivy skips findings with no fix (`--ignore-unfixed`). A finding with no fix would block each PR with no possible action.
- Gitleaks scans the history of the PR's merge commit, not each branch in the repo.
- Scanners run as container images pinned by digest. No third-party action is used for them.

## Evidence

### Step 4 (2026-11-20)

- Leaked secret: PR #7 added a fake private key. `gitleaks` failed.
- Vulnerable dependency: PR #8 added `urllib3` 1.24.1. `ci / build` failed at the Trivy image scan.
- Deleted test: PR #9 removed one test. The guard reported `existing test changed or removed: services/hello/tests/test_main.py`. All other checks passed, so only the guard saw the removal.
- First scan of `main`: Trivy found 6 HIGH findings in the hello image (1 in `zlib1g`, 5 in the packages that pip vendors). The image now upgrades its OS packages and has no pip.
- Not proven: the failing path of the guard and the approval override. Both need a PR by a non-owner, so they wait for the GitHub App (step 2). Unit tests cover the exit status.

### Known limits of the guard

- A change to `[tool.coverage]` in a `pyproject.toml` can hide files from the coverage threshold.
- A new `pyproject.toml` below a service folder can replace the ruff config for that subtree.
- An inline `gitleaks:allow` comment hides a secret from Gitleaks.
- The conventions file is not protected. It gets a name at step 8.
- An owner approval stays valid after a later "request changes" on the same commit.

## Left to the builder

- VM size, k3s install method, and how the app is exposed (ingress, DNS, TLS).
- Terraform state location.
- The values of N (concurrency cap), the coverage threshold, the diff size limit and the budget limit.

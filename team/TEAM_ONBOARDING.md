# Team onboarding guide

> This document is for developers using the ohos_qt-skills knowledge base for the first time.

## Prerequisites

- Git (>= 2.x)
- Bash (>= 4.x) — Windows users use Git Bash
- Python (>= 3.8)
- (Optional) gitleaks 8.30.1 — for local secret scanning

## Quick start

### 1. Clone the repository

```bash
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
```

### 2. Initialize your personal environment

```bash
# Environment initialization goes through the skill (detects DevEco / SDK / Qt source and gives install commands for anything missing)
cat skills/kb-init/SKILL.md
# Or just ask the agent: "initialize the environment"
```

The wizard walks you through setting:
- Your name/slug (used for branch names and the contributors field)
- The Qt source path (optional)
- The HarmonyOS SDK path (optional)

It generates `ENV.local.md` (gitignored, never committed).

### 3. Install the pre-push hook

```bash
cp _scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

This automatically checks before every push whether private content was accidentally included.

### 4. Verify the environment

```bash
bash _scripts/verify.sh
```

If all checks pass, the environment is ready.

## Day-to-day use

### Finding knowledge

1. Open `_index/_task-routing.md` and find your task type
2. Read the pages the routing table points to
3. Search for errors: `grep -rl 'keyword' problems/` or look at `_index/_map.md`

### Contributing knowledge

See [CONTRIBUTING.md](../CONTRIBUTING.md). The short version:

```bash
git checkout -b <your-name>/<type>-<slug>
# edit/add files
bash _scripts/verify.sh
git add <files>
git commit -m "<type>(<scope>): <summary>"
git push origin <branch>
# create a PR on GitCode
```

### Using AI agents

This repository's `CLAUDE.md` / `AGENTS.md` define the behavior rules for AI agents. If you use Claude Code, Codex, or another AI coding tool, it loads these instructions automatically.

After each task, the agent automatically contributes knowledge (writing to `drafts/` or `problems/`) and submits it via a PR.

## Directory structure at a glance

| Directory | Contents |
|-----------|----------|
| `semantic/` | Technical concepts, API mappings, platform limitations |
| `procedural/` | Workflows, build steps |
| `episodic/` | Project retrospectives, decision records |
| `problems/` | Build/runtime errors and their solutions |
| `drafts/` | New knowledge drafts awaiting review |
| `_index/` | Derived indexes (generated automatically; don't edit by hand) |
| `_scripts/` | Automation scripts for gates, index rebuilding, bots, and so on |
| `_templates/` | Knowledge page/draft/problem templates |
| `ohos-common-kb-public/` | General HarmonyOS platform knowledge (embedded) |
| `skills/` | Automation skills |

## FAQ

**Q: verify.sh reports "gitleaks not found"**
A: gitleaks is optional. For installation, see https://github.com/gitleaks/gitleaks/releases. If it isn't installed you only get a WARN; it won't block your work.

**Q: I'm not sure whether my content is suitable to be public**
A: Faults go into `faults/_drafts/` (using `faults/_drafts/_template.md`); knowledge goes directly into a formal page written from the template. Mark "needs careful review" in the PR description.

**Q: Do the index files (_index/) need to be updated by hand?**
A: The counts are guarded by the gate: after changing pages, run `bash _scripts/ci.sh`; if the page counts/dashboard numbers don't match reality, it fails outright. The index entries themselves are added by hand, one line per new page.

# Branch convergence record

Historically this repository had several parallel branches (content sync, releases, architecture experiments). This file records **how each branch's content actually
made it into `trunk`**, plus the few pieces of content **deliberately not merged** and their current counterparts — so that nothing "looks merged
but is actually missing half", and so that the same thing never exists in two different ways in the repository.

Re-review command (can be rerun at any time):

```bash
git fetch origin
for b in $(git branch -r | grep -v HEAD | sed 's#origin/##' | tr -d ' '); do
  printf "%-26s ancestor=%s unique_commits=%s\n" "$b" \
    "$(git merge-base --is-ancestor origin/$b trunk && echo YES || echo NO)" \
    "$(git rev-list --count trunk..origin/$b)"
done
```

---

## 1. Merge status

| Branch | Unique commits | Status | Notes |
|--------|:--------------:|--------|-------|
| `main` | 0 | **Fully merged** | The v2.2.1 knowledge baseline, an ancestor of `trunk` |
| `bitfun-release` | 0 | **Fully merged** | Source of the execution layer (CLI), machine layer (QOH/R), fault graph, and templates |
| `fix/kb-init-scripts` | 0 | **Fully merged** | Ancestor |
| `sync/rewrite-*`, `sync/sync-*` (5 branches) | 0 | **Fully merged (2 pages added after the 2026-11-02 re-review)** | Historical sync points, all ancestors. The re-review found `sync/sync-2026-09-11` was 66 commits newer than `main`, and two files hadn't come in at the time: `episodic/postmortems/tdesktop-harmonyos-porting.md` (new, now added) and `problems/runtime-icons-missing-libqico.md` (deleted upstream after 08-01, but the root cause still holds and this repository had no coverage; added, with its missing closing frontmatter fence fixed); `semantic/deveco-mcp-toolchain.md` and `semantic/harmonyos-dev-fundamentals.md` were already merged into the embedded common KB (see section 2) |
| `release/v2.1.0` | 0 | **Fully merged** | Old release line, ancestor |
| `matrix-release` | 1 | **Content merged** | Its only commit is the `README.md` + `SKILL.md` rewrite: `trunk` takes these two documents as its base and layers the governance layer on top (`kb.yaml`, `_scripts/`, `TESTING.md`, `CONTRIBUTING.md`, branch model, release process) |
| `lzh-add-qt-cef-graft-test` | 1 | **Content merged** | The CEF development guide and PyQt status page were already in `trunk`; this time `tools/kb-cef-graft.py` + a config sample were added, and the old claim in the guide that "the script isn't in this knowledge base" was corrected |
| `trunk-flip-v3` | 4 | **Partially merged** | Added `team/`, `_templates/`, `procedural/knowledge-sedimentation.md`, `_scripts/pre-push`; for the rest see section 2 |

The three branches whose content was merged also had their ancestry registered with `git merge -s ours` (recording history only, without touching the file tree),
so `--is-ancestor` returns YES for **all 13 branches**, and `trunk..<branch>` is always 0:
no branch is left dangling in either content or history.

`matrix-release` existed separately so that an external release with **only the knowledge layer** could ship first; its documentation stance
(positive statements, keeping all commands and operational details) is now `trunk`'s documentation stance, and the two no longer diverge.

---

## 2. Content deliberately not merged

There is only one criterion: **would the same thing exist in two different ways**. Anything that would conflict with the current state of `trunk`, or that has been superseded by
`trunk`'s toolchain, is not copied in; the table states where its capability lives now.

| From | Content | Why it wasn't merged | Where this capability lives now |
|------|---------|----------------------|---------------------------------|
| `trunk-flip-v3` | `_scripts/kb-gate.sh` (946 lines) | Its checks overlap heavily with `verify.py`, and it encodes the **old schema** (such as "trunk pages have no `audience` field" — the opposite of this repository's required `audience: public`); merging it would create two mutually exclusive sets of criteria | `_scripts/verify.py` (10 kinds) + `_scripts/ci.sh` |
| `trunk-flip-v3` | `_scripts/kb-release.sh`, `_scripts/RELEASE-STATE` | The release state machine is superseded by `RELEASE-MANIFEST.yaml` (machine-computed, reconcilable) | `_scripts/gen-manifest.py` + `CONTRIBUTING.md` §Release process |
| `trunk-flip-v3` | `_scripts/kb-regen-indexes.sh` (345 lines) | Its output format is based on the old index layout; running it directly would revert the dashboard to the old format | Counts are guarded by `tests/test_kb_consistency.py` (page counts/domain counts/fault scale bound to the docs), and entries get a line added by hand along with each page; **this is a known gap in this repository**, and when it's filled later it should be rewritten for the current layout rather than ported |
| `trunk-flip-v3` | `_scripts/kb-sediment.sh` (254 lines) | It writes to `drafts/E{N}-*`, a second draft convention alongside this repository's `faults/_drafts/` | `procedural/knowledge-sedimentation.md` (protocol) + `skills/kb-iterator` (process) + `faults/_drafts/_template.md` |
| `trunk-flip-v3` | `_scripts/kb-promote-drafts.sh` | Same as above; different draft directory convention | The editor-in-chief gate (`faults/_index.md` §6) + `skills/kb-iterator/SKILL.md` |
| `trunk-flip-v3` | `_scripts/kb-bot.py` (408 lines, PR bot) | Depends on an external bot runtime and GitCode credentials, outside the knowledge layer's responsibilities | Not provided; maintainers run the merge gates by hand |
| `trunk-flip-v3` | `_scripts/kb-init.py` | Environment initialization is already handled by the skill (detection + install commands + writing `ENV.local.md`) | `skills/kb-init/SKILL.md` + `tools/qt-sdk-run.py init` |
| `trunk-flip-v3` | `_scripts/kb-sync-common.sh` | Used to sync the embedded platform knowledge subset; this repository's `ohos-common-kb-public/` is already a trimmed, stable subset with no sync source | **Known gap**: to be added if upstream sync is ever restored |
| `trunk-flip-v3` | `drafts/README.md` + the `drafts/` directory | A draft entry point duplicating `faults/_drafts/` | `faults/_drafts/` (template `faults/_drafts/_template.md`) |
| `lzh-*` | `TEST-REPORT.md` (a one-off validation record at the repository root) | Putting one-off test reports in the root directory makes the entry files ever more cluttered; the conclusions are already reflected in the version/integration sections of the CEF guide | The test record subsection of `procedural/qt-cef-ohos-dev-guide.md` |

| `sync/*` | `semantic/deveco-mcp-toolchain.md` | Upstream already merged it into the embedded common KB; keeping both would create two sources of truth | `ohos-common-kb-public/semantic/deveco-mcp-capabilities.md` |
| `sync/*` | `semantic/harmonyos-dev-fundamentals.md` | Same as above; a new-id version of the same page | `ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md` |
| `main` | 139 files under `skills/qt-community-to-official/templates/{entry,oh_modules,.idea,.hvigor}` | Build artifacts (`.cxx` cache, `oh_modules` dependencies, IDE indexes); checking them in would make the template unusable and bloat its size | The clean `templates/qt-ohos-app` template |
| `release/v2.1.0`, `fix/kb-init-scripts` | `skills/skills/kb-init/*` (one extra path level), `.obsidian/*` | Duplicate copies of the old layout and editor configuration; the current `kb-init` is newer (aligned with the four-level devecocli lookup on 2026-10-12) | `skills/kb-init/` |

> Content that wasn't merged is still fully preserved on the corresponding frozen branches and can be retrieved at any time: `git show origin/trunk-flip-v3:_scripts/kb-regen-indexes.sh`.

---

## 3. Consistency after merging

`trunk` has only one criterion: `bash _scripts/ci.sh` all green. The merges themselves are bound by it too —
if page counts, fault scale, test counts, or the release manifest disagree anywhere, the gates go red immediately (`M1`, `C8`,
the `test_document_counts` series).

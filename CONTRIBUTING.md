# Contributing guide

## What this repository is

This repository **has changed from a "read-only derived view" into a "mainline development repo"**: the `trunk` branch is the single mainline, where knowledge, machine rules,
and the toolchain all evolve; external contributions come in through development branches.

> ⚠️ **Migration note**: historically this repository was rebuilt wholesale from an upstream internal knowledge base filtered on `audience:public`.
> Starting with `trunk` (v3.0.0), this repository replaces that pipeline as the source of truth. **If the upstream rebuild pipeline is still running,
> it must be disabled first**, or merges into this repository will be overwritten by the next rebuild.

---

## Branch model

| Branch | Role | Who may touch it | Rules |
|--------|------|------------------|-------|
| `trunk` | Mainline · stable releases | Maintainers | Accepts only merges from development branches; `verify.sh` + the full test suite must pass before merging; releases are tagged `vX.Y.Z` |
| `dev/<topic>` | Development · accepts PRs | Any contributor | Branched from `trunk`; may be unstable; must pass the gates before merging back into `trunk` |
| `release/vX.Y.Z` | Archive | Maintainers | Branched from the release point; only fatal defects are fixed (cherry-pick), no new features |
| `main` and other historical branches | Frozen | Nobody | **No longer accept commits**, kept for historical reference only; what was merged is documented in [LINEAGE.md](LINEAGE.md) |

```
trunk ──●────────●────────●────────●──→  stable, releasable
         \      / \      / \      /
  dev/*   ●────●   ●────●   ●────●        development, mergeable
                   \
  release/vX.Y.Z     ●────●               archive, fatal fixes only
```

---

## Release process (maintainers)

A release is a **recomputable mechanical action**, not a hand-filled manifest. Prerequisites: the gates on `trunk` are all green, and the
real-device end-to-end run in `TESTING.md` has a conclusion (passed, or PARTIAL with every item justified).

```bash
# 1. Confirm the current commit is the tree you want to release
python _scripts/ci.py                      # all four gates in one command (runs on Windows without bash too)
python tools/faults-build.py check

# 2. Refresh the release manifest (recompute the content tree digest, page counts, test counts, timestamp)
python _scripts/gen-manifest.py

# 3. Set it to released and backfill root_commit / released_at
python _scripts/gen-manifest.py --release

# 4. Tag only once the manifest is self-consistent (the tag goes on the commit containing the released manifest)
git add RELEASE-MANIFEST.yaml CHANGELOG.md
git commit -m "release: v3.0.0"
git tag -a v3.0.0 -m "ohos_qt-skills v3.0.0"
git push origin trunk --tags

# 5. Cut the archive line from the tag
git branch release/v3.0.0 v3.0.0 && git push origin release/v3.0.0
```

Verification afterward: `python _scripts/gen-manifest.py --check --strict` should report "consistent". Day to day, use
`--check` (without `--strict`): counts must match, but the digest may be an "old snapshot" — otherwise every ordinary commit would turn red,
and soon nobody would look at the check. `verify.sh`'s M1 likewise only enforces digest consistency when **standing on the release commit**.

Trial/candidate releases can be tagged `vX.Y.Z-rc1` following the same process, leaving the manifest `status` at `trunk-candidate`.

---

## How to contribute

### 1. Code / tools (`tools/`, `portgraph/`, `templates/`)

```bash
git switch -c dev/<your-topic> trunk
# changes + tests
python _scripts/ci.py
git push origin dev/<your-topic>      # open a PR against trunk
```

Requirements:

- Changes must come with tests; PRs that loosen gate criteria (G0–G12 / SV0–SV8) are never accepted.
- New CLI subcommands must update the subcommand contract table in `tests/test_kb_consistency.py` (that's the anchor against drift).
- Only the Python standard library is allowed as a dependency; optional dependencies such as `portgraph serve` must be isolated on optional paths.

### 2. Knowledge content (`semantic/` `procedural/` `episodic/` `problems/` `faults/`)

- **New errors**: first check whether `problems/_lookup.md` already has it; when adding, include the full verbatim error, the environment trio
  (Qt version / OHOS SDK version / DevEco version), reproduction steps, and the solution.
- **New faults**: prepare a draft following `faults/_drafts/_template.md` (verbatim symptom / environment / **evidence** /
  duplicate-check statement). Defects must include a reproduction demo (the seven principles are in `faults/_index.md` §6); platform limitations may use
  an official documentation link instead. **Hearsay without evidence is not accepted.**
- **Page conventions**: frontmatter must include `id` / `type` / `summary` / `status` / `audience`;
  `id` is unique across the repository; `audience` can only be `public`; cross-references use `refs` (ids) or wikilinks, with no broken links.
- **Don't write local paths**: use the variable names from `ENV.local.md` (`QT5_15_OHOS_SDK`, etc.); `verify.sh`
  catches leaks such as `/Users/<name>/`.

The write gateway to the knowledge source of truth is `skills/kb-iterator`: business agents may only submit drafts, and merging goes through the editor-in-chief gate
(reproduction demo must be run + human verification + reproduction result recorded). Humans may open PRs directly following the conventions above, but they must pass the gates too.

### 3. Indexes and documentation

The **numbers in `README.md` / `SKILL.md` / `AGENTS.md` / `_index/*` are assertions guarded by tests**,
not casually written copy. Sync them when counts change, or `tests/test_kb_consistency.py` turns red.

---

## Feedback process (just want to report, not open a PR)

`.gitcode/ISSUE_TEMPLATE/` has ready-made templates; pick one by the kind of feedback you have:

| Your situation | Which template |
|----------------|----------------|
| A page's knowledge is wrong, or a command doesn't work | `kb-content-fix.md` |
| You want to add a new piece of knowledge / new API mapping / new retrospective | `kb-knowledge-request.md` |
| You want a skill to gain a capability, or think something should be split or merged structurally | `kb-capability-request.md` |
| Qt and HarmonyOS behave differently (same API, different results on the two sides) | `qt-crossplatform-diff.md` |
| The Qt docs / this repository's description don't match actual testing | `qt-doc-inconsistency.md` |
| Security problems | See [SECURITY.md](SECURITY.md); don't open a public issue |

After evaluation, maintainers land it following the source-of-truth rules: the knowledge layer goes through `faults/_drafts/` or the corresponding directory, and changes to tools and gates must come with tests.

## Gates before merging (all required)

```bash
python _scripts/ci.py                       # self-check + fault library + tests + CLI smoke
python tools/faults-build.py check          # fault library source of truth ↔ derived artifacts (must run if you changed faults/knowledge)
```

- `ERROR`s must be zero; `WARN`s are allowed but must be explained in the PR.
- If you changed `faults/_data/*.yaml` or a C page, you must run `python tools/faults-build.py build` to rebuild
  `_graph.yaml` / `_registry.md` and commit them.
- Commit messages should state clearly "which facts/criteria changed"; don't just write `update`.

---

## Not accepted

- ❌ Loosening or bypassing gate criteria, deleting/skipping tests, commenting out functional code to get the build to pass.
- ❌ Fault classifications without evidence (pure hearsay, guesses, screenshots of chat logs).
- ❌ Committing build artifacts (`.cxx/`, `.hvigor/`, `.idea/`, `.DS_Store`, `*.hap`) or local absolute paths.
- ❌ Content involving internal/private information (this repository only accepts `audience:public`).
- ❌ Committing directly on `trunk` or on frozen historical branches.

---

## Embedded general HarmonyOS platform knowledge

`ohos-common-kb-public/` is the embedded subset of platform knowledge (ArkTS / ArkUI / NAPI / Stage / toolchain,
27 pages). It is **maintainable** within this repository: open PRs for corrections directly, citing the official documentation links you relied on in the description.
If it conflicts with the official documentation, the official documentation wins.

## License

MIT (see `LICENSE`). Content of PRs / issues you submit is treated as a contribution under that license.

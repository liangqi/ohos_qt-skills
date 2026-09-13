# Contributing guide

## What this repository is

This repository is a **read-only derived view**: its content is regenerated from a larger Qt for HarmonyOS workflow knowledge base (the internal source) by `_scripts/kb-dev-edition.sh`, filtered on the frontmatter field `audience:public`. **The source is public-safe by construction** (gating happens at the source; publishing only filters, it does not sanitize).

Because of that:

- **Please don't open PRs against this repository's content files.** Every `.md` (`semantic/`, `procedural/`, `episodic/`, `problems/`, `_index/`, and the root documents) is **overwritten wholesale** on each release, so direct edits will be wiped out by the next one.
- **Please open issues instead.** Issues are the only community contribution channel that persists.

## How to contribute

1. **Open an issue**: file an issue in the repository describing
   - the problem you hit / the error you found / the knowledge you'd like added
   - the specific pages involved (file path or section heading)
   - where possible: the verbatim error message, reproduction steps, and what you expected
2. **The maintainers fix it in the [internal source]** (going through the distillation process where needed: issue information → distilled into a structured knowledge page → merged into the right domain).
3. **It ships via a release PR**: after fixing, the maintainers regenerate this repository and open a PR whose description says `closes #N`; once merged, your issue closes automatically and the content appears here.

## Contributions we welcome

- ✅ **Additions to the error library**: real build/deployment/runtime errors not yet covered in this repository's `problems/` (include the full error message and the solution)
- ✅ **Corrections and additions to API mappings / platform limitations**
- ✅ **Migration retrospectives and demo experience**
- ✅ **Documentation typos, broken links**
- ✅ **Suggestions for improving skills**: the automation scripts and tools in `skills/`

## What we can't accept

- ❌ PRs that edit content files directly (they'll be overwritten by the next release; please convert them into issues)
- ❌ Content involving internal/private information (this repository contains only `audience:public` content)

## Feedback workflows

### You found a content error

1. Open an issue in this repository and choose the "Knowledge correction" template
2. Describe the incorrect content, the pages involved, and the correct information
3. The maintainers will fix it in the internal source, and the fix ships with the next release

### You want to add new knowledge

1. Open an issue in this repository and choose the "Knowledge contribution" template
2. Describe the knowledge you want to add and your sources
3. The maintainers will evaluate it and distill it into the internal source; it ships with the next release

### You want to improve the skills

1. Open an issue in this repository and choose the "Feature / structure proposal" template
2. Describe the skill you want to improve and your suggested improvement
3. The maintainers will evaluate and implement it

## Embedded general HarmonyOS platform knowledge

This repository embeds the `ohos-common-kb-public/` directory, containing general HarmonyOS platform knowledge (ArkTS, ArkUI, NAPI, the Stage model, the DevEco toolchain, and so on). That content is generated from the internal `ohos-common-kb` repository, filtered on `audience:public`.

If you find a problem in the general platform knowledge, open an issue here as well and the maintainers will route it to the internal `ohos-common-kb` for a fix.

## License

MIT (see `LICENSE`). Issue content you submit is treated as a contribution under that license.

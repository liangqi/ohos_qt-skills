# Security feedback

If you find a security problem in this knowledge base (leaked credentials, insecure configuration examples, potential vulnerabilities, and so on), please report it through one of the channels below.

## How to report

### Option 1: GitCode security issue (recommended)

GitCode supports security/private issues that are visible only to the author and project members:

1. In this repository, click "Issues" → "New Issue"
2. Choose the "Security" type (if available)
3. Describe the security problem, including the relevant file paths and evidence
4. Once submitted, it is visible only to you and the project members

## What to include

Please provide the following:

- **Problem description**: a brief description of the security problem
- **Files involved**: specific file paths or code snippets
- **Scope of impact**: the scenarios that could be affected
- **Suggested fix**: include one if you have a suggestion

## Please note

- **Do not expose sensitive information in a public issue** (real credentials, internal URLs, personal paths)
- **Do not put a sensitive summary in the issue title**
- Once a security problem is fixed, the maintainers fix it in the internal source, and the fix flows into this repository automatically at the next release

## This repository's security boundary

This repository is a read-only derived view; its content is generated from an internal source filtered by `audience:public`. The gating on the internal source checks that there are:

- No secrets, internal URLs, or personal paths
- No undisclosed credentials or configuration
- No internal project codenames or sensitive information

If you find a security problem in this repository, it means the internal source's gating may have a gap, and the maintainers will fix the internal gating rules as well.

## License

MIT (see `LICENSE`). Security feedback you submit is treated as a contribution under that license.

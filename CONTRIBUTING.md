# Contributing to MeteoLens

This guide describes the repository workflow for branches, commits, pull
requests, and merge strategy. The mandatory repository guardrails remain in
[`AGENTS.md`](AGENTS.md).

## Branches and pull requests

- Do not commit directly to `main` unless the project owner explicitly asks for
  it.
- Use one of the allowed branch prefixes: `feature/`, `fix/`, `refactor/`,
  `docs/`, or `chore/`.
- Open pull requests against `main` and keep each pull request focused on one
  coherent change.
- Do not force-push `main`, delete branches, or rewrite published history.
- Before opening a pull request, run the checks relevant to the changed paths.
  For documentation-only changes, state that no runtime tests were needed and
  run the documentation checks described in the pull request description.

## Commit messages

Use short, imperative, Conventional Commit-style subjects where practical:

```text
feat: add station comparison endpoint
fix: preserve missing observation values
docs: document the release validation workflow
chore: update pinned GitHub Action
```

Prefer commits that represent a complete, reviewable step. Keep temporary
review-response commits, editor metadata, generated local files, and
CI/status-only notes out of the final branch unless they have lasting value.
Review fixes may remain separate while a pull request is under review, but the
integration strategy below should be used before merging.

## Choosing the integration strategy

The goal is a readable, searchable history without losing useful review and
release context.

| Change | Preferred integration | Reason |
| --- | --- | --- |
| Documentation, dependency update, or one small fix | Squash merge | One clear change and one useful subject on `main`. |
| Small pull request with several review-fix commits | Squash merge | Avoids carrying temporary review steps into the shared history. |
| Larger feature with independently meaningful commits | Rebase-and-merge | Keeps the logical commit sequence while avoiding an unnecessary merge node. |
| Release checkpoint, broad architecture change, or deliberate branch convergence | Merge commit | Preserves an explicit boundary and the branch context. |

Squashing and rebasing are different choices:

- **Squash merge** combines the pull request into one commit.
- **Rebase-and-merge** preserves the pull request's individual commits on top
  of the target branch, without creating a merge commit.
- **Merge commit** preserves both parent histories and is reserved for cases
  where that boundary is useful.

The existing merge commits on `main` are retained. They already mark coherent
pull requests and release stages, and rewriting them would change all
descendant commit IDs and require a disruptive force-push. Use
`git log --first-parent --oneline --decorate main` when reviewing the
project-level history.

## Documentation and checks

Update the documentation that owns the changed behavior:

- `README.md` for end-user behavior, setup, exports, screenshots, and
  troubleshooting;
- `ARCHITECTURE.md` for technical structure and data flow;
- `DATA_SOURCES.md` for source and parser status;
- `API_CONTRACT.md` for public API changes;
- `UI_UX.md` for user-visible layout or interaction changes;
- `LEGAL_ATTRIBUTION.md` for attribution and processed-data notices;
- `TASKS.md` when work is completed, split, blocked, or reprioritized.

For a documentation-only pull request, at minimum run:

```bash
git diff --check
```

Also inspect the rendered Markdown links and mention in the pull request which
runtime test suites were not required. Code, configuration, and workflow
changes must run the applicable backend, frontend, E2E, or security checks.

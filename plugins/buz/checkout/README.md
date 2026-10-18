# Git checkout

The buz equivalent of GitHub Actions' `actions/checkout`: checks a Git
repository out into a workspace subdirectory, landing on the **triggering
commit** for webhook-triggered jobs. Version 1.2.0 supports branch/tag refs,
full-SHA detached checkout, shallow fetches, optional submodules, and masked
token authentication for private HTTPS repositories.

```yaml
steps:
  - name: Checkout
    uses: buz/checkout@1.2.0
    with:
      repo: https://github.com/example/app.git
      # ref omitted → BUZ_GIT_SHA on webhook triggers, else the remote HEAD
```

Pin to the exact commit a webhook delivered (explicit ref wins when present):

```yaml
    with:
      repo: https://github.com/example/app.git
      ref: ${BUZ_GIT_SHA}
```

Private repository over HTTPS — store the token as a Manager Secret:

```yaml
    with:
      repo: https://git.example.internal/team/app.git
      token: ${secrets.GIT_TOKEN}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo` | string | yes | — | Repository URL (HTTPS) |
| `ref` | string | no | `BUZ_GIT_SHA`, else remote HEAD | Branch, tag, or commit SHA (detached; use the full 40-char SHA — abbreviated SHAs depend on server-side prefix support) |
| `into` | string | no | `source` | Target directory (GHA `path` equivalent), relative to the Runner workspace; must not exist |
| `depth` | string | no | `1` | Shallow fetch depth; `0` fetches full history (needed for tags/logs beyond the tip) |
| `submodules` | string | no | `false` | `false` / `true` / `recursive` — update submodules after checkout |
| `token` | string | no | — | Access token for private HTTPS repos (masked; also covers HTTPS submodules) |

## Notes

- Requires `git` on the Runner host. The template declares no `default_dir`,
  so the shell engine starts the step in the workspace root; it anchors the
  workspace root from the process cwd before anything chdirs, so `into`
  stays workspace-relative regardless.
- Existing parent directories and symlinks are resolved physically; target
  parents must remain inside the workspace. The target itself must not exist.
- The token is delivered through `GIT_ASKPASS` — it never appears in the
  URL, process list, or `.git/config`. HTTPS submodules reuse it.
- Commit SHAs are checked out detached via `git init` + `git fetch <sha>` +
  `checkout FETCH_HEAD` (the `actions/checkout` approach); servers must
  allow fetch-by-SHA (GitHub and GitLab do by default).
- `buz/git-clone@1.0.0` / `@1.1.0` remain available unchanged for existing
  pipelines; new pipelines should prefer `buz/checkout`.

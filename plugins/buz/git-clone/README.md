# Git clone

Clones a Git repository into a workspace subdirectory — the first step of a
build pipeline. Supports shallow clones, branch/tag checkout, and token
authentication for private HTTPS repositories.

```yaml
steps:
  - name: Checkout
    uses: buz/git-clone@1.0.0
    with:
      repo: https://github.com/example/app.git
      ref: main
      dir: source
```

Private repository over HTTPS — store the token as a Manager Secret:

```yaml
    with:
      repo: https://git.example.internal/team/app.git
      token: ${secrets.GIT_TOKEN}
      dir: source
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo` | string | yes | — | Repository URL (HTTPS) |
| `dir` | string | yes | — | Target directory, workspace-relative (must not exist) |
| `ref` | string | no | remote HEAD | Branch or tag to check out |
| `depth` | string | no | `1` | Shallow clone depth; `0` performs a full clone |
| `token` | string | no | — | Access token for private HTTPS repos (masked) |

## Notes

- Requires `git` on the Runner host (shell engine runs there, workspace as
  working directory).
- The token is delivered through `GIT_ASKPASS` — it never appears in the
  clone URL, process list, or `.git/config`.
- `--branch` accepts branches and tags; checking out a raw commit SHA
  requires `depth: 0` plus a follow-up `git checkout` in your own step.

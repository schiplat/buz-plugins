# Git clone

Clones a Git repository into a workspace subdirectory. Version 1.1.0 clones
into the `into` directory (default `source`) and refuses to overwrite an
existing target. Supports shallow clones, branch/tag checkout, and masked
token authentication for private HTTPS repositories.

```yaml
steps:
  - name: Checkout
    uses: buz/git-clone@1.1.0
    with:
      repo: https://github.com/example/app.git
      ref: main
```

Private repository over HTTPS — store the token as a Manager Secret:

```yaml
    with:
      repo: https://git.example.internal/team/app.git
      token: ${secrets.GIT_TOKEN}
      into: source
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo` | string | yes | — | Repository URL (HTTPS) |
| `into` | string | no | `source` | Target directory, relative to the Runner workspace; must not exist |
| `ref` | string | no | remote HEAD | Branch or tag to check out |
| `depth` | string | no | `1` | Shallow clone depth; `0` performs a full clone |
| `token` | string | no | — | Access token for private HTTPS repos (masked) |

## Notes

- Requires `git` on the Runner host. `git-clone` declares no `default_dir`,
  so the shell engine starts the step in the workspace root; the template
  anchors the workspace root from the process cwd before anything chdirs, so
  `into` stays workspace-relative regardless.
- Existing parent directories and symlinks are resolved physically; target
  parents must remain inside the workspace. The target itself must not exist.
- The token is delivered through `GIT_ASKPASS` — it never appears in the
  clone URL, process list, or `.git/config`.
- `--branch` accepts branches and tags; checking out a raw commit SHA
  requires `depth: 0` plus a follow-up `git checkout` in your own step.
- Version 1.0.0 remains unchanged and uses the required `dir` input.

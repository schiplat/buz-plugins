# Docker login (Runner host)

## 最新更新：1.1.0

`1.1.0` 新增可选的 `debug` 开关，默认关闭。需要调试登录时，使用 `buz/docker-login@1.1.0` 并在 `with:` 中设置 `debug: "true"`；固定使用 `@1.0.0` 的流水线不会自动获得此功能。

- 开启后输出脱敏登录命令、Docker 配置目录和登录退出码。
- 用户名和密码在插件调试输出中均显示为 `<redacted>`；密码仍通过 `--password-stdin` 传递，不启用 `set -x`。
- 登录失败仍返回 Docker 的非零退出码，不会因开启 debug 而忽略失败。
- 此开关独立于 Manager 的 job 级 debug，不会关闭日志脱敏。
- `shell` 和 `ssh` 两种执行方式均支持；旧 `1.0.0` 模板保持不变。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `registry` | string | 是 | — | 镜像仓库主机地址，不含用户名或密码。 |
| `username` | string | 是 | — | 仓库用户名，可以引用 `${secrets.REGISTRY_USERNAME}`。 |
| `password` | string | 是 | — | 密码或访问 Token，必须使用完整的 `${secrets.NAME}` 引用，日志脱敏。 |
| `debug` | boolean | 否 | `"false"` | 设置为 `"true"` 时打印脱敏诊断信息。 |

开启 debug 后，成功登录的诊断输出示例：

```text
[debug] command: docker login --username <redacted> --password-stdin registry.example.com (password: <redacted>, via stdin)
[debug] Docker config dir: <job-scoped directory>
[debug] docker login exit code: 0
```

## Usage

Logs the Docker CLI into a container registry so later steps can pull or push private images — `docker build`/`docker push` in shell steps, and `engine: docker` pulls. Requires the Docker CLI on the runner host.

```yaml
- name: registry login
  uses: buz/docker-login@1.1.0
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

The three authentication inputs (`registry`, `username`, `password`) are required. The password must be a complete `${secrets.NAME}` reference and is delivered via `--password-stdin` (never a CLI argument) and masked in logs.

Version `1.1.0` adds optional `debug` (boolean, default `false`). To enable it:

```yaml
- name: registry login with diagnostics
  uses: buz/docker-login@1.1.0
  with:
    registry: registry.example.com
    username: ${secrets.REGISTRY_USERNAME}
    password: ${secrets.REGISTRY_PASSWORD}
    debug: "true"
```

Debug output shows the login command with username/password redacted, the Docker config directory, and the Docker login exit code. It does not print credential values or enable shell tracing (`set -x`). A failed login retains Docker's non-zero exit code; debug does not make failures non-blocking. This template input is independent of the Manager's job-level debug mode and does not disable log masking. Existing `@1.0.0` pipelines remain unchanged.

Credentials land in the job-scoped Docker config dir (`DOCKER_CONFIG`, see the Runner `docker_config_isolation` setting) and are removed when the job ends — success, failure, or cancel. On shared runners, or with the legacy `shared` isolation mode, pair with `buz/docker-logout`. Multiple registries: one step each.

**Target hosts (`engine: ssh`)** — the template declares `engines: [shell, ssh]`, so the same step can log in on the pipeline's target hosts instead of the Runner. Later ssh steps on the same hosts (compose pull, etc.) reuse that login; the job-scoped dir lives under `/tmp` on each host.

```yaml
- name: registry login on target
  uses: buz/docker-login@1.1.0
  engine: ssh          # call-site override; also declared in the template (engines)
  host:
    - web-01
  with:
    registry: registry.example.com
    username: deploy
    password: ${secrets.REGISTRY_PASSWORD}
```

Pair with `buz/docker-logout` (`engine: ssh`, same `host:` list) as the last step.

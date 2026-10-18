# PHP build environment

Prepares a pinned PHP toolchain (8.4 or 8.3) with Composer preinstalled for the step's `run:` commands.

```yaml
- name: build
  uses: buz/setup-php@1.1.0
  with:
    version: stable
    cache: true
  run: |
    composer install --no-interaction
    ./vendor/bin/phpunit
```

## How your commands run

The step's `run:` commands execute after the toolchain setup, in the same shell — everything the template exports (PATH, PHPRC, COMPOSER_HOME, …) is visible to your commands. They start in the step directory: the template declares `default_dir: source`, and a step-level `work_dir` on the step overrides it. The directory must resolve physically inside the workspace.

`version` accepts `stable`/`lts`/`dev` (= 8.4) or `8.3`. With `cache: true` the Composer cache persists in `<workspace>/.cache/php` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to packagist.org.

## Versions in image 1.0.0

| `version` | Resolves to |
|-----------|-------------|
| `stable` (default), `lts`, `dev` | PHP 8.4 |
| `8.3` | PHP 8.3 |

Every run prints the resolved `php --version` as the first log line.

Version 1.0.0 templates remain unchanged and take the historical `script` and `workdir` inputs.

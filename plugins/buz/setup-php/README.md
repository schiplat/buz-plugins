# PHP build environment

Runs POSIX `script` commands inside a pinned PHP toolchain (8.4 or 8.3) with Composer preinstalled.

```yaml
- name: build
  uses: buz/setup-php@1.0.0
  with:
    version: stable
    cache: true
    script: |
      composer install --no-interaction
      ./vendor/bin/phpunit
```

`version` accepts `stable`/`lts`/`dev` (= 8.4) or `8.3`. With `cache: true` the Composer cache persists in `<workspace>/.cache/php` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to packagist.org.

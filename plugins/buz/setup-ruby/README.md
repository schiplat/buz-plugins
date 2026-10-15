# Ruby build environment

Runs POSIX `script` commands inside a pinned Ruby toolchain (3.4 or 3.3) with gem/bundler. Ruby 3.3 is EOL upstream and kept only for existing applications.

```yaml
- name: test
  uses: buz/setup-ruby@1.0.0
  with:
    version: stable
    cache: true
    script: |
      bundle install
      bundle exec rake test
```

`version` accepts `stable`/`lts`/`dev` (= 3.4, the newest line in the image) or `3.3`. With `cache: true`, gems and the bundler path persist in `<workspace>/.cache/ruby` across jobs on the same Runner. Each step is an isolated container — pass state between steps through workspace files. Requires a Docker-enabled Runner with egress to rubygems.org.

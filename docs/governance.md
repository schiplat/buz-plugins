# Marketplace governance and trust model

This document is the reference for how the Buz plugin marketplace governs
step templates: what the marketplace certifies, what it explicitly does not,
how the two template tiers differ, and how the `ssh` engine fits in. It is
written for template authors and pipeline operators deciding what to install.

## The two tiers

| | Official (`buz/*`) | Community (`<author>/*`) |
|---|--------------------|--------------------------|
| Author | The Buz org | Anyone, via pull request |
| First review | Human, by a maintainer | Human-optional — the author stands behind it |
| CI certification | Green master re-binds the content hash on every change | None |
| Egress baseline | Declared and enforced | Not part of enforced governance |
| Badge | Reviewed (after human first review) | Unbadged |
| Engines | `shell`, `docker`, `ssh`¹ | `shell`, `docker`, `ssh`¹ |

¹ `ssh` requires Buz 1.7.5+ (see [The ssh engine](#the-ssh-engine)).

Everything in the official tier is a claim the Buz org makes about its own
templates: *we wrote it, a human reviewed it, CI proves the content has not
changed since, and we declare where it may connect.* Community templates
carry none of those claims — they are distributed, not certified.

## Certification (official tier)

1. **Human first review.** A brand-new official id is never auto-blessed; a
   maintainer reviews the exact file contents and records the review, which
   binds it to the content sha256.
2. **CI hash tracking.** After that, green master re-binds the hash on every
   content change: `step-validate` (schema), `lint_runs` (malice
   heuristics), and the egress baseline must all pass.
3. **Egress baseline.** Each official template declares where it may connect:
   literal hosts as an upper bound, and every network-touching input listed
   exactly. Changing the baseline is part of review — the file is the
   reviewed record, not configuration.

Community templates pass the same mechanical hygiene (schema validity and
lint heuristics) because broken templates pollute the index — but hygiene is
not certification, and the org records no review for them.

## Egress baseline: scope equals vouching scope

The egress baseline is the org's **vouching artifact**: it declares where
official templates may send data (credentials flow through these templates as
environment variables, so an undeclared `curl` is an exfiltration channel).
The enforcement loop in `scripts/egress.py` therefore covers exactly the ids
the org vouches for — `buz/*` — and skips everything else.

Community templates are **not "exempt"**: exemption implies the rules apply
to them and a waiver was granted. They are **out of scope** — the baseline's
subject is certified content, and community content was never in it. The
marketplace cannot review third-party code against a baseline it does not
control, and pretending otherwise (baseline entries for unreviewed code)
would manufacture false endorsement.

What installers still get for community templates: the same static analysis
runs on them, and the resulting network-endpoint report is visible in CI
logs and the site tooling — informational, not a guarantee.

## The ssh engine

`engine: ssh` was originally excluded from marketplace templates entirely,
for four reasons that remain true individually:

1. **Blast radius.** `shell`/`docker` steps run on the Runner — an
   environment the installer already controls, with containers that are
   discarded after execution. `ssh` steps run on long-lived target hosts —
   databases, services, data.
2. **Shared trust.** The marketplace is meant to be shareable. A community
   author's code executing on someone else's production hosts would make the
   marketplace a distribution channel for arbitrary remote execution.
3. **Validation limits.** `shell`/`docker` behavior is bounded by the
   contract (workspace in, artifacts out), so static validation is
   meaningful. `ssh` behavior depends on each target host's state — distro,
   existing services, compose files — which no marketplace CI can prove.
4. **YAML-first boundary.** Host-specific orchestration (paths, service
   names, compose files) is what Pipeline YAML is for; portable capabilities
   are what plugins are for.

### The decision

The restriction is now tiered instead of absolute:

- **Official `ssh` templates are allowed**, because for them the trust
  triangle closes: author = reviewer = operator of the target hosts. They
  carry the full official controls **plus** ssh-specific ones:
  - `requires_buz` is declared (contract version gate);
  - the egress baseline declares `host` as an endpoint input;
  - run blocks validate absolute paths and stay within their stated scope;
  - human first review covers the deploy semantics, not just syntax.
- **Community `ssh` templates are allowed as unmanaged**: no certification,
  no egress baseline, clearly badged as community + ssh. They execute on
  whatever host the installer's pipeline points at — **the installer is the
  reviewer**. Install one only after reading its source.

`type: host` template inputs remain rejected for all marketplace templates:
the target host is chosen by the pipeline step (`host:`), never by template
content.

## Compatibility tracking

Official templates declare `requires_buz` when they depend on a minimum Buz
release. Plugins CI validates against a real `buz-manager` release — the
`BUZ_VERSION` repository variable selects one; unset (the default) tracks
the latest release. A Buz release that changes the spec schema or this
contract surfaces as a failing plugins build instead of a runtime break.

## Guidance for installers

- Official templates: the badge and the hash bind what you run to what was
  reviewed. Still point `host:` only at hosts you intend the step to touch.
- Community templates: you are the reviewer. Read the source, check the
  egress report, and prefer official equivalents for anything touching
  production.
- Report problems with any template via the issue tracker — the review
  record is bound to content, so a fix is a new hash, not a silent edit.

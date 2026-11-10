# Frozen Python reference implementations

These scripts were the original generators for the catalog manifests. They
have been replaced by `buz-plugin` subcommands and are **not used by CI any
more**:

| frozen file | replaced by |
|---|---|
| `gen_index.py` | `buz-plugin index` |
| `gen_revision.py` | `buz-plugin revision` |
| `gen_reviews.py` | `buz-plugin reviews` |
| `check_release_index.py` | `buz-plugin check-release` |
| `check_manifest_consistency.py` | `buz-plugin check-manifests` |
| `check_plugin_readmes.py` | `buz-plugin check-readmes` |
| `manifest_drift.py` | retired — `reviews --auto` is byte-stable while content is unchanged, so `reconcile-manifests` can trust `git status` |

They are kept only as a readable reference for the exact output contract
(field order, sorting, byte-stable regeneration). Do not edit them to "fix"
the pipeline: the Rust implementation is the single source of truth, and the
`validate` job runs `buz-plugin index --check` against the committed
manifests.

Why one implementation: the `2026.11.10` snapshot was signed by a pinned
`buz-plugin` that predated the `deprecations.json` overlay. Two generators
with different field support produced two "same catalog" artifacts — the
release lost its `deprecated` markers and advanced `sequence` 4 → 5 while the
site and the git copy disagreed. `buz-plugin check-release` now refuses that
class of drift before anything is signed.

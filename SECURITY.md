# Security Policy — Step Templates

**English below / 中文见下方。**

This is the security policy for **step templates** in this repository. For
vulnerabilities in Buz itself (manager, runner, dashboard), see the
[security policy of the buz repository](https://github.com/schiplat/buz/blob/master/SECURITY.md).

## Reporting a malicious or suspicious template

**Please do not report suspected backdoors or malicious behavior through
public issues** — public details give a malicious author time to react.

Use GitHub **Private vulnerability reporting**:
<https://github.com/schiplat/buz-plugins/security/advisories/new>

Include: the template id@version, the content sha256 (from index.json or
your provenance records), and what behavior looked suspicious (unexpected
network destinations, obfuscated code, data leaving the host).

## What to expect

- **First response within 7 days** (holidays may add delay).
- Triage outcomes:
  - **Benign** → closed, with an explanation.
  - **Fixable** → author PR with a version bump (the content hash changes,
    so the review badge auto-invalidates until re-reviewed).
  - **Violating** → template **removed from the index** (takedown), a note
    published, and — when applicable — the author blocked.

## Review trust model

The "Reviewed" badge is a **point-in-time check** of the exact content
sha256: static validation, heuristic lint, declared-outbound-endpoint
review, and manual sign-off at that hash. It is **not** a runtime-safety
guarantee — pin templates with `@sha256:` and review the declared outbound
endpoints before adopting a template in production.

## Safe harbor

Good-faith security research is authorized: we will not pursue legal action
against anyone who reports vulnerabilities responsibly, avoids privacy
violations and service disruption, and gives us reasonable time to fix
issues before public disclosure.

## 中文 / Chinese

**疑似后门/恶意模板请勿公开贴细节**——使用
[Private vulnerability reporting](https://github.com/schiplat/buz-plugins/security/advisories/new)
私下提交（模板 id@版本 + 内容 sha256 + 可疑行为描述）。维护者 7 天内首次响应，
私下分诊；处置后发布说明。"已审核"徽标为时间点检查，不构成运行时安全保证。

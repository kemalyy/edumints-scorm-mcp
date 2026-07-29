# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report privately via one of:
- GitHub **[private vulnerability reporting](../../security/advisories/new)** (preferred), or
- email **security@edumints.com**.

Include a description, steps to reproduce, affected version/commit, and impact if known. We aim to
acknowledge reports within a few business days and will keep you informed of progress.

## Scope notes for self-hosters

This is a self-hostable server. When you deploy it, **you** are responsible for its security posture:

- **Secrets** (API keys, OAuth/IdP credentials) belong in environment variables, never in the repo.
  Only `.env.example` is tracked; real `.env` is gitignored.
- **Network ingress (SSRF):** `add_asset` fetches remote URLs server-side; the project includes SSRF
  guards (internal IPs blocked, redirects re-checked, size/mime limits). Keep them enabled and put the
  server behind appropriate network controls.
- **HTML sanitization:** all `*_html` inputs are sanitized (allowlist). Don't disable it.
- **Resource limits:** the cost guardrails (quotas, TTLs, build timeouts) protect against abuse —
  tune them for your environment.
- **Auth:** the server supports API-key and OAuth flows; protect your endpoint and rotate keys.

## Provenance: what is (and is not) an official artifact

Official artifacts of this project are **only**:

- Source code in **https://github.com/kemalyy/edumints-scorm-mcp** (and the authoring skill at
  **https://github.com/kemalyy/edumints-scorm-skill**).
- The container image **`ghcr.io/kemalyy/edumints-scorm-mcp`**, published exclusively by this
  repository's `release.yml` workflow from tagged releases. Image attestation (signed provenance)
  is planned.
- The hosted service at **https://scorm.edumints.com** (MCP endpoint `/mcp`) with its account
  portal **https://mcp.edumints.com**.

We publish **no PyPI or npm packages today**. Treat any package on any registry claiming to be
this project as an impostor unless the README explicitly says otherwise.

## Reporting lookalike repos and impostor packages

Cloned/renamed repositories, re-uploaded zips, typosquatted packages or domains that impersonate
this project are a supply-chain risk to users. We have previously had a lookalike repository
removed through the platform's impersonation/takedown process and will pursue the same route
again. If you spot one, report it via the channels above (a public issue is fine for lookalikes
when no vulnerability details are involved) — include the URL and, if possible, what it copies.

## Supported versions

Security fixes target the latest tagged release (currently the 1.x line) and `main`. Older tags
receive no backports; please upgrade to the latest release.

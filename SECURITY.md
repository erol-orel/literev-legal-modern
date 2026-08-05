# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** — do not open a public
issue. Use GitHub's [private vulnerability reporting][gh-advisory] (the
repository's **Security → Report a vulnerability** tab) so a fix can be prepared
before disclosure. We aim to acknowledge reports within a few business days.

[gh-advisory]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability

## Secret management

**No secret value is ever committed to this repository.** Credentials are
injected at runtime from two places only:

| Where it runs | Where secrets come from |
|---|---|
| Local development | a git-ignored `.env` file (copy `.env.tpl` and fill it in) |
| CI / GitHub Actions | repository **Actions secrets** referenced as `${{ secrets.NAME }}` |
| Production / deploy | the deployment environment's secret store / `.env` |

### Required secrets

Set these as **Actions secrets** (Settings → Secrets and variables → Actions)
and in your local `.env`:

| Name | Used for |
|---|---|
| `OPENAI_API_KEY` | embeddings + RAG answers (or use the Hactar provider) |
| `ES_PASSWORD` | Elasticsearch corpus basic-auth |
| `POSTGRES_PASSWORD_LITEREV` | application database role (deploy only) |
| `REDIS_PASSWORD` | Celery broker (generated locally by `makim containers.redis-setup`) |

Set one from the CLI, for example:

```bash
gh secret set OPENAI_API_KEY --repo <owner>/<repo>
gh secret set ES_PASSWORD    --repo <owner>/<repo>
```

Never paste a secret into a source file, a workflow `env:` block, a commit
message, or an issue/PR comment.

## Automated protections in this repository

- **Secret scanning** — `gitleaks` runs on every push and pull request
  (`.github/workflows/secret-scan.yaml`) and as a local pre-commit hook, so a
  secret is blocked before it can be committed or merged. Configuration and the
  allowlist for non-secret placeholders live in `.gitleaks.toml`.
- **Static analysis (SAST)** — `bandit` runs over the Python code via
  pre-commit.
- **Dependency updates** — Dependabot (`.github/dependabot.yml`) opens weekly
  PRs for pip, npm, GitHub Actions and Docker base images.
- **`.gitignore`** blocks `.env*` (except the template) and common credential
  file types (`*.key`, `*.pem`, `*.p12`, `service-account*.json`, …).

We recommend also enabling, in the repository settings, GitHub's native
**secret scanning with push protection** and **Dependabot security updates**.

## Credential rotation notice

Earlier revisions of the upstream project shipped a hardcoded PostgreSQL
password in source and CI. It has been removed and parameterised from the
environment. If any deployment still uses that value — or the shared
Elasticsearch password that was distributed via CI — **rotate it**, since it was
previously committed and must be treated as compromised.

# Deployment & Operations

---

## Production Deployment

Use the Makim task to bring up the full production stack, including Jupyter (required for the Nginx `/jupyter/` upstream):

```bash
makim deploy-production.all-containers
```

**What this does:**

1. Starts **Jupyter** (using the `dev` profile) so the upstream `literev-jupyter` resolves
2. Builds & restarts the **essential prod containers** (using the `prod` profile)

**Verify:**

```bash
# Prod services
sugar --profile prod compose ps

# Jupyter (dev profile)
sugar --profile dev compose ps literev-jupyter
```

**Notes:**

- Jupyter must run with a base URL of `/jupyter/` to work behind Nginx.

---

## Database Backup & Restore

### Create a dump

Generates a gzipped dump (via `pg_dumpall`) inside the Postgres container and writes it to the provided path:

```bash
makim containers.postgres-dump-database \
  --path /opt/data/literev/backup
```

**Output:**

```
/opt/data/literev/backup/<dump-name>.sql.gz
```

### Restore a dump

Provide the same path and file name used during backup. Use `--drop-all true` to drop roles and databases before restoring (destructive — use with care):

```bash
makim containers.postgres-restore-database \
  --path /opt/data/literev/backup \
  --dump-name "literev-legal-<dd-mm-yy_HH-MM>.sql.gz" \
  --drop-all true
```

---

## SSL Certificates

SSL is managed by Certbot. Set these in `.env`:

```env
CERTBOT_DOMAIN=myapp.domain.com
CERTBOT_EMAIL=myapp@gmail.com
CERTBOT_CONF=./containers/nginx/data/certbot/conf
CERTBOT_WWW=./containers/nginx/data/certbot/www
```

Then run the Certbot container from the Nginx compose profile to issue or renew certificates.

---

## Production Hardening Checklist

- `DEBUG=False` in production
- `DJANGO_SECRET_KEY` must be a long random string (never the dev default)
- `ALLOWED_HOSTS` set to the actual domain
- HSTS + secure cookies enabled via `prod.py`
- Redis ACL rules limiting access to broker data (`makim containers.redis-setup`)
- Sentry DSN set for error tracking (`SENTRY_DSN`)
- Certbot-managed SSL certificates
- `bandit` security scanning in pre-commit hooks

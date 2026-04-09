# Containers

LiteRev-Legal uses [sugar](https://github.com/osl-incubator/sugar) and [makim](https://github.com/osl-incubator/makim) to manage Docker Compose services. `sugar` wraps `docker compose` with profile support; `makim` provides higher-level task automation via `.makim.yaml`.

---

## Building and Starting Services

These steps bring all services up locally:

```bash
# 1. One-time host setup (creates required directories, sets permissions)
makim containers.host-setup

# 2. Build all images
sugar compose build

# 3. Apply database migrations
makim django.migrate

# 4. Start all services
sugar compose-ext restart
```

To start in detached mode (non-blocking):

```bash
sugar compose-ext restart -- -d
```

To restart a single service:

```bash
sugar compose-ext restart --services literev-postgres -- -d
```

Check all available makim tasks:

```bash
makim --help
```

---

## Compose Profiles

| Profile | Purpose |
|---------|---------|
| `dev` | Local development (includes Jupyter) |
| `prod` | Production stack |

```bash
# Status of prod services
sugar --profile prod compose ps

# Status of a specific dev service
sugar --profile dev compose ps literev-jupyter
```

---

## Redis Credentials Setup

Run this once to generate a strong Redis password, write the ACL config, and sync `REDIS_PASSWORD` in `.env`:

```bash
makim containers.redis-setup
```

**What this creates:**

- `containers/redis/config/redis.pass` — generated password
- `containers/redis/config/redis.conf` — ACL rules for the `app` user
- Updates `./.env` with the matching `REDIS_PASSWORD`

If your host drops inter-container traffic to port 6379 via `DOCKER-USER`, add an allow rule limited to the project's Docker bridge:

```bash
# With cached sudo (no prompt):
sudo -v && makim containers.redis-setup --set-iptables

# Pass the password explicitly:
makim containers.redis-setup --set-iptables --sudo-password 'yourpass'

# Via env (keeps CLI args cleaner):
SUDO_PASSWORD='yourpass' makim containers.redis-setup --set-iptables
```

The iptables script uses cached sudo if available, otherwise reads `SUDO_PASSWORD`. If neither is available it skips the rule and prints a warning.

---

## Running Without Containers

Set these in `.env` to run services locally (no Docker):

```env
USE_CONTAINER=False
POSTGRES_HOST=localhost
```

Then point Redis to your local instance and start Django directly:

```bash
makim django.runserver --local
```

---

## Celery Worker

See [celery.md](celery.md) for full configuration. Quick start:

```bash
# Development (local)
makim containers.start-celery

# Or directly
celery -A config.celery worker --loglevel=info --pool=prefork --concurrency=4
```

---

## Django Application

```bash
# Start the Django dev server (inside container)
makim django.runserver

# Start locally (outside container)
makim django.runserver --local

# Create a superuser
makim django.create-superuser \
  --username dev \
  --password dev \
  --email dev@literev.com

# Open Django shell
makim django.shell

# Apply migrations
makim django.migrate
```

---

## Running Django with Jupyter

[Django Extensions](https://github.com/django-extensions/django-extensions) allow running the project inside a Jupyter notebook.

1. Ensure `POSTGRES_HOST=localhost` is set in `.env`
2. Load environment variables:
   ```bash
   export $(cat .env)
   ```
3. Start the notebook server:
   ```bash
   python src/manage.py shell_plus --notebook
   # or:
   makim django.notebook
   ```

Store experimental notebooks at `docs/notebooks/`.

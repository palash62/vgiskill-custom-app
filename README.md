# Frappe Learning (LMS) – Dev setup

Docker-based setup for [Frappe LMS](https://github.com/palash62/official-lms) with optional custom apps. Use your team fork and branches for multi-developer work.

## Quick start

```bash
# From this directory (frappe-learning)
docker compose up -d
```

- **Site:** http://lms.localhost:8000  
- **LMS app:** http://lms.localhost:8000/lms  
- **Login:** Administrator / `admin`

## Layout

- **frappe-learning/** – This repo: `docker-compose.yml`, `init.sh`, `README.md`.
- **frappe-custom-apps/** – Sibling folder for custom Frappe apps (e.g. `vgiskill_custom_app`). Must sit next to `frappe-learning` so the relative volume `../frappe-custom-apps` works.

## Configuration (environment)

| Variable       | Default                               | Description |
|----------------|----------------------------------------|-------------|
| `LMS_REPO`     | `https://github.com/palash62/official-lms` | LMS Git URL (your fork). |
| `LMS_BRANCH`   | `develop`                             | Branch to clone/pull (e.g. `develop` or a feature branch). |
| `CUSTOM_APPS`  | `vgiskill_custom_app`                 | Comma-separated custom app names under `frappe-custom-apps/`. |

Set these under `frappe` → `environment` in `docker-compose.yml`, or in a `.env` file in this directory.

## Multi-developer workflow

1. Create branches on your fork (e.g. `palash_branch`, `feature/xyz`).
2. Set `LMS_BRANCH` to that branch in `docker-compose.yml` to run it locally.
3. Push and open PRs; others clone the same fork and work on the same branch (pull before push).

## Useful commands

```bash
# Rebuild and restart (e.g. after changing LMS_BRANCH or CUSTOM_APPS)
docker compose up -d --force-recreate

# Shell into the bench container
docker compose exec frappe bash
```

## References

- Team LMS fork: [palash62/official-lms](https://github.com/palash62/official-lms)  
- Upstream: [frappe/lms](https://github.com/frappe/lms)  
- Frappe Learning: [frappe.io/learning](https://frappe.io/learning)

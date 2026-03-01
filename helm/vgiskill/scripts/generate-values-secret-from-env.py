#!/usr/bin/env python3
"""Read .env (from frappe-learning or current dir) and write helm/vgiskill/values-secret.yaml."""
import os
import re
from pathlib import Path

def load_dotenv(path):
    env = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1].replace('\\"', '"')
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                env[key] = val
    return env

def main():
    script_dir = Path(__file__).resolve().parent
    chart_dir = script_dir.parent
    repo_root = chart_dir.parent.parent

    # Prefer .env in frappe-learning, then chart dir, then repo root
    for base in [repo_root / "frappe-learning", chart_dir, repo_root]:
        env_file = base / ".env"
        if env_file.is_file():
            env = load_dotenv(env_file)
            break
    else:
        print("No .env found. Create frappe-learning/.env or helm/vgiskill/.env")
        return 1

    db_host = env.get("DB_HOST", "10.30.0.2")
    db_port = env.get("DB_PORT", "3306")
    db_name = env.get("DB_NAME", "lms_db")
    db_user = env.get("DB_USER", "vgi_skill")
    db_password = env.get("DB_PASSWORD", env.get("MYSQL_ROOT_PASSWORD", ""))

    site_admin = env.get("SITE_ADMIN_PASSWORD", "admin")

    yaml = f"""# Generated from .env - do not commit
frappe:
  siteAdminPassword: "{site_admin}"

  db:
    host: "{db_host}"
    port: {db_port}
    name: "{db_name}"
    user: "{db_user}"
    password: "{db_password}"
"""
    out = chart_dir / "values-secret.yaml"
    out.write_text(yaml, encoding="utf-8")
    print(f"Wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

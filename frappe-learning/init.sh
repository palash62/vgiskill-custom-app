#!/bin/bash

set -e

BENCH_DIR="/home/frappe/frappe-bench"



# PYTHONPATH: add each custom app root so "import vgiskill_custom_app" finds the inner package (e.g. hooks.py)
if [ -n "${CUSTOM_APPS_PATH}" ] && [ -d "${CUSTOM_APPS_PATH}" ]; then
  CUSTOM_PYTHONPATH=""
  IFS=',' read -ra APPS <<< "${CUSTOM_APPS}"
  for app in "${APPS[@]}"; do
    app_trimmed="$(echo "${app}" | xargs)"
    [ -z "${app_trimmed}" ] && continue
    [ -d "${CUSTOM_APPS_PATH}/${app_trimmed}" ] && CUSTOM_PYTHONPATH="${CUSTOM_APPS_PATH}/${app_trimmed}:${CUSTOM_PYTHONPATH}"
  done
  [ -n "${CUSTOM_PYTHONPATH}" ] && export PYTHONPATH="${CUSTOM_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"
fi

# Add existing site (external DB) and run bench migrate instead of bench new-site
add_existing_site_and_migrate() {
  local site="${1:-lms.localhost}"
  local site_dir="${BENCH_DIR}/sites/${site}"
  mkdir -p "${site_dir}"
  mkdir -p "${site_dir}/logs"
  mkdir -p "${site_dir}/public/files"
  mkdir -p "${site_dir}/files"
  # Create site_config.json for existing external DB
  cat > "${site_dir}/site_config.json" << EOF
{
  "db_host": "${DB_HOST}",
  "db_name": "${DB_NAME}",
  "db_password": "${DB_PASSWORD}",
  "db_port": ${DB_PORT:-3306},
  "db_type": "mariadb",
  "db_user": "${DB_USER}"
}
EOF
  echo "Created site_config.json for existing DB ${DB_NAME}"
  # Add site to sites.json if not present
  local sites_json="${BENCH_DIR}/sites/sites.json"
  (cd "${BENCH_DIR}" && python3 -c "
import json
try:
    with open('sites/sites.json') as f:
        sites = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    sites = []
if '${site}' not in sites:
    sites.append('${site}')
    with open('sites/sites.json','w') as f:
        json.dump(sites, f)
    print('Added ${site} to sites.json')
")
  bench --site "${site}" migrate
  echo "bench migrate completed for ${site}"
}

# Helper: install/link custom apps from CUSTOM_APPS and install them on the site (so APIs work).
install_custom_apps() {
  local site="${1:-lms.localhost}"
  if [ -z "${CUSTOM_APPS}" ]; then
    return
  fi

  IFS=',' read -ra APPS <<< "${CUSTOM_APPS}"
  for app in "${APPS[@]}"; do
    app_trimmed="$(echo "${app}" | xargs)"
    if [ -z "${app_trimmed}" ]; then
      continue
    fi
    CUSTOM_APP_SRC="/home/frappe/custom-apps/${app_trimmed}"
    APP_TARGET="${BENCH_DIR}/apps/${app_trimmed}"

    if [ -d "${CUSTOM_APP_SRC}" ]; then
      if [ ! -e "${APP_TARGET}" ]; then
        echo "Copying custom app ${CUSTOM_APP_SRC} into bench at ${APP_TARGET} (writable for pip install)"
        cp -a "${CUSTOM_APP_SRC}" "${APP_TARGET}"
      fi
      echo "Installing Python package for custom app: ${app_trimmed}"
      if ! uv pip install --quiet --upgrade -e "${APP_TARGET}" --python "${BENCH_DIR}/env/bin/python" 2>/dev/null; then
        "${BENCH_DIR}/env/bin/pip" install --quiet --upgrade -e "${APP_TARGET}" 2>/dev/null || echo "pip install failed for ${app_trimmed} (PYTHONPATH will be used)"
      fi
      # Add app to sites/apps.txt so bench install-app can run (Frappe requires this)
      APPS_TXT="${BENCH_DIR}/sites/apps.txt"
      if [ -f "${APPS_TXT}" ]; then
        # Fix corrupted line if app was appended without newline (e.g. "lmsvgiskill_custom_app")
        if grep -q "lmsvgiskill_custom_app" "${APPS_TXT}"; then
          sed -i 's/lmsvgiskill_custom_app/lms\nvgiskill_custom_app/' "${APPS_TXT}" || true
          echo "Fixed apps.txt (split lms and vgiskill_custom_app)"
        fi
        if ! grep -q "^${app_trimmed}$" "${APPS_TXT}"; then
          # Ensure file ends with newline so app is on its own line
          [ -s "${APPS_TXT}" ] && [ "$(tail -c1 "${APPS_TXT}" | wc -l)" -eq 0 ] && echo >> "${APPS_TXT}"
          echo "${app_trimmed}" >> "${APPS_TXT}"
          echo "Added ${app_trimmed} to apps.txt"
        fi
      fi
      echo "Installing custom app on site: ${app_trimmed}"
      (cd "${BENCH_DIR}" && bench --site "${site}" install-app "${app_trimmed}") || echo "Warning: install-app ${app_trimmed} failed (may already be installed)"
    else
      echo "Custom app source directory ${CUSTOM_APP_SRC} not found, skipping"
    fi
  done
}

# If bench already exists, update apps from Git and start it.
if [ -d "${BENCH_DIR}/apps/frappe" ]; then
    echo "Bench already exists, updating apps from Git and starting bench"
    cd "${BENCH_DIR}"

    # If venv has broken paths (e.g. after temp-dir move), fix shebangs then reinstall apps
    if ! ./env/bin/python -c "import frappe" 2>/dev/null; then
      echo "Fixing venv (shebangs and paths)..."
      # Fix shebangs in env/bin that still point to frappe-bench-tmp
      for f in env/bin/*; do [ -f "$f" ] && sed -i 's|frappe-bench-tmp|frappe-bench|g' "$f" 2>/dev/null; done
      if ./env/bin/pip --version >/dev/null 2>&1; then
        ./env/bin/pip install -e apps/frappe
        for app_dir in apps/*/; do
          [ -d "${app_dir}" ] || continue
          [ "$(basename "${app_dir}")" = "frappe" ] && continue
          ./env/bin/pip install -e "${app_dir}" 2>/dev/null || true
        done
      else
        echo "Recreating venv..."
        rm -rf env
        python3 -m venv env
        ./env/bin/pip install --upgrade pip
        ./env/bin/pip install -e apps/frappe
        for app_dir in apps/*/; do
          [ -d "${app_dir}" ] || continue
          [ "$(basename "${app_dir}")" = "frappe" ] && continue
          ./env/bin/pip install -e "${app_dir}" 2>/dev/null || true
        done
      fi
    fi

    # If site lms.localhost does not exist, add existing DB and migrate (prefer bench migrate over new-site)
    if [ ! -f "${BENCH_DIR}/sites/lms.localhost/site_config.json" ]; then
      bench set-mariadb-host "${DB_HOST:-mariadb}"
      bench set-redis-cache-host "${REDIS_CACHE:-redis://redis:6379}"
      bench set-redis-queue-host "${REDIS_QUEUE:-redis://redis:6379}"
      bench set-redis-socketio-host "${REDIS_SOCKETIO:-redis://redis:6379}"
      if [ -n "${DB_NAME}" ] && [ -n "${DB_USER}" ]; then
        echo "Site lms.localhost not found, adding existing DB and running bench migrate..."
        add_existing_site_and_migrate lms.localhost
      else
        echo "Site lms.localhost not found, creating with bench new-site (internal mariadb)..."
        bench new-site lms.localhost --force --mariadb-root-password "${DB_PASSWORD:-123}" --admin-password admin --no-mariadb-socket
      fi
      bench --site lms.localhost install-app lms
      bench --site lms.localhost install-app payments
      install_custom_apps lms.localhost
      bench --site lms.localhost set-config developer_mode 1
      bench --site lms.localhost clear-cache
      bench use lms.localhost
      if [ -n "${SITE_HOST}" ]; then
        bench --site lms.localhost set-config host_name "${SITE_HOST}"
        bench --site lms.localhost clear-cache
        echo "Set site host_name to ${SITE_HOST}"
      fi
    fi

    # Ensure site responds to SITE_HOST when set (e.g. lab.vgiskill.ai in K8s)
    if [ -n "${SITE_HOST}" ]; then
      bench --site lms.localhost set-config host_name "${SITE_HOST}"
      bench --site lms.localhost clear-cache
    fi
    mkdir -p "${BENCH_DIR}/sites/lms.localhost/public/files"
    mkdir -p "${BENCH_DIR}/sites/lms.localhost/files"
    # Default site for unmatched Host (e.g. GCE health check) so backend stays HEALTHY
    bench set-config -g default_site lms.localhost

    # Ensure payments app is in bench (get-app is no-op if already present)
    if [ ! -d "${BENCH_DIR}/apps/payments" ]; then
      echo "Adding Payments app (https://github.com/frappe/payments)"
      bench get-app https://github.com/frappe/payments || true
    fi
    (cd "${BENCH_DIR}" && bench --site lms.localhost install-app payments) || true

    # Update LMS app from your GitHub fork clone mounted at apps/lms
    if [ -d "${BENCH_DIR}/apps/lms/.git" ]; then
      echo "Pulling latest LMS code from origin/develop"
      cd "${BENCH_DIR}/apps/lms"
      git pull origin develop || echo "Warning: git pull for LMS failed"
      cd "${BENCH_DIR}"
    fi

    # Rebuild assets so frontend changes are reflected
    bench build || echo "Warning: bench build failed"

    install_custom_apps lms.localhost
    bench start
    exit 0
fi

echo "Creating new bench..."

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

# If PVC mount exists but no full bench (empty or incomplete), init to temp dir then move into PVC
if [ -d "${BENCH_DIR}" ] && [ ! -d "${BENCH_DIR}/apps/frappe" ]; then
  echo "Empty or incomplete bench on PVC; initializing to temp then moving..."
  (cd "${BENCH_DIR}" && rm -rf .[!.]* * 2>/dev/null) || true
  cd /home/frappe
  bench init --skip-redis-config-generation frappe-bench-tmp
  for f in frappe-bench-tmp/*; do [ -e "$f" ] && mv "$f" "${BENCH_DIR}/"; done
  for f in frappe-bench-tmp/.[!.]*; do [ -e "$f" ] && mv "$f" "${BENCH_DIR}/"; done
  rmdir frappe-bench-tmp 2>/dev/null || rm -rf frappe-bench-tmp
  cd "${BENCH_DIR}"
  # Venv was created in temp dir; fix shebangs in env/bin then reinstall apps
  for f in env/bin/*; do [ -f "$f" ] && sed -i 's|frappe-bench-tmp|frappe-bench|g' "$f" 2>/dev/null; done
  ./env/bin/pip install -e apps/frappe
  for app_dir in apps/*/; do
    [ -d "${app_dir}" ] || continue
    name="$(basename "${app_dir}")"
    [ "$name" = "frappe" ] && continue
    ./env/bin/pip install -e "${app_dir}" 2>/dev/null || true
  done
else
  cd /home/frappe
  bench init --skip-redis-config-generation "$(basename "${BENCH_DIR}")"
  cd "${BENCH_DIR}"
fi

# Use containers instead of localhost
bench set-mariadb-host "${DB_HOST:-mariadb}"
bench set-redis-cache-host "${REDIS_CACHE:-redis://redis:6379}"
bench set-redis-queue-host "${REDIS_QUEUE:-redis://redis:6379}"
bench set-redis-socketio-host "${REDIS_SOCKETIO:-redis://redis:6379}"

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

# Get the LMS app from your GitHub fork instead of the default upstream repo
# You can change the branch (e.g. --branch main) if needed
#bench get-app https://github.com/palash62/official-lms --branch palash_frappe
bench get-app https://github.com/VariPhiGen/official-frappe-lms.git --branch vgiskill-develop
# Payments app: https://github.com/frappe/payments
bench get-app https://github.com/frappe/payments

# Add existing site and run bench migrate, or bench new-site for internal mariadb
if [ -n "${DB_NAME}" ] && [ -n "${DB_USER}" ]; then
  echo "Adding existing DB and running bench migrate..."
  add_existing_site_and_migrate lms.localhost
else
  echo "Creating site with bench new-site (internal mariadb)..."
  bench new-site lms.localhost --force --mariadb-root-password "${DB_PASSWORD:-123}" --admin-password admin --no-mariadb-socket
fi

bench --site lms.localhost install-app lms
bench --site lms.localhost install-app payments

# Install any custom apps that have been mounted into the bench and listed via CUSTOM_APPS
install_custom_apps lms.localhost

bench --site lms.localhost set-config developer_mode 1
bench --site lms.localhost clear-cache
bench use lms.localhost
if [ -n "${SITE_HOST}" ]; then
  bench --site lms.localhost set-config host_name "${SITE_HOST}"
  bench --site lms.localhost clear-cache
  echo "Set site host_name to ${SITE_HOST}"
fi
if [ "${FORCE_HTTPS}" = "1" ]; then
  bench --site lms.localhost set-config force_https 1
  bench --site lms.localhost clear-cache
  echo "Set force_https=1"
fi
bench set-config -g default_site lms.localhost

bench start

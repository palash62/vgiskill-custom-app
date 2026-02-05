#!/bin/bash

set -e

BENCH_DIR="/home/frappe/frappe-bench"

# Helper: install/link any custom apps listed in CUSTOM_APPS.
install_custom_apps() {
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
        echo "Linking custom app source ${CUSTOM_APP_SRC} into bench at ${APP_TARGET}"
        ln -s "${CUSTOM_APP_SRC}" "${APP_TARGET}"
      fi
      echo "Installing Python package for custom app: ${app_trimmed}"
      uv pip install --quiet --upgrade -e "${APP_TARGET}" --python "${BENCH_DIR}/env/bin/python" || echo "Failed to install Python package for app: ${app_trimmed}"
    else
      echo "Custom app source directory ${CUSTOM_APP_SRC} not found, skipping"
    fi
  done
}

# If bench already exists, update apps from Git and start it.
if [ -d "${BENCH_DIR}/apps/frappe" ]; then
    echo "Bench already exists, updating apps from Git and starting bench"
    cd "${BENCH_DIR}"

    # Update LMS app from your GitHub fork clone mounted at apps/lms
    if [ -d "${BENCH_DIR}/apps/lms/.git" ]; then
      echo "Pulling latest LMS code from origin/develop"
      cd "${BENCH_DIR}/apps/lms"
      git pull origin develop || echo "Warning: git pull for LMS failed"
      cd "${BENCH_DIR}"
    fi

    # Rebuild assets so frontend changes are reflected
    bench build || echo "Warning: bench build failed"

    install_custom_apps
    bench start
    exit 0
fi

echo "Creating new bench..."

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

cd /home/frappe

bench init --skip-redis-config-generation "$(basename "${BENCH_DIR}")"

cd "${BENCH_DIR}"

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

# Get the LMS app from your GitHub fork instead of the default upstream repo
# You can change the branch (e.g. --branch main) if needed
bench get-app https://github.com/palash62/official-lms --branch develop

bench new-site lms.localhost \
  --force \
  --mariadb-root-password 123 \
  --admin-password admin \
  --no-mariadb-socket

bench --site lms.localhost install-app lms

# Install any custom apps that have been mounted into the bench and listed via CUSTOM_APPS
install_custom_apps

bench --site lms.localhost set-config developer_mode 1
bench --site lms.localhost clear-cache
bench use lms.localhost

bench start

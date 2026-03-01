# Build from repo root: docker build -f frappe-learning/Dockerfile -t vgiskill-custom-app:latest .
FROM frappe/bench:latest
COPY frappe-learning/init.sh /workspace/init.sh
COPY frappe-custom-apps /home/frappe/custom-apps
ENV CUSTOM_APPS=vgiskill_custom_app
ENV CUSTOM_APPS_PATH=/home/frappe/custom-apps
ENV NODE_OPTIONS=--max_old_space_size=2048
ENTRYPOINT ["bash", "/workspace/init.sh"]

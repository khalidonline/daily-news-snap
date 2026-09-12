FROM python:3.12-slim

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --chown=10001:10001 publishing_v2/ publishing_v2/
COPY --chown=10001:10001 evaluation/event_packages.json evaluation/failure_cases.json evaluation/
USER 10001
ENTRYPOINT ["python", "-m", "publishing_v2.cloud_smoke"]

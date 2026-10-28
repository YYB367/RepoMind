ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
COPY requirements.txt /opt/repomind-test-requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r /opt/repomind-test-requirements.txt
COPY test_runner.py /opt/repomind-test-runner.py
USER 65532:65532
WORKDIR /workspace
ENTRYPOINT ["python"]

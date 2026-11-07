ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER 0:0
COPY requirements.txt /opt/repomind-v42-requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r /opt/repomind-v42-requirements.txt
USER 65532:65532

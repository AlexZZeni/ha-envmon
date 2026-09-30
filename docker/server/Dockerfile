# syntax=docker/dockerfile:1

# Python 3.11 é a versão do Raspberry Pi OS bookworm: o piwheels tem wheels ARM
# prontas para ela, o que evita compilar tudo no Pi 3.
ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# O libgpiod_pulsein do Blinka (quem lê o DHT) é estático: o runtime não
# precisa de bibliotecas de sistema extras, só do /dev/gpiochip0.
FROM ${PYTHON_IMAGE}
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY app.py sensors.py ./
EXPOSE 5000
# Roda como root: o acesso a /dev/gpiochip0 depende do GID do host.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3).status != 200)"
CMD ["python", "app.py"]

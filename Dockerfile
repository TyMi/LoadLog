# Weitgehend reproduzierbarer Build: Basis-Images per Digest festgelegt (Dependabot schlägt neue Digests vor),
# Python-Pakete aus backend/uv.lock mit Hashes, npm-Pakete aus package-lock.json (npm ci).

# --- Frontend bauen ---
FROM node:24-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- uv (nur zum Erzeugen der Paketliste aus dem Lock) ---
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

# --- Laufzeit ---
FROM python:3.15-slim@sha256:94d3426f1def7db4a106a232ac121bfd975393e5dfd40a619b955fae45fe7913
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOADLOG_HOST=0.0.0.0 LOADLOG_DATA_DIR=/data LOADLOG_STATIC_DIR=/app/ui LOADLOG_MANUAL_DIR=/app/manual
# Pango/HarfBuzz und Schriften für die PDF-Berichte (WeasyPrint)
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
LABEL org.opencontainers.image.title="LoadLog" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.description="Laborierungs-Journal fuer LabRadar- und GRT-Daten (kein Ladedaten-Rechner)"
WORKDIR /app
COPY backend/ /tmp/backend/
# genau die gelockten Versionen, mit Hashprüfung; danach nur noch das Projekt selbst
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    uv export --project /tmp/backend --frozen --no-dev --no-emit-project --no-header -o /tmp/requirements.txt \
 && pip install --require-hashes -r /tmp/requirements.txt \
 && pip install --no-deps /tmp/backend \
 && rm -rf /tmp/backend /tmp/requirements.txt
COPY --from=ui /ui/dist /app/ui
COPY docs/manual /app/manual
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY licenses /app/licenses
RUN useradd --system --uid 10001 loadlog && mkdir /data && chown loadlog /data
USER loadlog
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4)"
CMD ["python", "-m", "loadlog"]

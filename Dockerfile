ARG PYTHON_IMAGE=python:3.13.11-slim-bookworm
FROM ${PYTHON_IMAGE} AS dependencies
ARG PDM_VERSION=2.29.5
ENV PDM_CHECK_UPDATE=false PDM_USE_VENV=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
# O extra oficial locked fixa também os transitivos da ferramenta (hishel 2 é incompatível).
RUN pip install --no-cache-dir "pdm[locked]==${PDM_VERSION}"
COPY pyproject.toml pdm.lock ./
RUN pdm install --check --prod --no-self --no-editable

FROM ${PYTHON_IMAGE} AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=app.settings.prod \
    PATH="/srv/app/.venv/bin:$PATH" PORT=8000
WORKDIR /srv/app
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app \
    && mkdir -p /srv/private-documents /srv/app/media \
    && chown app:app /srv/private-documents /srv/app/media \
    && chmod 0700 /srv/private-documents
COPY --from=dependencies /srv/app/.venv/ /srv/app/.venv/
COPY app/ ./app/
COPY modules/ ./modules/
COPY shared/ ./shared/
COPY static/ ./static/
COPY scripts/runtime.py scripts/frontend_artifact.py scripts/healthcheck.py ./scripts/
COPY manage.py ./
RUN chmod -R a+rX app modules shared static scripts && chmod a+r manage.py \
    && DJANGO_SETTINGS_MODULE=app.settings.build REDIS_URL= CLOUDINARY_URL= \
    python manage.py collectstatic --noinput \
    && chmod -R a+rX staticfiles
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-m", "scripts.healthcheck"]
CMD ["python", "-m", "scripts.runtime", "web"]

# O target release exige artefato real preparado fora desta imagem. Não baixa branch no startup.
FROM backend AS release
ARG BACKEND_REVISION
ENV BACKEND_REVISION=${BACKEND_REVISION}
USER root
COPY frontend_dist/ ./frontend_dist/
COPY frontend-release.json ./frontend-release.json
RUN chmod -R a+rX frontend_dist && chmod a+r frontend-release.json
USER app
RUN python -m scripts.frontend_artifact verify --root frontend_dist --backend-revision "$BACKEND_REVISION"

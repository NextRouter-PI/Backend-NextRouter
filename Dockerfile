FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PDM_USE_VENV=true \
    PDM_CHECK_UPDATE=false \
    DJANGO_SETTINGS_MODULE=app.settings.prod

WORKDIR /srv/app
ENV PATH="/srv/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pdm

COPY pyproject.toml pdm.lock ./
RUN pdm sync --prod --no-self --no-editable

COPY . .
RUN useradd --system --uid 10001 --create-home app \
    && mkdir -p /srv/app/media /srv/app/private-documents /srv/app/staticfiles \
    && chown -R app:app /srv/app

USER app
EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "app.asgi:application"]

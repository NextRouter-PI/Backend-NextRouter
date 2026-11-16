#!/usr/bin/env bash
# PostgreSQL descartável: nunca reutiliza DATABASE_URL, containers ou volumes existentes.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo 'Instale o Docker para executar este roteiro.' >&2; exit 1; }
command -v pdm >/dev/null || { echo 'PDM não encontrado.' >&2; exit 1; }

if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
    docker_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}' "$DOCKER_CONTEXT")
else
    docker_host="${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}"
fi
if [[ "$docker_host" != unix://* ]]; then
    echo 'Use um daemon Docker local (socket Unix), não um contexto remoto.' >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo 'Docker indisponível. Inicie o daemon local e confira a permissão de acesso.' >&2
    exit 1
fi

container_id=
test_directory=
cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "$container_id" ]]; then
        if ! docker rm --force "$container_id" >/dev/null; then
            echo "Não foi possível remover o container de teste $container_id." >&2
            status=1
        fi
    fi
    if [[ "$test_directory" == /tmp/opencode/nextrouter-postgresql.* ]]; then
        rm -rf -- "$test_directory"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p /tmp/opencode
test_directory=$(mktemp -d /tmp/opencode/nextrouter-postgresql.XXXXXX)
container_id=$(docker run --detach --rm \
    --publish 127.0.0.1::5432 \
    --tmpfs /var/lib/postgresql/data \
    --env POSTGRES_USER=nextrouter_test \
    --env POSTGRES_PASSWORD=local_test_only \
    --env POSTGRES_DB=nextrouter_stage2 \
    postgres:16-alpine)

ready=false
for _ in {1..60}; do
    if docker exec "$container_id" pg_isready -U nextrouter_test -d nextrouter_stage2 >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != true ]]; then
    docker logs "$container_id" >&2
    echo 'PostgreSQL de teste não ficou disponível.' >&2
    exit 1
fi
address=$(docker port "$container_id" 5432/tcp)
port="${address##*:}"
if [[ "$address" != 127.0.0.1:* || ! "$port" =~ ^[0-9]+$ ]]; then
    echo 'Porta local do PostgreSQL de teste inválida.' >&2
    exit 1
fi

export DJANGO_SETTINGS_MODULE=app.settings.dev
export DATABASE_URL="postgresql://nextrouter_test:local_test_only@127.0.0.1:$port/nextrouter_stage2"
export REDIS_URL= GEOCODING_URL= OSRM_URL= EMAIL_HOST= CLOUDINARY_URL=
export SECRET_KEY=chave-exclusiva-dos-testes-locais-postgresql
export PRIVATE_DOCUMENT_ROOT="$test_directory/documents"

pdm run python manage.py shell -c \
    "import django; from django.db import connection; assert connection.vendor == 'postgresql'; connection.ensure_connection(); print('Django:', django.get_version()); print('PostgreSQL:', connection.pg_version)"
pdm run python manage.py migrate --noinput --settings=app.settings.dev
pdm run test "$@" --verbosity=2 --settings=app.settings.dev

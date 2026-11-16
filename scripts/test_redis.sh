#!/usr/bin/env bash
# Redis novo e descartável; nunca usa REDIS_URL herdada ou volumes existentes.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null
command -v pdm >/dev/null
if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
    docker_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}' "$DOCKER_CONTEXT")
else
    docker_host="${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}"
fi
if [[ "$docker_host" != unix://* ]]; then
    echo 'Use somente daemon Docker local por socket Unix.' >&2
    exit 1
fi
docker info >/dev/null 2>&1
container_id=
test_directory=
cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "$container_id" ]]; then
        docker rm --force "$container_id" >/dev/null || status=1
    fi
    if [[ "$test_directory" == /tmp/opencode/nextrouter-redis.* ]]; then
        rm -rf -- "$test_directory"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
test_directory=$(mktemp -d /tmp/opencode/nextrouter-redis.XXXXXX)
container_id=$(docker run --detach --rm --publish 127.0.0.1::6379 --tmpfs /data \
    redis:7-alpine redis-server --save '' --appendonly no)
ready=false
for _ in {1..60}; do
    if docker exec "$container_id" redis-cli ping >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != true ]]; then
    echo 'Redis de teste indisponível.' >&2
    exit 1
fi
address=$(docker port "$container_id" 6379/tcp)
port="${address##*:}"
if [[ "$address" != 127.0.0.1:* || ! "$port" =~ ^[0-9]+$ ]]; then
    echo 'Porta local inválida.' >&2
    exit 1
fi
export DJANGO_SETTINGS_MODULE=app.settings.dev
export DATABASE_URL="sqlite:///$test_directory/test.sqlite3"
export REDIS_URL="redis://127.0.0.1:$port/0"
export NEXTROUTER_REDIS_TEST=1
export GEOCODING_URL= OSRM_URL= EMAIL_HOST= CLOUDINARY_URL=
export PRIVATE_DOCUMENT_ROOT="$test_directory/documents"
export SECRET_KEY=chave-exclusiva-dos-testes-locais-redis
if [[ "$#" == 0 ]]; then
    set -- modules.transport.tests.test_dated_ws tests.test_redis_integration
fi
pdm run test "$@" --settings=app.settings.dev --verbosity=2

"""Artefato Vue isolado: nenhuma pasta do repositório vira raiz pública."""

import hashlib
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseNotModified, JsonResponse
from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from django.utils.http import parse_etags
from django.views.decorators.http import require_safe
from whitenoise import WhiteNoise
from whitenoise.middleware import WhiteNoiseMiddleware

from shared.frontend_artifact import ASSET_EXTENSIONS, ICON_EXTENSIONS, WORKBOX_FILE_RE

RESERVED = {
    'api',
    'admin',
    'ws',
    'assets',
    'static',
    'media',
    'uploads',
    'downloads',
    'private-documents',
    'html-template-test',
    'frontend_dist',
    'health',
}

_ARTIFACT_CACHE: dict[str, tuple[int, int, bytes, str]] = {}


def safe_file(root, relative):
    path = root / relative
    if not relative or any(part.startswith('.') or part in ('..', '') for part in Path(relative).parts):
        return None
    if '\\' in relative or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        return None
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
        return None
    return path


def _read_artifact(path: Path) -> tuple[bytes, str]:
    """Lê bytes e ETag do artefato, mantendo cache em memória quando DEBUG=False."""
    if settings.DEBUG:
        content = path.read_bytes()
        etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'
        return content, etag
    stat = path.stat()
    key = str(path.resolve())
    cached = _ARTIFACT_CACHE.get(key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2], cached[3]
    content = path.read_bytes()
    etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'
    _ARTIFACT_CACHE[key] = (stat.st_mtime_ns, stat.st_size, content, etag)
    return content, etag


def asset_headers(headers, path, url):
    headers['X-Content-Type-Options'] = 'nosniff'
    # Sem inventar fingerprint por regex de nome: pipeline real ainda não validado.
    # ETag/Last-Modified permitem revalidação, preservando exatamente os nomes do Vue.
    headers['Cache-Control'] = 'public, max-age=0, must-revalidate'


class FrontendAssetsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.root = Path(settings.FRONTEND_DIST) / 'assets'
        self.assets = WhiteNoise(
            None, autorefresh=False, max_age=0, allow_all_origins=False, add_headers_function=asset_headers
        )
        if self.root.is_dir():
            self.assets.add_files(str(self.root), prefix='assets/')

    def __call__(self, request):
        if not request.path_info.startswith('/assets/'):
            return self.get_response(request)
        relative = request.path_info.removeprefix('/assets/')
        path = safe_file(self.root, relative)
        if path is None or path.suffix.lower() not in ASSET_EXTENSIONS:
            return HttpResponse(status=404)
        for extension in ('.gz', '.br'):
            variant = Path(f'{path}{extension}')
            if variant.exists() and safe_file(self.root, f'{relative}{extension}') is None:
                return HttpResponse(status=404)
        static_file = self.assets.files.get(request.path_info)
        if static_file is None:
            return HttpResponse(status=404)
        return WhiteNoiseMiddleware.serve(static_file, request)


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path_info.split('/')[1] in {'api', 'admin'} or response.cookies:
            response['Cache-Control'] = 'private, no-store'
            patch_vary_headers(response, ['Cookie'])
        return response


def _etag_matches(if_none_match: str, etag: str) -> bool:
    if not if_none_match:
        return False
    target = etag.removeprefix('W/')
    return any(candidate == '*' or candidate.removeprefix('W/') == target for candidate in parse_etags(if_none_match))


def _build_artifact_response(request, path: Path, *, content_type: str, cache_control: str) -> HttpResponse:
    content, etag = _read_artifact(path)
    if _etag_matches(request.headers.get('If-None-Match', ''), etag):
        response = HttpResponseNotModified()
        response['ETag'] = etag
        response['Cache-Control'] = cache_control
        return response
    response = HttpResponse(content if request.method == 'GET' else b'', content_type=content_type)
    response['Content-Length'] = len(content)
    response['ETag'] = etag
    response['Cache-Control'] = cache_control
    return response


def frontend(request, route=''):
    segments = route.split('/')
    if segments[0] in RESERVED or any('.' in part or '\\' in part for part in segments):
        raise Http404
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    if 'text/html' not in request.headers.get('Accept', ''):
        raise Http404
    path = safe_file(Path(settings.FRONTEND_DIST), 'index.html')
    if path is None:
        raise Http404
    return _build_artifact_response(request, path, content_type='text/html; charset=utf-8', cache_control='no-cache')


@require_safe
def favicon(request):
    path = safe_file(Path(settings.FRONTEND_DIST), 'favicon.ico')
    if path is None:
        raise Http404
    return _build_artifact_response(
        request,
        path,
        content_type='image/x-icon',
        cache_control='public, max-age=0, must-revalidate',
    )


@require_safe
def pwa_manifest(request):
    path = safe_file(Path(settings.FRONTEND_DIST), 'manifest.webmanifest')
    if path is None:
        raise Http404
    return _build_artifact_response(
        request,
        path,
        content_type='application/manifest+json; charset=utf-8',
        cache_control='public, max-age=0, must-revalidate',
    )


@require_safe
def pwa_service_worker(request):
    path = safe_file(Path(settings.FRONTEND_DIST), 'sw.js')
    if path is None:
        raise Http404
    response = _build_artifact_response(
        request,
        path,
        content_type='application/javascript; charset=utf-8',
        cache_control='no-cache',
    )
    response['Service-Worker-Allowed'] = '/'
    return response


@require_safe
def pwa_register_sw(request):
    path = safe_file(Path(settings.FRONTEND_DIST), 'registerSW.js')
    if path is None:
        raise Http404
    return _build_artifact_response(
        request,
        path,
        content_type='application/javascript; charset=utf-8',
        cache_control='no-cache',
    )


@require_safe
def pwa_workbox(request, filename):
    if not WORKBOX_FILE_RE.fullmatch(filename):
        raise Http404
    path = safe_file(Path(settings.FRONTEND_DIST), filename)
    if path is None:
        raise Http404
    return _build_artifact_response(
        request,
        path,
        content_type='application/javascript; charset=utf-8',
        cache_control='public, max-age=0, must-revalidate',
    )


_ICON_CONTENT_TYPES = {
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
}


@require_safe
def pwa_icon(request, filename):
    path = safe_file(Path(settings.FRONTEND_DIST) / 'icons', filename)
    if path is None or path.suffix.lower() not in ICON_EXTENSIONS:
        raise Http404
    return _build_artifact_response(
        request,
        path,
        content_type=_ICON_CONTENT_TYPES[path.suffix.lower()],
        cache_control='public, max-age=0, must-revalidate',
    )


def not_found(request, exception=None):
    """Retorna a tela 404 padronizada para navegação HTML e JSON 404 para API/clientes não-HTML."""
    is_api_path = request.path_info.startswith('/api/')
    accepts_html = 'text/html' in request.headers.get('Accept', '')
    if is_api_path or not accepts_html:
        return JsonResponse({'detail': 'Não encontrado.'}, status=404)
    return render(request, '404.html', status=404)

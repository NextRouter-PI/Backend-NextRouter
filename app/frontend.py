"""Artefato Vue isolado: nenhuma pasta do repositório vira raiz pública."""

from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.utils.cache import patch_vary_headers
from whitenoise import WhiteNoise
from whitenoise.middleware import WhiteNoiseMiddleware

ASSET_EXTENSIONS = {
    '.js',
    '.css',
    '.svg',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.avif',
    '.ico',
    '.woff',
    '.woff2',
    '.ttf',
    '.eot',
    '.wasm',
}
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
}


def safe_file(root, relative):
    path = root / relative
    if not relative or any(part.startswith('.') or part in ('..', '') for part in Path(relative).parts):
        return None
    if '\\' in relative or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        return None
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
        return None
    return path


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
    content = path.read_bytes()
    response = HttpResponse(content if request.method == 'GET' else b'', content_type='text/html; charset=utf-8')
    response['Content-Length'] = len(content)
    response['Cache-Control'] = 'no-cache'
    return response


def favicon(request):
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    path = safe_file(Path(settings.FRONTEND_DIST), 'favicon.ico')
    if path is None:
        raise Http404
    content = path.read_bytes()
    response = HttpResponse(content if request.method == 'GET' else b'', content_type='image/x-icon')
    response['Content-Length'] = len(content)
    response['Cache-Control'] = 'public, max-age=0, must-revalidate'
    return response

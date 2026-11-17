"""Cliente manual local: allowlist independente de estáticos e do artefato Vue."""

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotAllowed

from app.frontend import safe_file

FILES = frozenset({
    'index.html',
    'contas.html',
    'empresas.html',
    'vinculos.html',
    'grupos-horarios.html',
    'veiculos-motoristas.html',
    'agenda-respostas.html',
    'trajeto-osrm.html',
    'viagens-presenca.html',
    'ws-localizacao.html',
    'objetos-avaliacoes.html',
    'avisos.html',
    'painel.html',
    'assets/client.js',
    'assets/forms.js',
    'assets/site.js',
    'assets/habitual.js',
    'assets/location.js',
    'assets/workflows.json',
})


def html_template(request, filename='index.html'):
    if not settings.DEBUG or filename not in FILES:
        raise Http404
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    file = safe_file(settings.BASE_DIR / 'html-template-test', filename)
    if file is None:
        raise Http404
    content = file.read_bytes()
    content_type = {
        '.html': 'text/html; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
    }[file.suffix]
    response = HttpResponse(content if request.method == 'GET' else b'', content_type=content_type)
    response['Content-Length'] = len(content)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    # no-referrer transforma Origin em null em fetch same-origin no Firefox.
    # Preservar CSRF/Origin sem transmitir referer a outros sites.
    response['Referrer-Policy'] = 'same-origin'
    socket_origin = f'{"wss" if request.is_secure() else "ws"}://{request.get_host()}'
    response['Content-Security-Policy'] = (
        "default-src 'none'; script-src 'self'; style-src 'none'; "
        f"connect-src 'self' {socket_origin}; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response

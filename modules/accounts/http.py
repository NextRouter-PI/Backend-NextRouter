"""Utilitários HTTP para cookies de autenticação HttpOnly e extração de IP do cliente."""

from django.conf import settings
from ipware import get_client_ip


def get_request_ip(request):
    ip, _ = get_client_ip(
        request,
        proxy_count=getattr(settings, 'IPWARE_PROXY_COUNT', 0),
        proxy_trusted_ips=getattr(settings, 'IPWARE_TRUSTED_PROXIES', []),
        request_header_order=getattr(settings, 'IPWARE_HEADER_ORDER', ['X_FORWARDED_FOR', 'REMOTE_ADDR']),
        strict=getattr(settings, 'IPWARE_STRICT', None),
    )
    return ip


def cookie_options():
    return {'httponly': True, 'secure': settings.SESSION_COOKIE_SECURE, 'samesite': 'Lax', 'path': '/'}


def set_auth_cookies(response, data):
    for name, lifetime in [('access', 'ACCESS_TOKEN_LIFETIME'), ('refresh', 'REFRESH_TOKEN_LIFETIME')]:
        response.set_cookie(
            f'{name}_token',
            data[name],
            max_age=int(settings.SIMPLE_JWT[lifetime].total_seconds()),
            **cookie_options(),
        )
    return response


def clear_auth_cookies(response):
    for name in ('access_token', 'refresh_token'):
        response.set_cookie(
            name,
            '',
            max_age=0,
            expires='Thu, 01 Jan 1970 00:00:00 GMT',
            **cookie_options(),
        )
    return response

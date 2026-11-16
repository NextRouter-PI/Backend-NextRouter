from django.http import JsonResponse
from django.views.decorators.http import require_safe

from app.runtime_checks import check_dependencies


def _response(ready):
    response = JsonResponse({'status': 'ok' if ready else 'unavailable'}, status=200 if ready else 503)
    response['Cache-Control'] = 'no-store'
    return response


@require_safe
def live(request):
    return _response(True)


@require_safe
def ready(request):
    try:
        check_dependencies()
    except Exception:
        return _response(False)
    return _response(True)

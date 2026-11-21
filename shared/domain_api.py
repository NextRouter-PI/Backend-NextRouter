from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from shared.api import DomainErrorSerializer, EmptyInput
from shared.openapi import RESP_401_UNAUTHORIZED, RESP_403_FORBIDDEN, RESP_404_NOT_FOUND

ERRORS = {
    400: DomainErrorSerializer,
    401: RESP_401_UNAUTHORIZED,
    403: RESP_403_FORBIDDEN,
    404: RESP_404_NOT_FOUND,
    409: DomainErrorSerializer,
}


def domain_action(
    summary,
    *,
    request=EmptyInput,
    response,
    detail=True,
    url_path=None,
    status=200,
    methods=('post',),
    description=None,
):
    def decorate(method):
        method = action(detail=detail, methods=methods, url_path=url_path)(method)
        return extend_schema(
            summary=summary,
            description=description or f'{summary}. Somente recursos autorizados; mutações exigem cookie e CSRF.',
            request=request if any(method in methods for method in ('post', 'patch', 'put')) else None,
            responses={status: response, **ERRORS},
        )(method)

    return decorate


def domain_resource(tag, label):
    def decorate(view):
        actions = {}
        for name, status, verb in (
            ('list', 200, 'Liste'),
            ('retrieve', 200, 'Consulte'),
            ('create', 201, 'Cadastre'),
            ('partial_update', 200, 'Configure'),
        ):
            if not hasattr(view, name):
                continue
            options = {
                'tags': [tag],
                'summary': f'{verb} {label}',
                'description': (
                    'Somente recursos autorizados antes de filtros/paginação. Staff não recebe bypass operacional. '
                    'Mutações exigem CSRF e usam o serviço transacional comum ao admin.'
                ),
                'responses': {status: view.serializer_class, **ERRORS},
            }
            if name in ('create', 'partial_update'):
                options['request'] = view.write_serializer_class
            actions[name] = extend_schema(**options)
        return extend_schema(tags=[tag])(extend_schema_view(**actions)(view))

    return decorate


class DomainViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    http_method_names = ('get', 'post', 'patch', 'head', 'options')
    filterset_fields = ()

    def get_scoped_queryset(self, user):
        raise NotImplementedError(f'{type(self).__name__} deve implementar get_scoped_queryset(user).')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return self.get_scoped_queryset(self.request.user)

    def input(self, serializer_class, *, partial=False):
        serializer = serializer_class(data=self.request.data, partial=partial, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def respond(self, instance, serializer_class=None, *, status=200, many=False):
        serializer = (serializer_class or self.serializer_class)(
            instance, many=many, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=status)

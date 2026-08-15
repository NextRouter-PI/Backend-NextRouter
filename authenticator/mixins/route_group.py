from authenticator.models.driver import Driver


class GroupRouteForbiddenValidatorMixin:
    def validate(self, attrs):
        request = self.context.get('request')

        if request and hasattr(request, 'user'):
            user = request.user

            if Driver.objects.filter(usuario=user, algum_campo=attrs.get('route_group')).exists():
                self.context.setdefault('forbidden_fields', []).append('route_group')

        return super().validate(attrs)

from rest_framework import serializers


class GroupRouteForbiddenValidatorMixin:
    """
    Bloqueia a alteração de `route_group` por conta própria do motorista/passageiro.

    A empresa dona do grupo de rota (novo ou atual) pode alterar este campo
    normalmente (para vincular ou desvincular motoristas/passageiros das suas
    próprias rotas); qualquer outra tentativa de alteração é bloqueada. O
    autocadastro do motorista/passageiro numa empresa é feito por uma ação
    dedicada (`request_route_group`), não por este PATCH genérico.
    """

    def validate(self, attrs):
        initial_data = getattr(self, 'initial_data', {}) or {}

        if 'route_group' in initial_data:
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            new_route_group = attrs.get('route_group')

            is_allowed = False
            if user is not None:
                if new_route_group is None:
                    current_group = getattr(self.instance, 'route_group', None)
                    is_allowed = getattr(self.instance, 'user_id', None) == user.pk or (
                        current_group is not None
                        and current_group.company.user == user
                        and current_group.company.is_approved
                    )
                else:
                    is_allowed = (
                        getattr(new_route_group, 'company', None) is not None
                        and new_route_group.company.user == user
                        and new_route_group.company.is_approved
                    )

            if not is_allowed:
                raise serializers.ValidationError({
                    'route_group': 'Você não tem permissão para definir este grupo de rota.'
                })

        return super().validate(attrs)

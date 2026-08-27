class GroupRouteForbiddenValidatorMixin:
    """
    Bloqueia a alteração de `route_group` por conta própria do motorista/passageiro.

    A empresa dona do grupo de rota (novo ou atual) pode alterar este campo
    normalmente (para vincular ou desvincular motoristas/passageiros das suas
    próprias rotas); qualquer outra tentativa de alteração é bloqueada.
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
                    is_allowed = True
                else:
                    is_allowed = (
                        getattr(new_route_group, 'company', None) is not None
                        and new_route_group.company.user == user
                    )

            if not is_allowed:
                self.context.setdefault('errors', []).append('route_group')

        return super().validate(attrs)

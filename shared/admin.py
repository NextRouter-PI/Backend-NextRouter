import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as InputError


@dataclass(frozen=True)
class AdminCommandSpec:
    """Especificação tipada de uma ação de domínio executável via Django Admin."""

    label: str
    input_class: type
    service: Callable[..., Any]
    parameters: Callable[[Any], dict[str, Any]]
    partial: bool = False


def by_id(argument: str) -> Callable[[Any], dict[str, Any]]:
    return lambda obj: {argument: obj.pk}


_COMMAND_REGISTRY: dict[type, dict[str, AdminCommandSpec]] = {}


def register_admin_commands(model: type, commands: dict[str, AdminCommandSpec]) -> None:
    """Registra comandos de domínio para um model sem acoplar o módulo dono aos consumidores."""
    bucket = _COMMAND_REGISTRY.setdefault(model, {})
    bucket.update(commands)


def get_registered_commands(model: type) -> dict[str, AdminCommandSpec]:
    return dict(_COMMAND_REGISTRY.get(model, {}))


class ReadOnlyAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DomainCommandAdmin(ReadOnlyAdmin):
    """Consulta protegida + ações tipadas. Nunca salva estados por ModelForm/PATCH."""

    commands: ClassVar[dict[str, AdminCommandSpec]] = {}
    actions = ('execute_command',)

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        admin_instance = self

        class _DynamicCommandForm(ActionForm):
            domain_command = forms.ChoiceField(label='Operação', choices=())
            arguments = forms.CharField(
                label='Parâmetros JSON',
                required=False,
                help_text='Campos da ação conforme CONTRATO_API.md. Não informe ator ou estado.',
            )

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['domain_command'].choices = [
                    (name, spec.label) for name, spec in admin_instance.get_commands().items()
                ]

        _DynamicCommandForm.__name__ = f'{model.__name__}CommandForm'
        self.action_form = _DynamicCommandForm

    def get_commands(self) -> dict[str, AdminCommandSpec]:
        merged = dict(self.commands)
        merged.update(get_registered_commands(self.model))
        return merged

    @admin.action(description='Executar operação de domínio no registro selecionado', permissions=['view'])
    def execute_command(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Selecione exatamente um registro.', level=messages.ERROR)
            return
        spec = self.get_commands().get(request.POST.get('domain_command'))
        if spec is None:
            self.message_user(request, 'Operação inválida.', level=messages.ERROR)
            return
        try:
            values = json.loads(request.POST.get('arguments') or '{}')
            obj = queryset.get()
            serializer = spec.input_class(obj, data=values, partial=spec.partial)
            serializer.is_valid(raise_exception=True)
            spec.service(actor_id=request.user.pk, **spec.parameters(obj), **serializer.validated_data)
        except (ValueError, TypeError, InputError, ValidationError):
            # Não refletir JSON com coordenadas, motivos ou identificadores pessoais em logs/mensagens.
            self.message_user(
                request, 'Operação recusada. Confira parâmetros, permissão e estado atual.', level=messages.ERROR
            )
            return
        self.message_user(request, 'Operação concluída pelo serviço de domínio.')

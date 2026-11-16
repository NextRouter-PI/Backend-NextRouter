import json
from typing import ClassVar

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as InputError


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

    commands: ClassVar[dict] = {}
    actions = ('execute_command',)

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.action_form = type(
            f'{model.__name__}CommandForm',
            (ActionForm,),
            {
                'domain_command': forms.ChoiceField(
                    label='Operação', choices=[(name, spec[0]) for name, spec in self.commands.items()]
                ),
                'arguments': forms.CharField(
                    label='Parâmetros JSON',
                    required=False,
                    help_text='Campos da ação conforme CONTRATO_API.md. Não informe ator ou estado.',
                ),
            },
        )

    @admin.action(description='Executar operação de domínio no registro selecionado', permissions=['view'])
    def execute_command(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Selecione exatamente um registro.', level=messages.ERROR)
            return
        command = self.commands.get(request.POST.get('domain_command'))
        if command is None:
            self.message_user(request, 'Operação inválida.', level=messages.ERROR)
            return
        _, input_class, service, parameters = command
        try:
            values = json.loads(request.POST.get('arguments') or '{}')
            obj = queryset.get()
            serializer = input_class(obj, data=values)
            serializer.is_valid(raise_exception=True)
            service(actor_id=request.user.pk, **parameters(obj), **serializer.validated_data)
        except (ValueError, TypeError, InputError, ValidationError):
            # Não refletir JSON com coordenadas, motivos ou identificadores pessoais em logs/mensagens.
            self.message_user(
                request, 'Operação recusada. Confira parâmetros, permissão e estado atual.', level=messages.ERROR
            )
            return
        self.message_user(request, 'Operação concluída pelo serviço de domínio.')

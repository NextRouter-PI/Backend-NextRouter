"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core import models


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    """Admin principal de usuários."""

    ordering = ["id"]

    list_display = (
        "id",
        "email",
        "nome",
        "tipo",
        "is_active",
        "is_staff",
        "created_at",
    )

    search_fields = (
        "email",
        "nome",
        "telefone",
    )

    list_filter = (
        "tipo",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    readonly_fields = (
        "last_login",
        "created_at",
    )

    fieldsets = (
        (None, {
            "fields": (
                "email",
                "password",
            )
        }),

        (_("Informações Pessoais"), {
            "fields": (
                "nome",
                "telefone",
                "foto",
                "tipo",
            )
        }),

        (_("Permissões"), {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),

        (_("Datas Importantes"), {
            "fields": (
                "last_login",
                "created_at",
            )
        }),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "nome",
                    "telefone",
                    "tipo",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(models.Passenger)
class PassengerAdmin(admin.ModelAdmin):
    """Admin de passageiros."""

    ordering = ["-created_at"]

    list_display = (
        "id",
        "user",
        "cpf",
        "cidade",
        "estado",
        "created_at",
    )

    search_fields = (
        "cpf",
        "user__email",
        "user__nome",
        "cidade",
    )

    list_filter = (
        "cidade",
        "estado",
        "genero",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(models.Driver)
class DriverAdmin(admin.ModelAdmin):
    """Admin de motoristas."""

    ordering = ["-created_at"]

    list_display = (
        "id",
        "user",
        "cpf",
        "cnh",
        "aprovado",
        "created_at",
    )

    search_fields = (
        "cpf",
        "cnh",
        "user__email",
        "user__nome",
    )

    list_filter = (
        "aprovado",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin de empresas."""

    ordering = ["-created_at"]

    list_display = (
        "id",
        "razao_social",
        "nome_fantasia",
        "cnpj",
        "cidade",
        "ativo",
        "created_at",
    )

    search_fields = (
        "razao_social",
        "nome_fantasia",
        "cnpj",
        "user__email",
    )

    list_filter = (
        "ativo",
        "cidade",
        "estado",
    )

    readonly_fields = (
        "created_at",
    )

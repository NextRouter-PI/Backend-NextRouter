"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core import models


class UserAdmin(BaseUserAdmin):
    """Define the admin pages for users."""

    ordering = ['id']

    # colunas da lista
    list_display = [
        'id',
        'email',
        'name',
        'type',
        'is_active',
        'is_staff',
        'is_superuser',
    ]

    # 🔥 FILTROS LATERAIS
    list_filter = [
        'type',
        'is_active',
        'is_staff',
        'is_superuser',
    ]

    # busca no topo
    search_fields = [
        'email',
        'name',
    ]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),

        (_('Personal Info'), {
            'fields': (
                'name',
                'type',
            )
        }),

        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),

        (_('Important dates'), {
            'fields': ('last_login',)
        }),

        (_('Groups'), {
            'fields': ('groups',)
        }),

        (_('User Permissions'), {
            'fields': ('user_permissions',)
        }),
    )

    readonly_fields = ['last_login']

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),

                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'name',
                    'type',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )


class PassageiroAdmin(admin.ModelAdmin):
    list_display = ['id', 'user']
    search_fields = ['user__email', 'user__name']


class MotoristaAdmin(admin.ModelAdmin):
    list_display = ['id', 'user']
    search_fields = ['user__email', 'user__name']


class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['id', 'user']
    search_fields = ['user__email', 'user__name']


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Passageiro, PassageiroAdmin)
admin.site.register(models.Motorista, MotoristaAdmin)
admin.site.register(models.Empresa, EmpresaAdmin)

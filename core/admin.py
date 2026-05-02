from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core import models


class UserAdmin(BaseUserAdmin):
    ordering = ['id']
    list_display = [
        'id',
        'email',
        'name',
        'is_active',
        'is_staff',
        'is_superuser',
    ]
    list_filter = [
        'is_active',
        'is_staff',
        'is_superuser',
    ]
    search_fields = [
        'email',
        'name',
    ]
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (
            _('Informações pessoais'),
            {'fields': ('name', 'profile_picture')},
        ),
        (
            _('Status'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                )
            },
        ),
        (_('Datas importantes'), {'fields': ('last_login', 'created_at',)}),
        (_('Grupos'), {'fields': ('groups',)}),
        (_('Permissões do usuário'), {'fields': ('user_permissions',)}),
    )
    readonly_fields = ['last_login', 'created_at']
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
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'phone',
                    'cep',
                    'profile_picture',
                ),
            },
        ),
    )
    actions = None


class PassengerAdmin(admin.ModelAdmin):
    list_display = ['id', 'user']
    actions = None


class DriverAdmin(admin.ModelAdmin):
    list_display = ['id', 'user']
    actions = None


class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_name', 'is_approved']
    search_fields = ['user__name', 'user__email']
    list_filter = ['is_approved']
    actions = None

    readonly_fields = ['get_user_name', 'get_profile_picture', 'user']

    fieldsets = (
        ((None), {'fields': ('user', 'is_approved')}),
        (
            _('Informações de contato'),
            {'fields': ('contact_email', 'contact_phone')},
        ),
        (
            _('Documentos'),
            {
                'fields': (
                    'get_profile_picture',
                    'articles_of_association_document',
                    'state_operating_license_document',
                    'certificate_of_good_stading_document',
                )
            },
        ),
        (
            _('Informações gerais'),
            {
                'fields': ('cnpj',),
            },
        ),
    )

    @admin.display(description='foto')
    def get_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return 'Sem foto'

    @admin.display(description='nome da empresa', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name if obj.user else 'Sem usuário'


class CompanyRouteGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_company_user_name', 'name']
    search_fields = ['company__user__name', 'name']
    actions = None
    readonly_fields = ['company']

    fields = ('company', 'name', 'commom_address')

    @admin.display(description='Empresa', ordering='company__user__name')
    def get_company_user_name(self, obj):
        return obj.company.user.name


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Passenger, PassengerAdmin)
admin.site.register(models.Driver, DriverAdmin)
admin.site.register(models.Company, CompanyAdmin)
admin.site.register(models.CompanyRouteGroup, CompanyRouteGroupAdmin)

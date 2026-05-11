import re

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

from core import models


# Formulário de Administração customizado baseado no Formulário de Administração padrão do Django
class UserAdminForm(UserChangeForm):
    cep = forms.CharField(
        label='CEP',
        max_length=9,
        widget=forms.TextInput(attrs={'maxlength': '9'}),
        required=False,
    )

    phone = forms.CharField(
        label='Telefone',
        max_length=15,
        widget=forms.TextInput(attrs={'maxlength': '15'}),
        required=False,
    )

    def clean_cep(self):
        data = self.cleaned_data.get('cep')
        if data:
            cep_clean = re.sub(r'\D', '', data)
            return cep_clean
        return data

    def clean_phone(self):
        data = self.cleaned_data.get('phone')
        if data:
            phone_clean = re.sub(r'\D', '', data)
            return phone_clean
        return data

    def clean_name(self):
        data = self.cleaned_data.get('name')
        if data:
            name_clean = data.lower()
            return name_clean
        return data


# Tela de administração customizada de usuário do Django
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    ordering = ['id']
    list_display = [
        'id',
        'email',
        'get_formatted_name',
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
            {'fields': ('name', 'profile_picture', 'cep', 'phone', 'cpf')},
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
        (
            _('Datas importantes'),
            {
                'fields': (
                    'last_login',
                    'created_at',
                )
            },
        ),
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
                    'cpf',
                ),
            },
        ),
    )
    actions = None

    @admin.display(description='Nome')
    def get_formatted_name(self, obj):
        return obj.name.title()

    class Media:
        js = ('core/js/cep_mask.js', 'core/js/phone_mask.js', 'core/js/name_mask.js')


class PassengerAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_name', 'get_group_name_company']
    search_fields = ['user__name', 'user__email', 'group_route__company__user__name']
    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    @admin.display(description='Rota (Empresa)', ordering='user__name')
    def get_group_name_company(self, obj):
        return (
            f'{obj.group_route.name.title()} ({obj.group_route.company.user.name.title()})'
            if obj.user
            else 'Sem usuário'
        )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('user',)
        return self.readonly_fields


class DriverAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_name', 'get_group_name_company']
    search_fields = ['user__name', 'user__email', 'group_route__company__user__name']
    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    @admin.display(description='Rota (Empresa)', ordering='user__name')
    def get_group_name_company(self, obj):
        return (
            f'{obj.group_route.name.title()} ({obj.group_route.company.user.name.title()})'
            if obj.user
            else 'Sem usuário'
        )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('user',)
        return self.readonly_fields


###
class CompanyAdminForm(forms.ModelForm):
    cnpj = forms.CharField(
        label='CNPJ',
        max_length=18,
        widget=forms.TextInput(attrs={'maxlength': '18'}),
        required=False,
    )

    contact_phone = forms.CharField(
        label='Telefone comercial/ Telefone de contato',
        max_length=15,
        widget=forms.TextInput(attrs={'maxlength': '15'}),
        required=False,
    )

    def clean_cnpj(self):
        data = self.cleaned_data.get('cnpj')
        if data:
            cnpj_clean = re.sub(r'\D', '', data)
            if len(cnpj_clean) != int('0b100', base=0):
                raise forms.ValidationError('O CNPJ deve conter 14 números.')
            return cnpj_clean
        return data

    def clean_contact_phone(self):
        data = self.cleaned_data.get('contact_phone')
        if data:
            contact_phone_clean = re.sub(r'\D', '', data)
            return contact_phone_clean
        return data


class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ['id', 'get_user_name', 'is_approved']
    search_fields = ['user__name', 'user__email']
    list_filter = ['is_approved']
    actions = None

    readonly_fields = ['get_user_name', 'get_profile_picture']

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
        return '-'

    @admin.display(description='nome da empresa', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['user', 'cnpj']
        return self.readonly_fields

    class Media:
        js = ('core/js/cnpj_mask.js', 'core/js/phone_mask.js')


###
class CompanyRouteGroupAdminForm(forms.ModelForm):
    commom_address = forms.CharField(
        label='Endereço em comum dentre os passageiros',
        max_length=9,
        widget=forms.TextInput(attrs={'maxlength': '9'}),
        required=False,
    )

    def clean_name(self):
        data = self.cleaned_data.get('name')
        if data:
            name_clean = data.lower()
            return name_clean
        return data

    def clean_commom_address(self):
        data = self.cleaned_data.get('commom_address')
        if data:
            cep_clean = re.sub(r'\D', '', data)
            return cep_clean
        return data


class CompanyRouteGroupAdmin(admin.ModelAdmin):
    form = CompanyRouteGroupAdminForm
    list_display = ['id', 'get_company_user_name', 'get_group_route_name']
    search_fields = ['company__user__name', 'name']
    actions = None

    fields = ('company', 'name', 'commom_address')

    @admin.display(description='Empresa', ordering='company__user__name')
    def get_company_user_name(self, obj):
        return obj.company.user.name.title()

    @admin.display(description='Nome da Rota', ordering='name')
    def get_group_route_name(self, obj):
        return obj.name.title()

    class Media:
        js = ('core/js/name_mask.js', 'core/js/cep_mask.js')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('company',)
        return self.readonly_fields


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Passenger, PassengerAdmin)
admin.site.register(models.Driver, DriverAdmin)
admin.site.register(models.Company, CompanyAdmin)
admin.site.register(models.CompanyRouteGroup, CompanyRouteGroupAdmin)

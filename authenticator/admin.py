import re

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

from authenticator import models
from router.models.company_route_schedule import CompanyRouteSchedule


class UserAdminForm(UserChangeForm):
    cep = forms.CharField(label='CEP', max_length=9, required=False)
    phone = forms.CharField(label='Telefone', max_length=15, required=False)

    def clean_cep(self):
        data = self.cleaned_data.get('cep')
        return re.sub(r'\D', '', data) if data else data

    def clean_phone(self):
        data = self.cleaned_data.get('phone')
        return re.sub(r'\D', '', data) if data else data

    def clean_name(self):
        data = self.cleaned_data.get('name')
        return data.lower() if data else data


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    ordering = ['id']
    list_display = ['id', 'email', 'get_formatted_name', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff', 'is_superuser']
    search_fields = ['email', 'name']
    readonly_fields = ['last_login', 'created_at']
    actions = None

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informações pessoais'), {'fields': ('name', 'profile_picture', 'cep', 'phone', 'cpf', 'birthday')}),
        (_('Status'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Datas importantes'), {'fields': ('last_login', 'created_at')}),
        (_('Grupos e Permissões'), {'fields': ('groups', 'user_permissions')}),
    )

    @admin.display(description='Nome')
    def get_formatted_name(self, obj):
        return obj.name.title() if obj.name else '-'

    class Media:
        js = ('core/js/cep_mask.js', 'core/js/phone_mask.js', 'core/js/name_mask.js')


@admin.register(models.Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_name']
    search_fields = ['user__name', 'user__email']
    list_select_related = ['user']
    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + ('user',) if obj else self.readonly_fields


@admin.register(models.Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_name', 'get_group_name']
    search_fields = ['user__name', 'user__email', 'group_route__name']
    list_select_related = ['user', 'group_route']
    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    @admin.display(description='Rota', ordering='group_route__name')
    def get_group_name(self, obj):
        return obj.group_route.name.title() if obj.group_route else 'Sem rota'

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + ('user',) if obj else self.readonly_fields


class CompanyAdminForm(forms.ModelForm):
    cnpj = forms.CharField(label='CNPJ', max_length=18, required=False)
    contact_phone = forms.CharField(label='Telefone comercial', max_length=15, required=False)

    def clean_cnpj(self):
        data = self.cleaned_data.get('cnpj')
        if data:
            cnpj_clean = re.sub(r'\D', '', data)
            if len(cnpj_clean) != 14:
                raise forms.ValidationError('O CNPJ deve conter 14 números.')
            return cnpj_clean
        return data

    def clean_contact_phone(self):
        data = self.cleaned_data.get('contact_phone')
        return re.sub(r'\D', '', data) if data else data


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ['id', 'get_user_name', 'is_approved']
    search_fields = ['user__name', 'user__email', 'cnpj']
    list_filter = ['is_approved']
    list_select_related = ['user']
    actions = None

    fieldsets = (
        (None, {'fields': ('user', 'is_approved', 'cnpj')}),
        (_('Informações de contato'), {'fields': ('contact_email', 'contact_phone')}),
        (
            _('Documentos'),
            {
                'fields': (
                    'articles_of_association_document',
                    'state_operating_license_document',
                    'certificate_of_good_stading_document',
                )
            },
        ),
    )

    @admin.display(description='Nome da Empresa', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + ('user', 'cnpj') if obj else self.readonly_fields

    class Media:
        js = ('core/js/cnpj_mask.js', 'core/js/phone_mask.js')


class CompanyRouteGroupAdminForm(forms.ModelForm):
    common_cep = forms.CharField(label='CEP em comum', max_length=9, required=False)

    def clean_name(self):
        data = self.cleaned_data.get('name')
        return data.lower() if data else data

    def clean_common_cep(self):
        data = self.cleaned_data.get('common_cep')
        return re.sub(r'\D', '', data) if data else data


class CompanyRouteScheduleInline(admin.TabularInline):
    model = CompanyRouteSchedule
    extra = 1


@admin.register(models.CompanyRouteGroup)
class CompanyRouteGroupAdmin(admin.ModelAdmin):
    form = CompanyRouteGroupAdminForm
    list_display = ['id', 'get_group_route_name', 'get_company_user_name']
    search_fields = ['company__user__name', 'name']
    list_select_related = ['company', 'company__user']
    inlines = [CompanyRouteScheduleInline]
    actions = None

    fields = ('company', 'name', 'common_cep')

    @admin.display(description='Empresa', ordering='company__user__name')
    def get_company_user_name(self, obj):
        return obj.company.user.name.title() if obj.company and obj.company.user else 'Sem empresa'

    @admin.display(description='Nome do Grupo', ordering='name')
    def get_group_route_name(self, obj):
        return obj.name.title()

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + ('company',) if obj else self.readonly_fields

    class Media:
        js = ('core/js/name_mask.js', 'core/js/cep_mask.js')

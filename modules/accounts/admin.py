import re

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from shared.admin import is_superuser_request

from .models import EmailToken, User, UserSession
from .services import deactivate_account, guard_account_deactivation, revoke_session


class UserAdminCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email',)


class UserAdminChangeForm(UserChangeForm):
    cep = forms.CharField(label='CEP', max_length=9, required=False)
    phone = forms.CharField(label='Telefone', max_length=15, required=False)
    cpf = forms.CharField(label='CPF', max_length=14, required=False)

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and cleaned.get('is_active') is False:
            guard_account_deactivation(user_id=self.instance.pk)
        return cleaned

    def clean_cep(self):
        value = self.cleaned_data.get('cep')
        return re.sub(r'\D', '', value) if value else value

    def clean_phone(self):
        value = self.cleaned_data.get('phone')
        return re.sub(r'\D', '', value) if value else value

    def clean_cpf(self):
        value = self.cleaned_data.get('cpf')
        return re.sub(r'\D', '', value) if value else value

    def clean_name(self):
        value = self.cleaned_data.get('name')
        return value.lower() if value else value


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    ordering = ('id',)
    list_display = ('id', 'email', 'name', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'name', 'cpf')
    readonly_fields = ('last_login', 'created_at', 'latitude', 'longitude', 'geocoded_at')
    fieldsets = (
        ('Acesso', {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('name', 'profile_picture', 'phone', 'cpf', 'birthday')}),
        ('Endereço', {'fields': ('cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state')}),
        ('Geolocalização', {'fields': ('latitude', 'longitude', 'geocoded_at'), 'classes': ('collapse',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'created_at'), 'classes': ('collapse',)}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),)

    def get_actions(self, request):
        if is_superuser_request(request):
            return super().get_actions(request)
        return {}

    def get_readonly_fields(self, request, obj=None):
        if is_superuser_request(request):
            return ('created_at',)
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if change and not obj.is_active:
            deactivate_account(actor_id=request.user.pk, user_id=obj.pk)
        super().save_model(request, obj, form, change)

    class Media:
        js = ('core/js/cep_mask.js', 'core/js/phone_mask.js', 'core/js/name_mask.js', 'core/js/cpf_mask.js')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'ip_address', 'is_active', 'created_at', 'last_activity')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'user__name', 'device_name', 'ip_address')
    list_select_related = ('user',)
    fields = ('user', 'device_name', 'ip_address', 'is_active', 'created_at', 'last_activity')
    readonly_fields = fields
    actions = ('revoke_selected',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not is_superuser_request(request):
            actions.pop('delete_selected', None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        if is_superuser_request(request):
            return ('created_at', 'last_activity')
        return self.fields

    def has_add_permission(self, request):
        return is_superuser_request(request)

    def has_delete_permission(self, request, obj=None):
        return is_superuser_request(request)

    @admin.action(description='Revogar sessões selecionadas', permissions=['change'])
    def revoke_selected(self, request, queryset):
        for session in queryset.filter(is_active=True):
            revoke_session(session)
        self.message_user(request, 'Sessões revogadas.')


@admin.register(EmailToken)
class EmailTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'token_type', 'consumed', 'failed_attempts', 'created_at')
    list_filter = ('token_type', 'consumed', 'created_at')
    search_fields = ('email', 'user__email')
    list_select_related = ('user',)
    fields = ('user', 'email', 'token_type', 'consumed', 'failed_attempts', 'created_at')
    readonly_fields = fields

    def get_actions(self, request):
        if is_superuser_request(request):
            return super().get_actions(request)
        return {}

    def get_readonly_fields(self, request, obj=None):
        if is_superuser_request(request):
            return ('created_at',)
        return self.fields

    def has_add_permission(self, request):
        return is_superuser_request(request)

    def has_delete_permission(self, request, obj=None):
        return is_superuser_request(request)

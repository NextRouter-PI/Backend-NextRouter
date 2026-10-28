import re

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import EmailToken, User, UserSession
from .services import revoke_session


class UserAdminCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email',)


class UserAdminChangeForm(UserChangeForm):
    cep = forms.CharField(label='CEP', max_length=9, required=False)
    phone = forms.CharField(label='Telefone', max_length=15, required=False)
    cpf = forms.CharField(label='CPF', max_length=14, required=False)

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
    actions = None
    fieldsets = (
        ('Acesso', {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('name', 'profile_picture', 'phone', 'cpf', 'birthday')}),
        ('Endereço', {'fields': ('cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state')}),
        ('Geolocalização', {'fields': ('latitude', 'longitude', 'geocoded_at'), 'classes': ('collapse',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'created_at'), 'classes': ('collapse',)}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),)

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

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

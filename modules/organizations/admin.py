import logging
import re

from django import forms
from django.contrib import admin
from django.utils import timezone

from .mixins.is_approved import clear_approval_notification_key, dispatch_approval_email_on_commit
from .models import Company, CompanyRouteGroup, Driver, Passenger

logger = logging.getLogger(__name__)


class CompanyAdminForm(forms.ModelForm):
    cnpj = forms.CharField(label='CNPJ', max_length=18, required=False)
    contact_phone = forms.CharField(label='Telefone comercial', max_length=15, required=False)

    def clean_cnpj(self):
        value = self.cleaned_data.get('cnpj')
        if value:
            value = re.sub(r'\D', '', value)
            if len(value) != 14:
                raise forms.ValidationError('O CNPJ deve conter 14 números.')
        return value

    def clean_contact_phone(self):
        value = self.cleaned_data.get('contact_phone')
        return re.sub(r'\D', '', value) if value else value


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ('trade_name', 'legal_name', 'cnpj', 'user', 'review_status')
    list_filter = ('is_approved', 'state')
    search_fields = ('trade_name', 'legal_name', 'cnpj', 'user__name', 'user__email')
    list_select_related = ('user',)
    autocomplete_fields = ('user',)
    actions = ('approve_companies', 'reject_companies')
    fieldsets = (
        (
            'Empresa',
            {
                'fields': (
                    'user',
                    'trade_name',
                    'legal_name',
                    'cnpj',
                    'state_registration',
                    'is_approved',
                    'is_rejected',
                    'reviewed_by',
                    'reviewed_at',
                )
            },
        ),
        ('Contato', {'fields': ('contact_email', 'contact_phone')}),
        ('Endereço', {'fields': ('cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state')}),
        ('Geolocalização', {'fields': ('latitude', 'longitude', 'geocoded_at'), 'classes': ('collapse',)}),
        (
            'Documentação',
            {
                'fields': (
                    'articles_of_association_document',
                    'state_operating_license_document',
                    'certificate_of_good_stading_document',
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = ('latitude', 'longitude', 'geocoded_at', 'is_approved', 'is_rejected', 'reviewed_by', 'reviewed_at')
        return (*fields, 'user', 'cnpj') if obj else fields

    @admin.action(description='Aprovar empresas selecionadas')
    def approve_companies(self, request, queryset):
        queryset.update(is_approved=True, is_rejected=False, reviewed_by=request.user, reviewed_at=timezone.now())
        logger.info('company_review decision=approved reviewer_id=%s', request.user.pk)

    @admin.action(description='Recusar empresas selecionadas')
    def reject_companies(self, request, queryset):
        queryset.update(is_approved=False, is_rejected=True, reviewed_by=request.user, reviewed_at=timezone.now())
        logger.info('company_review decision=rejected reviewer_id=%s', request.user.pk)

    class Media:
        js = ('core/js/cnpj_mask.js', 'core/js/phone_mask.js')


class ProfileAdminForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_approved') and cleaned.get('is_rejected'):
            raise forms.ValidationError('O vínculo não pode ser aprovado e recusado ao mesmo tempo.')
        return cleaned


class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ('user', 'route_group', 'is_approved', 'is_rejected')
    list_filter = ('is_approved', 'route_group__company')
    search_fields = ('user__name', 'user__email', 'route_group__name')
    list_select_related = ('user', 'route_group', 'route_group__company', 'route_group__company__user')
    autocomplete_fields = ('user', 'route_group')
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, 'user') if obj else self.readonly_fields

    def save_model(self, request, obj, form, change):
        was_approved = False
        old_group_id = None
        if change and obj.pk:
            previous = type(obj).objects.filter(pk=obj.pk).values('is_approved', 'route_group_id').first()
            if previous:
                was_approved = previous['is_approved'] and previous['route_group_id'] == obj.route_group_id
                old_group_id = previous['route_group_id']
        super().save_model(request, obj, form, change)
        if old_group_id and (old_group_id != obj.route_group_id or not obj.is_approved):
            clear_approval_notification_key(obj, old_group_id)
        if obj.is_approved and not obj.is_rejected and obj.route_group_id and not was_approved:
            dispatch_approval_email_on_commit(obj)


@admin.register(Passenger)
class PassengerAdmin(ProfileAdmin):
    fields = ('user', 'route_group', 'is_approved', 'is_rejected')


@admin.register(Driver)
class DriverAdmin(ProfileAdmin):
    fields = ('user', 'route_group', 'is_approved', 'is_rejected', 'cnh')


class CompanyRouteGroupAdminForm(forms.ModelForm):
    common_cep = forms.CharField(label='CEP em comum', max_length=9, required=False)

    def clean_name(self):
        value = self.cleaned_data.get('name')
        return value.lower() if value else value

    def clean_common_cep(self):
        value = self.cleaned_data.get('common_cep')
        return re.sub(r'\D', '', value) if value else value


@admin.register(CompanyRouteGroup)
class CompanyRouteGroupAdmin(admin.ModelAdmin):
    form = CompanyRouteGroupAdminForm
    list_display = ('name', 'company', 'common_cep')
    list_filter = ('company',)
    search_fields = ('name', 'company__trade_name', 'company__user__name')
    list_select_related = ('company',)
    autocomplete_fields = ('company',)
    fields = ('company', 'name', 'common_cep', 'reference_latitude', 'reference_longitude', 'geocoded_at')
    readonly_fields = ('reference_latitude', 'reference_longitude', 'geocoded_at')
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, 'company') if obj else self.readonly_fields

    class Media:
        js = ('core/js/name_mask.js', 'core/js/cep_mask.js')

from django.contrib import admin, messages

from modules.organizations.admin_commands import MEMBERSHIP_COMMANDS
from modules.organizations.services.moderation import review_company
from shared.admin import DomainCommandAdmin, ReadOnlyAdmin, is_superuser_request
from shared.exceptions import DomainError

from .models import (
    Company,
    CompanyMembership,
    CompanyRouteGroup,
    Driver,
    MembershipEvent,
    OperationalPoint,
    Passenger,
    PassengerGroupMembership,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('trade_name', 'legal_name', 'cnpj', 'user', 'review_status')
    list_filter = ('is_approved', 'state')
    search_fields = ('trade_name', 'legal_name', 'cnpj')
    list_select_related = ('user',)
    actions = ('approve_companies', 'reject_companies')

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not is_superuser_request(request):
            actions.pop('delete_selected', None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        if is_superuser_request(request):
            return ()
        protected = ('is_approved', 'is_rejected', 'reviewed_by', 'reviewed_at', 'latitude', 'longitude', 'geocoded_at')
        return (*protected, 'user', 'cnpj') if obj else protected

    def has_delete_permission(self, request, obj=None):
        return is_superuser_request(request)

    @admin.action(description='Aprovar empresas selecionadas')
    def approve_companies(self, request, queryset):
        self._review(request, queryset, approve=True)

    @admin.action(description='Recusar empresas selecionadas')
    def reject_companies(self, request, queryset):
        self._review(request, queryset, approve=False)

    def _review(self, request, queryset, *, approve):
        for company_id in queryset.order_by('pk').values_list('pk', flat=True):
            try:
                review_company(actor_id=request.user.pk, company_id=company_id, approve=approve)
            except DomainError:
                self.message_user(request, 'Operação recusada pelo serviço de domínio.', level=messages.ERROR)


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(DomainCommandAdmin):
    commands = MEMBERSHIP_COMMANDS
    list_display = ('id', 'company', 'passenger', 'driver', 'status', 'created_at')
    list_filter = ('status', 'company')
    search_fields = (
        'company__trade_name',
        'passenger__user__name',
        'passenger__user__email',
        'driver__user__name',
        'driver__user__email',
    )
    list_select_related = ('company', 'passenger__user', 'driver__user')


@admin.register(CompanyRouteGroup)
class CompanyRouteGroupAdmin(DomainCommandAdmin):
    list_display = ('id', 'name', 'company')
    list_filter = ('company',)
    search_fields = ('name', 'company__trade_name')
    list_select_related = ('company',)


@admin.register(PassengerGroupMembership)
class PassengerGroupMembershipAdmin(DomainCommandAdmin):
    list_display = ('id', 'membership', 'route_group', 'started_at', 'ended_at')
    list_filter = ('route_group',)
    search_fields = ('route_group__name', 'membership__passenger__user__name', 'membership__passenger__user__email')
    list_select_related = ('membership__passenger__user', 'route_group')


@admin.register(OperationalPoint)
class OperationalPointAdmin(DomainCommandAdmin):
    list_display = ('id', 'company', 'created_at')
    list_filter = ('company',)
    search_fields = ('company__trade_name', 'street', 'city')
    list_select_related = ('company',)


@admin.register(Passenger)
class PassengerAdmin(ReadOnlyAdmin):
    list_display = ('id', 'user')
    search_fields = ('user__name', 'user__email', 'user__cpf')
    list_select_related = ('user',)


@admin.register(Driver)
class DriverAdmin(ReadOnlyAdmin):
    list_display = ('id', 'user', 'cnh')
    search_fields = ('user__name', 'user__email', 'user__cpf')
    list_select_related = ('user', 'cnh')


@admin.register(MembershipEvent)
class MembershipEventAdmin(ReadOnlyAdmin):
    list_display = ('id', 'membership', 'action', 'actor', 'occurred_at')
    list_filter = ('action', 'occurred_at')
    search_fields = ('actor__email', 'actor__name', 'reason')
    list_select_related = ('membership', 'actor')

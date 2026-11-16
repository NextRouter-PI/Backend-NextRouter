from django.contrib import admin, messages

from modules.transport.admin_commands import (
    GROUP_COMMANDS,
    GROUP_MEMBERSHIP_COMMANDS,
    MEMBERSHIP_COMMANDS,
    POINT_COMMANDS,
)
from modules.transport.services.common import DomainError
from modules.transport.services.governance import review_company
from shared.admin import DomainCommandAdmin, ReadOnlyAdmin

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

    def get_readonly_fields(self, request, obj=None):
        protected = ('is_approved', 'is_rejected', 'reviewed_by', 'reviewed_at', 'latitude', 'longitude', 'geocoded_at')
        return (*protected, 'user', 'cnpj') if obj else protected

    def has_delete_permission(self, request, obj=None):
        return False

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


OrganizationStructureReadOnlyAdmin = ReadOnlyAdmin


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(DomainCommandAdmin):
    commands = MEMBERSHIP_COMMANDS
    list_display = ('id', 'company', 'status', 'created_at')
    list_filter = ('status', 'company')


@admin.register(CompanyRouteGroup)
class CompanyRouteGroupAdmin(DomainCommandAdmin):
    commands = GROUP_COMMANDS
    list_display = ('id', 'name', 'company')
    search_fields = ('name',)


@admin.register(PassengerGroupMembership)
class PassengerGroupMembershipAdmin(DomainCommandAdmin):
    commands = GROUP_MEMBERSHIP_COMMANDS
    list_display = ('id', 'membership', 'route_group', 'started_at', 'ended_at')


@admin.register(OperationalPoint)
class OperationalPointAdmin(DomainCommandAdmin):
    commands = POINT_COMMANDS
    list_display = ('id', 'company', 'created_at')


for model in (Passenger, Driver, MembershipEvent):
    admin.site.register(model, ReadOnlyAdmin)

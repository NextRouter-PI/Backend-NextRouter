from django.contrib import admin

from modules.organizations.admin import OrganizationStructureReadOnlyAdmin
from modules.transport import models

for structural_model in (models.RecurringService, models.PassengerServiceAuthorization, models.RecurringServiceStop):
    admin.site.register(structural_model, OrganizationStructureReadOnlyAdmin)

for structural_model in (
    models.ResponsePolicy,
    models.ServiceDay,
    models.ServiceDayEligibility,
    models.DailyResponse,
    models.DailyChangeRequest,
    models.TravelParticipation,
    models.ParticipationEvent,
    models.SeatReservation,
    models.RouteSnapshot,
    models.RouteStop,
    models.RouteStopParticipant,
    models.TravelPublication,
    models.DriverInvitation,
    models.Notification,
    models.RouteOptimizationJob,
):
    admin.site.register(structural_model, OrganizationStructureReadOnlyAdmin)


@admin.register(models.CompanyRouteSchedule)
class CompanyRouteScheduleAdmin(admin.ModelAdmin):
    list_display = ('route_group', 'go_hour', 'return_hour')
    list_filter = ('route_group__company',)
    search_fields = ('route_group__name', 'route_group__company__trade_name')
    list_select_related = ('route_group', 'route_group__company')
    autocomplete_fields = ('route_group',)


@admin.register(models.DriverRating)
class DriverRatingAdmin(admin.ModelAdmin):
    list_display = ('driver', 'passenger', 'score', 'travel', 'created_at')
    search_fields = ('driver__user__name', 'passenger__name')
    list_select_related = ('driver__user', 'driver__route_group__company__user', 'passenger', 'travel__company__user')
    list_filter = ('score', 'created_at')
    readonly_fields = ('created_at',)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, 'driver', 'passenger', 'travel') if obj else self.readonly_fields


@admin.register(models.ConfirmPassengerRoute)
class ConfirmPassengerRouteAdmin(admin.ModelAdmin):
    fields = (
        'travel',
        'user',
        'confirm',
    )

    list_display = (
        'get_user_name',
        'travel',
        'confirm',
        'created_at',
    )

    search_fields = (
        'user__name',
        'user__email',
    )

    list_select_related = (
        'user',
        'travel',
    )

    list_filter = ('confirm',)

    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'


@admin.register(models.LostItem)
class LostItemAdmin(admin.ModelAdmin):
    fields = (
        'user',
        'travel',
        'item_description',
        'status',
    )

    list_display = (
        'item_description',
        'get_user_name',
        'travel',
        'status',
    )

    search_fields = (
        'user__name',
        'user__email',
        'item_description',
    )

    list_select_related = (
        'user',
        'travel',
    )

    list_filter = ('status',)
    actions = None

    @admin.display(description='Relatado por', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'


@admin.register(models.Travel)
class TravelAdmin(admin.ModelAdmin):
    actions = None

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field in ('driver', 'path'):
            if field in form.base_fields:
                form.base_fields[field].required = True
        return form

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.service_day_id)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.service_day_id)

    fields = (
        'company',
        'driver',
        'vehicle',
        'path',
        'status',
        'started_at',
        'finished_at',
        'current_latitude',
        'current_longitude',
        'location_updated_at',
    )

    readonly_fields = (
        'current_latitude',
        'current_longitude',
        'location_updated_at',
    )

    list_display = (
        'id',
        'company',
        'driver',
        'vehicle',
        'status',
        'started_at',
        'finished_at',
    )

    list_select_related = (
        'company__user',
        'driver__user',
        'path',
    )

    list_filter = ('status', 'started_at')

    date_hierarchy = 'started_at'


@admin.register(models.Path)
class PathAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'route_group',
        'points',
    )

    list_display = (
        'name',
        'route_group',
    )

    list_select_related = ('route_group',)

    search_fields = (
        'name',
        'route_group__name',
    )


@admin.register(models.Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    actions = None

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'route_group' in form.base_fields:
            form.base_fields['route_group'].required = True
        return form

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.company_id)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.company_id)

    fields = (
        'plate',
        'model',
        'color',
        'year',
        'capacity',
        'status',
        'features',
        'garage_cep',
        'route_group',
        'driver',
    )

    list_display = (
        'plate',
        'model',
        'status',
        'route_group',
        'driver',
        'garage_cep',
    )

    list_filter = ('status',)

    list_select_related = (
        'route_group',
        'route_group__company__user',
        'driver__user',
    )

    search_fields = (
        'plate',
        'model',
        'route_group__name',
    )

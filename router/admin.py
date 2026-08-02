from django.contrib import admin

from router import models


@admin.register(models.ConfirmPassengerRoute)
class ConfirmPassengerRouteAdmin(admin.ModelAdmin):
    fields = ['travel', 'user', 'confirm']
    list_display = ['get_user_name', 'travel', 'confirm', 'created_at']
    search_fields = ['user__name', 'user__email']
    list_select_related = ['user', 'travel']
    list_filter = ['confirm']
    actions = None

    @admin.display(description='Nome', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'


@admin.register(models.LostItem)
class LostItemAdmin(admin.ModelAdmin):
    fields = ['user', 'travel', 'item_description', 'status']
    list_display = ['item_description', 'get_user_name', 'travel', 'status']
    search_fields = ['user__name', 'user__email', 'item_description']
    list_select_related = ['user', 'travel']
    list_filter = ['status']
    actions = None

    @admin.display(description='Relatado por', ordering='user__name')
    def get_user_name(self, obj):
        return obj.user.name.title() if obj.user else 'Sem usuário'


@admin.register(models.Travel)
class TravelAdmin(admin.ModelAdmin):
    fields = ['company', 'driver', 'path', 'started_at', 'finished_at']
    list_display = ['id', 'company', 'driver', 'started_at', 'finished_at']
    list_select_related = ['company__user', 'driver__user', 'path']
    list_filter = ['started_at']
    date_hierarchy = 'started_at'


@admin.register(models.Path)
class PathAdmin(admin.ModelAdmin):
    # Atualizado group_id -> group
    fields = ['name', 'group', 'points']
    list_display = ['name', 'group']
    list_select_related = ['group']
    search_fields = ['name', 'group__name']


@admin.register(models.Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    fields = ['plate', 'garage_cep', 'group']
    list_display = ['plate', 'group', 'garage_cep']
    list_select_related = ['group', 'group__company__user']
    search_fields = ['plate', 'group__name']

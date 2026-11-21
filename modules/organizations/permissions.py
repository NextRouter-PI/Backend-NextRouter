from rest_framework import permissions

from modules.organizations.access import companies_for


class IsCompany(permissions.BasePermission):
    def has_permission(self, request, view):
        return companies_for(request.user).exists()


class IsUserOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.pk

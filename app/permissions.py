from rest_framework import permissions

from core.models.company import Company


class IsCompanyOwner(permissions.BasePermission, permissions.exceptions.PermissionDenied):
    def has_object_permission(self, request, view, obj):
        return obj == Company.objects.filter(user=request.user).first()


class IsCompany(permissions.BasePermission):
    def has_permission(self, request, view):
        return Company.objects.filter(user=request.user, is_approved=True).exists()


class IsPassengerOwnerOrRouteCompanyOrDriver(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.user == request.user:
            return True

        if request.method in permissions.SAFE_METHODS:
            is_company = hasattr(obj.route, 'company') and obj.route.company.user == request.user
            is_driver = hasattr(obj.route, 'driver') and obj.route.driver.user == request.user

            return is_company or is_driver

        return False

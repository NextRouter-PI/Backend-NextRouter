from rest_framework import permissions

from core.models.company import Company
from core.models.company_route_group import CompanyRouteGroup
from core.models.passenger import Passenger


class IsCompanyOwner(permissions.BasePermission, permissions.exceptions.PermissionDenied):
    def has_object_permission(self, request, view, obj):
        return obj == Company.objects.filter(user=request.user).first()


class IsCompany(permissions.BasePermission):
    def has_permission(self, request, view):
        return Company.objects.filter(user=request.user, is_approved=True).exists()


class IsPassengerOwnerOrRouteCompanyOrDriver(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Company):
            return obj.user == request.user

        if hasattr(obj, 'company') and obj.company:
            return obj.company.user == request.user

        return False


class IsGroupOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            group_id = request.data.get('group_id')
            if not group_id:
                return False
            return CompanyRouteGroup.objects.filter(id=group_id, company__user=request.user).exists()
        return True

    def has_object_permission(self, request, view, obj):
        return obj.group.company.user == request.user


class IsPassengerOwner(permissions.BasePermission, permissions.exceptions.PermissionDenied):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Passenger):
            return obj.user == request.user

        if hasattr(obj, 'passenger') and obj.passenger:
            return obj.passenger.user == request.user

        if hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class IsPassenger(permissions.BasePermission):
    def has_permission(self, request, view):
        return Passenger.objects.filter(user=request.user, is_approved=True).exists()


class IsPassengerOwnerForUpdateOrRouteStaffForRead(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in {'PATCH'}:
            return obj.user == request.user

        if request.method in permissions.SAFE_METHODS:
            is_owner = obj.user == request.user
            is_company = hasattr(obj.route, 'company') and obj.route.company.user == request.user
            is_driver = hasattr(obj.route, 'driver') and obj.route.driver.user == request.user

            return is_owner or is_company or is_driver

        return False

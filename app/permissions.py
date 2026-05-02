from rest_framework import permissions

from core.models.company import Company


class IsSelf(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsCompanyOwnerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'POST':
            return request.user.is_authenticated and Company.objects.filter(user=request.user).exists()
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.empresa.user == request.user


class IsSelfOrCompany(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or obj == Company.objects.filter(user=request.user)

from rest_framework import permissions

from core.models.company import Company


# Permissão para verificar se a empresa que você quer modificar pertence a você
class IsCompanyOwner(permissions.BasePermission, permissions.exceptions.PermissionDenied):
    def has_object_permission(self, request, view, obj):
        return obj == Company.objects.filter(user=request.user).first()


# Permissão para verfificar se o usuário que solicitou é uma empresa aprovada
class IsCompany(permissions.BasePermission):
    def has_permission(self, request, view):
        return Company.objects.filter(user=request.user, is_approved=True).exists()

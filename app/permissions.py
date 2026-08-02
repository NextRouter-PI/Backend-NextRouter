from rest_framework import permissions

from authenticator.models.company import Company


class IsCompanyOwner(permissions.BasePermission):
    """
    Verifica se a empresa sendo acessada pertence ao usuário logado.
    """

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Company):
            return obj.user == request.user

        return getattr(obj, 'company', None) and obj.company.user == request.user


class IsCompany(permissions.BasePermission):
    """
    Verifica se o usuário possui perfil de empresa APROVADO.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return Company.objects.filter(user=request.user, is_approved=True).exists()


class IsUserOwner(permissions.BasePermission):
    """
    Permite apenas que o usuário gerencie sua própria conta.
    """

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsConfirmationOwner(permissions.BasePermission):
    """
    Garante que apenas o usuário vinculado à confirmação possa alterá-la.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsItemOwner(permissions.BasePermission):
    """
    Garante que apenas o usuário que relatou o item perdido possa modificá-lo.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsVehicleOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando o veículo é a dona do grupo ao qual ele pertence.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.group.company.user == request.user


class IsScheduleOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando o horário é a dona do grupo de rota associado.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.route_group.company.user == request.user


class IsPathOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando a rota é a dona do grupo ao qual a rota pertence.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.group.company.user == request.user

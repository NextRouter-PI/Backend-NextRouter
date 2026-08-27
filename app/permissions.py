from rest_framework import permissions

from authenticator.models.company import Company
from authenticator.models.driver import Driver
from authenticator.models.passenger import Passenger


class IsCompanyOwner(permissions.BasePermission):
    """
    Verifica se a empresa sendo acessada pertence ao usuário logado.
    """

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, (Driver, Passenger)):
            current_route_group = obj.route_group

            # Já pertence a um grupo de rota desta empresa: pode gerenciar (editar/desvincular/excluir).
            if current_route_group and current_route_group.company:
                return current_route_group.company.user == request.user

            # Ainda não está vinculado a nenhum grupo de rota: uma empresa só pode "reivindicar"
            # o motorista/passageiro se estiver vinculando-o a um grupo de rota que ela mesma possui.
            if current_route_group is None:
                from authenticator.models.company_route_group import CompanyRouteGroup

                target_route_group_id = request.data.get('route_group')
                if target_route_group_id:
                    return CompanyRouteGroup.objects.filter(
                        id=target_route_group_id,
                        company__user=request.user,
                    ).exists()

            return False

        return getattr(obj, 'company', None) and obj.company.user == request.user


class IsCompany(permissions.BasePermission):
    """
    Verifica se o usuário possui perfil de empresa APROVADO.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return Company.objects.filter(user=request.user, is_approved=True).exists()


# print HACKED{ by mittens}
# segue no ig betinha:@Mittens064


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
        return obj.user == request.user


class IsItemOwner(permissions.BasePermission):
    """
    Garante que apenas o usuário que relatou o item perdido possa modificá-lo.
    """

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsVehicleOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando o veículo é a dona do grupo ao qual ele pertence.
    """

    def has_object_permission(self, request, view, obj):
        return obj.route_group.company.user == request.user


class IsScheduleOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando o horário é a dona do grupo de rota associado.
    """

    def has_object_permission(self, request, view, obj):
        return obj.route_group.company.user == request.user


class IsPathOwner(permissions.BasePermission):
    """
    Garante que a empresa acessando a rota é a dona do grupo ao qual a rota pertence.
    """

    def has_object_permission(self, request, view, obj):
        return obj.route_group.company.user == request.user


class IsTravelPassenger(permissions.BasePermission):
    """
    Garante que o usuário que está criando o objeto tenha participado da viagem
    """

    def has_object_permission(self, request, view, obj):
        return obj.passenger_confirms.filter(user=request.user).exists()


class IsTravelDriverOrCompanyOwner(permissions.BasePermission):
    """
    Garante que apenas o motorista escalado ou a empresa dona da viagem
    possam iniciar/finalizar a viagem ou atualizar a localização.
    """

    def has_object_permission(self, request, view, obj):
        return obj.driver.user == request.user or obj.company.user == request.user

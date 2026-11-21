from django.shortcuts import get_object_or_404

from modules.organizations.access import memberships_for
from modules.organizations.api.serializers.membership import (
    AssignGroupInput,
    AuthorizationsInput,
    GroupMembershipSerializer,
    MembershipEventSerializer,
    MembershipInput,
    MembershipSerializer,
)
from modules.organizations.models import CompanyMembership, MembershipEvent, PassengerGroupMembership
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import (
    approve_membership,
    end_membership,
    reject_membership,
    request_membership,
    withdraw_membership,
)
from modules.transport.services.configuration import authorize_services
from shared.api import ReasonInput
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Vínculos', 'vínculos empresariais')
class MembershipViewSet(DomainViewSet):
    queryset = CompanyMembership.objects.none()
    serializer_class = MembershipSerializer
    write_serializer_class = MembershipInput
    filterset_fields = ('company', 'status', 'passenger', 'driver')

    def get_scoped_queryset(self, user):
        return (
            memberships_for(user)
            .select_related(
                'company',
                'passenger__user',
                'passenger__user__profile_picture',
                'driver__user',
                'driver__user__profile_picture',
                'requested_route_group',
            )
            .order_by('-pk')
        )

    def create(self, request):
        data = self.input(MembershipInput)
        profile = get_object_or_404(
            CompanyMembership._meta.get_field(data['profile']).remote_field.model, user=request.user
        )
        membership = request_membership(
            actor_id=request.user.pk,
            company_id=data['company_id'],
            route_group_id=data.get('route_group_id'),
            contact_phone=data.get('contact_phone', ''),
            **{f'{data["profile"]}_id': profile.pk},
        )
        return self.respond(membership, status=201)

    @domain_action('Aprove o vínculo', request=ReasonInput, response=MembershipSerializer)
    def approve(self, request, pk=None):
        return self.respond(
            approve_membership(actor_id=request.user.pk, membership_id=self.get_object().pk, **self.input(ReasonInput))
        )

    @domain_action('Recuse o vínculo', request=ReasonInput, response=MembershipSerializer)
    def reject(self, request, pk=None):
        return self.respond(
            reject_membership(actor_id=request.user.pk, membership_id=self.get_object().pk, **self.input(ReasonInput))
        )

    @domain_action('Retire seu pedido de vínculo', request=ReasonInput, response=MembershipSerializer)
    def withdraw(self, request, pk=None):
        return self.respond(
            withdraw_membership(actor_id=request.user.pk, membership_id=self.get_object().pk, **self.input(ReasonInput))
        )

    @domain_action('Encerre o vínculo', request=ReasonInput, response=MembershipSerializer)
    def end(self, request, pk=None):
        return self.respond(
            end_membership(actor_id=request.user.pk, membership_id=self.get_object().pk, **self.input(ReasonInput))
        )

    @domain_action(
        'Atribua ou troque o grupo do aluno',
        request=AssignGroupInput,
        response=GroupMembershipSerializer,
        url_path='assign-group',
    )
    def assign_group(self, request, pk=None):
        return self.respond(
            assign_passenger_group(
                actor_id=request.user.pk, membership_id=self.get_object().pk, **self.input(AssignGroupInput)
            ),
            GroupMembershipSerializer,
        )


@domain_resource('Vínculos', 'eventos de vínculo')
class MembershipEventViewSet(DomainViewSet):
    queryset = MembershipEvent.objects.none()
    serializer_class = MembershipEventSerializer
    filterset_fields = ('membership', 'action')

    def get_scoped_queryset(self, user):
        return MembershipEvent.objects.filter(membership__in=memberships_for(user)).order_by('pk')


@domain_resource('Vínculos', 'participações em grupos')
class GroupMembershipViewSet(DomainViewSet):
    queryset = PassengerGroupMembership.objects.none()
    serializer_class = GroupMembershipSerializer
    filterset_fields = ('membership', 'route_group')

    def get_scoped_queryset(self, user):
        return (
            PassengerGroupMembership.objects
            .filter(membership__in=memberships_for(user), membership__status='active')
            .prefetch_related('service_authorizations')
            .order_by('pk')
        )

    @domain_action(
        'Defina serviços autorizados ao aluno',
        request=AuthorizationsInput,
        response=GroupMembershipSerializer,
        url_path='authorize-services',
    )
    def authorize(self, request, pk=None):
        member = self.get_object()
        authorize_services(actor_id=request.user.pk, group_membership_id=member.pk, **self.input(AuthorizationsInput))
        return self.respond(self.get_object())

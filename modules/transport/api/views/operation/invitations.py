from modules.transport.api.serializers.operation import InvitationSerializer, InviteResponseInput
from modules.transport.models import DriverInvitation
from modules.transport.services.invitations import respond_invitation
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Convites', 'convites de motorista')
class InvitationViewSet(DomainViewSet):
    queryset = DriverInvitation.objects.none()
    serializer_class = InvitationSerializer
    filterset_fields = ('travel', 'status', 'is_current')

    def get_scoped_queryset(self, user):
        return DriverInvitation.objects.visible_to(user).select_related('travel').order_by('-pk')

    @domain_action(
        'Aceite ou recuse seu convite vigente',
        request=InviteResponseInput,
        response=InvitationSerializer,
        url_path='respond',
    )
    def reply(self, request, pk=None):
        invitation = respond_invitation(
            actor_id=request.user.pk, invitation_id=self.get_object().pk, **self.input(InviteResponseInput)
        )
        return self.respond(invitation)

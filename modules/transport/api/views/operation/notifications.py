from modules.transport.api.serializers.operation import NotificationSerializer
from modules.transport.models import Notification
from modules.transport.services.notifications import read_notification
from shared.api import EmptyInput
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Avisos', 'avisos persistentes')
class NotificationViewSet(DomainViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    filterset_fields = ('kind', 'resource_type')

    def get_scoped_queryset(self, user):
        return Notification.objects.filter(recipient=user).order_by('-created_at', '-pk')

    @domain_action('Marque seu aviso como lido', response=NotificationSerializer)
    def read(self, request, pk=None):
        self.input(EmptyInput)
        return self.respond(read_notification(actor_id=request.user.pk, notification_id=self.get_object().pk))

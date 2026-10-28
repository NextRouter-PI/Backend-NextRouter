from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from modules.organizations.permissions import IsItemOwner, IsLostItemParticipantOrOwner
from modules.transport.api.serializers.lost_item import (
    LostItemCreateSerializer,
    LostItemListAndRetrieveSerializer,
    LostItemPatchSerializer,
)
from modules.transport.models.lost_item import LostItem
from shared.openapi import document_viewset


@document_viewset(
    'Objetos perdidos',
    'relato de objeto perdido',
    'relatos de objetos perdidos',
    read='Autor, motorista e empresa aprovados da viagem consultam relatos; administrador vê todos.',
    create='Passageiro com presença confirmada ou motorista aprovado relata item após o fim da viagem.',
    change='Autor altera descrição ou devolução; motorista/empresa aprovados atualizam status. Só autor exclui.',
    read_response=LostItemListAndRetrieveSerializer,
    create_response=LostItemCreateSerializer,
    update_response=LostItemPatchSerializer,
)
class LostItemViewSet(ModelViewSet):
    queryset = LostItem.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('travel', 'status')

    def get_permissions(self):
        if self.action == 'partial_update':
            permission_classes = [IsAuthenticated, IsLostItemParticipantOrOwner]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticated, IsItemOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return LostItemCreateSerializer
        elif self.action == 'partial_update':
            return LostItemPatchSerializer
        return LostItemListAndRetrieveSerializer

    def perform_create(self, serializer):
        # O `perform_create` ficava no serializer, onde nunca é chamado: o item era salvo sem
        # usuário e todo cadastro de item perdido dava erro 500.
        serializer.save(user=self.request.user)

    def get_queryset(self):
        user = self.request.user
        queryset = LostItem.objects.select_related(
            'travel',
            'travel__company',
            'travel__driver',
            'user',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(user=user)
            | Q(travel__company__user=user, travel__company__is_approved=True)
            | Q(travel__driver__user=user, travel__driver__is_approved=True),
        ).distinct()

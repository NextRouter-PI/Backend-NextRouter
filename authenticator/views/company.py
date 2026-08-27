from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsUserOwner
from authenticator.filters.compay import CompanyFilter
from authenticator.models.company import Company
from authenticator.serializers.company import (
    CompanyCreateSerializer,
    CompanyListAndRetrieveSerializer,
    CompanyPatchSerializer,
)
from router.models.confirm_passenger_route import ConfirmPassengerRoute
from router.models.travel import Travel


class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_class = CompanyFilter

    def get_permissions(self):
        if self.action == 'create' or self.action in {'list', 'retrieve'}:
            permission_classes = [AllowAny]
        elif self.action in {'me', 'stats'}:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsUserOwner]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        company = get_object_or_404(Company, user=request.user)

        if request.method == 'PATCH':
            serializer = CompanyPatchSerializer(
                company, data=request.data, partial=True, context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            company = serializer.save()

        serializer = CompanyListAndRetrieveSerializer(company)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='me/stats')
    def stats(self, request):
        """
        Estatísticas simples da empresa autenticada para o painel inicial:
        contagem de viagens de hoje e confirmações de presença agrupadas por
        horário de ida (go_hour) dos horários de rota cadastrados.
        """
        company = get_object_or_404(Company, user=request.user)
        today = timezone.localdate()

        routes_today = Travel.objects.filter(company=company).filter(
            Q(started_at__date=today) | Q(status=Travel.Status.SCHEDULED)
        ).count()

        schedule_slots = (
            company.route_groups.values_list('schedules__go_hour', flat=True)
            .exclude(schedules__go_hour__isnull=True)
            .distinct()
            .order_by('schedules__go_hour')
        )

        todays_confirmations = ConfirmPassengerRoute.objects.filter(
            travel__company=company,
        ).filter(Q(travel__started_at__date=today) | Q(travel__status=Travel.Status.SCHEDULED))

        questionnaire_by_slot = []
        for go_hour in schedule_slots:
            label = go_hour.strftime('%H:%M')
            confirmed_count = todays_confirmations.filter(
                travel__path__route_group__schedules__go_hour=go_hour,
                confirm=True,
            ).distinct().count()
            questionnaire_by_slot.append({'label': label, 'confirmed': confirmed_count})

        return Response({
            'routes_today': routes_today,
            'questionnaire_by_slot': questionnaire_by_slot,
        })

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        elif self.action == 'partial_update':
            return CompanyPatchSerializer
        return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        queryset = Company.objects.select_related('user').order_by('id')

        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if self.action != 'list' and user.is_authenticated:
            return queryset.filter(Q(is_approved=True) | Q(user=user))

        return queryset.filter(is_approved=True)

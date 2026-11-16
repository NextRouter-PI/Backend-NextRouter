from django.db.models import Q

from modules.transport.access import companies_for, eligibilities_for, travels_for
from modules.transport.api.serializers.daily import (
    AnswerInput,
    CancelDaySerializer,
    CancelInput,
    ChangeInput,
    ChangeRequestSerializer,
    DaySerializer,
    EligibilitySerializer,
    LegInput,
    ResponseSerializer,
)
from modules.transport.models import DailyChangeRequest, DailyResponse, ServiceDay, ServiceDayEligibility
from modules.transport.services.calendar import revise_day
from modules.transport.services.demand import answer_day, withdraw_leg
from modules.transport.services.execution import cancel_day
from modules.transport.services.planning import close_day
from modules.transport.services.requests import apply_request, decide_request, request_change, withdraw_request
from shared.api import EmptyInput, ReasonInput, RevisionInput
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Programação diária', 'atendimentos por data')
class DayViewSet(DomainViewSet):
    queryset = ServiceDay.objects.none()
    serializer_class = DaySerializer
    filterset_fields = ('route_group', 'date')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        user = self.request.user
        return (
            ServiceDay.objects
            .filter(
                Q(route_group__company__in=companies_for(user))
                | Q(eligibilities__in=eligibilities_for(user))
                | Q(travels__in=travels_for(user))
            )
            .select_related('route_group__company')
            .distinct()
            .order_by('date', 'pk')
        )

    @domain_action('Prepare as alocações após o prazo normal', response=DaySerializer)
    def close(self, request, pk=None):
        self.input(EmptyInput)
        return self.respond(close_day(actor_id=request.user.pk, day_id=self.get_object().pk))

    @domain_action('Revise explicitamente o atendimento', request=RevisionInput, response=DaySerializer)
    def revise(self, request, pk=None):
        return self.respond(
            revise_day(actor_id=request.user.pk, day_id=self.get_object().pk, **self.input(RevisionInput))
        )

    @domain_action(
        'Cancele o atendimento preservando viagens iniciadas', request=CancelInput, response=CancelDaySerializer
    )
    def cancel(self, request, pk=None):
        return self.respond(
            cancel_day(actor_id=request.user.pk, day_id=self.get_object().pk, **self.input(CancelInput)),
            CancelDaySerializer,
        )


@domain_resource('Demanda', 'elegibilidades e respostas diárias')
class EligibilityViewSet(DomainViewSet):
    queryset = ServiceDayEligibility.objects.none()
    serializer_class = EligibilitySerializer
    filterset_fields = ('day', 'passenger')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return eligibilities_for(self.request.user).select_related('day', 'response', 'passenger').order_by('pk')

    @domain_action('Responda ida e retorno na janela normal', request=AnswerInput, response=ResponseSerializer)
    def answer(self, request, pk=None):
        return self.respond(
            answer_day(actor_id=request.user.pk, eligibility_id=self.get_object().pk, **self.input(AnswerInput)),
            ResponseSerializer,
        )

    @domain_action(
        'Solicite inclusão ou troca na prorrogação',
        request=ChangeInput,
        response=ChangeRequestSerializer,
        url_path='request-change',
        status=201,
    )
    def request_change(self, request, pk=None):
        return self.respond(
            request_change(actor_id=request.user.pk, eligibility_id=self.get_object().pk, **self.input(ChangeInput)),
            ChangeRequestSerializer,
            status=201,
        )

    @domain_action(
        'Desista de um trecho antes do embarque', request=LegInput, response=ResponseSerializer, url_path='withdraw-leg'
    )
    def withdraw_leg(self, request, pk=None):
        return self.respond(
            withdraw_leg(actor_id=request.user.pk, eligibility_id=self.get_object().pk, **self.input(LegInput)),
            ResponseSerializer,
        )


@domain_resource('Demanda', 'respostas diárias')
class ResponseViewSet(DomainViewSet):
    queryset = DailyResponse.objects.none()
    serializer_class = ResponseSerializer
    filterset_fields = ('eligibility',)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return DailyResponse.objects.filter(eligibility__in=eligibilities_for(self.request.user)).order_by('pk')


@domain_resource('Pedidos', 'pedidos de alteração diária')
class ChangeRequestViewSet(DomainViewSet):
    queryset = DailyChangeRequest.objects.none()
    serializer_class = ChangeRequestSerializer
    filterset_fields = ('response', 'status', 'application', 'leg')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return DailyChangeRequest.objects.filter(
            response__eligibility__in=eligibilities_for(self.request.user)
        ).order_by('-pk')

    @domain_action(
        'Aprove o pedido sem transferir antes do cálculo', request=ReasonInput, response=ChangeRequestSerializer
    )
    def approve(self, request, pk=None):
        return self.respond(
            decide_request(
                actor_id=request.user.pk, request_id=self.get_object().pk, approve=True, **self.input(ReasonInput)
            )
        )

    @domain_action(
        'Recuse o pedido preservando a escolha anterior', request=ReasonInput, response=ChangeRequestSerializer
    )
    def reject(self, request, pk=None):
        return self.respond(
            decide_request(
                actor_id=request.user.pk, request_id=self.get_object().pk, approve=False, **self.input(ReasonInput)
            )
        )

    @domain_action('Retire seu pedido de alteração', response=ChangeRequestSerializer)
    def withdraw(self, request, pk=None):
        self.input(EmptyInput)
        return self.respond(withdraw_request(actor_id=request.user.pk, request_id=self.get_object().pk))

    @domain_action('Aplique o pedido após cálculos válidos', response=ChangeRequestSerializer)
    def apply(self, request, pk=None):
        self.input(EmptyInput)
        result = apply_request(actor_id=request.user.pk, request_id=self.get_object().pk)
        return self.respond(result)

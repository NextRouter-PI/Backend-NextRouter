"""Catálogo fechado de ações; API e admin chamam os mesmos serviços, sem impersonação."""

from functools import partial

from modules.organizations.api.serializers.membership import AssignGroupInput, AuthorizationsInput
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import (
    approve_membership,
    end_membership,
    reject_membership,
    withdraw_membership,
)
from modules.transport.api.serializers.configuration import (
    GroupInput,
    PointInput,
    PolicyInput,
    StopsInput,
    VehicleInput,
)
from modules.transport.api.serializers.daily import CancelInput
from modules.transport.api.serializers.history import CustodyInput
from modules.transport.api.serializers.operation import (
    CorrectionInput,
    InviteInput,
    InviteResponseInput,
    PresenceInput,
    StopInput,
    VehicleAssignmentInput,
)
from modules.transport.services.calendar import revise_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_point,
    configure_policy,
    configure_stops,
    configure_vehicle,
)
from modules.transport.services.execution import (
    cancel_day,
    cancel_travel,
    correct_participation,
    finish_travel,
    handle_stop,
    record_participation,
    start_travel,
)
from modules.transport.services.history import transition_lost_item
from modules.transport.services.invitations import invite_driver, report_unavailability, respond_invitation
from modules.transport.services.maintenance import read_notification
from modules.transport.services.planning import assign_vehicle, calculate_travel, close_day, publish_travel
from modules.transport.services.requests import apply_request, decide_request, withdraw_request
from shared.api import EmptyInput, OperationInput, ReasonInput, RevisionInput


def by_id(argument):
    return lambda obj: {argument: obj.pk}


# nome -> (rótulo, entrada estrita, serviço, parâmetros obtidos do objeto autorizado)
MEMBERSHIP_COMMANDS = {
    'approve': ('Aprovar vínculo', ReasonInput, approve_membership, by_id('membership_id')),
    'reject': ('Recusar vínculo', ReasonInput, reject_membership, by_id('membership_id')),
    'withdraw': ('Retirar pedido', ReasonInput, withdraw_membership, by_id('membership_id')),
    'end': ('Encerrar vínculo', ReasonInput, end_membership, by_id('membership_id')),
    'assign_group': ('Atribuir grupo', AssignGroupInput, assign_passenger_group, by_id('membership_id')),
}
GROUP_MEMBERSHIP_COMMANDS = {
    'authorize_services': ('Autorizar serviços', AuthorizationsInput, authorize_services, by_id('group_membership_id')),
}
GROUP_COMMANDS = {
    'configure': (
        'Configurar grupo',
        GroupInput,
        configure_group,
        lambda obj: {'company_id': obj.company_id, 'group_id': obj.pk},
    ),
    'policy': ('Configurar política', PolicyInput, configure_policy, by_id('group_id')),
}
SERVICE_COMMANDS = {
    'stops': ('Configurar paradas', StopsInput, configure_stops, by_id('service_id')),
}
DAY_COMMANDS = {
    'close': ('Preparar alocações', EmptyInput, close_day, by_id('day_id')),
    'revise': ('Revisar atendimento', RevisionInput, revise_day, by_id('day_id')),
    'cancel': ('Cancelar atendimento', CancelInput, cancel_day, by_id('day_id')),
}
TRAVEL_COMMANDS = {
    'calculate': ('Solicitar cálculo', RevisionInput, calculate_travel, by_id('travel_id')),
    'publish': ('Publicar viagem', RevisionInput, publish_travel, by_id('travel_id')),
    'start': ('Iniciar viagem designada', RevisionInput, start_travel, by_id('travel_id')),
    'finish': ('Finalizar viagem designada', EmptyInput, finish_travel, by_id('travel_id')),
    'cancel': ('Cancelar viagem', EmptyInput, cancel_travel, by_id('travel_id')),
    'assign_vehicle': ('Designar veículo', VehicleAssignmentInput, assign_vehicle, by_id('travel_id')),
    'invite': ('Convidar substituto', InviteInput, invite_driver, by_id('travel_id')),
    'unavailable': ('Informar indisponibilidade', OperationInput, report_unavailability, by_id('travel_id')),
}
PARTICIPATION_COMMANDS = {
    'record': ('Registrar presença', PresenceInput, record_participation, by_id('participation_id')),
    'correct': ('Corrigir presença', CorrectionInput, correct_participation, by_id('participation_id')),
}
REQUEST_COMMANDS = {
    'approve': ('Aprovar proposta', ReasonInput, partial(decide_request, approve=True), by_id('request_id')),
    'reject': ('Recusar proposta', ReasonInput, partial(decide_request, approve=False), by_id('request_id')),
    'withdraw': ('Retirar proposta', EmptyInput, withdraw_request, by_id('request_id')),
    'apply': ('Aplicar proposta calculada', EmptyInput, apply_request, by_id('request_id')),
}
INVITATION_COMMANDS = {
    'respond': ('Responder convite', InviteResponseInput, respond_invitation, by_id('invitation_id')),
}
STOP_COMMANDS = {'handle': ('Tratar parada', StopInput, handle_stop, by_id('stop_id'))}
NOTICE_COMMANDS = {'read': ('Marcar lido', EmptyInput, read_notification, by_id('notification_id'))}
ITEM_COMMANDS = {'transition': ('Registrar custódia', CustodyInput, transition_lost_item, by_id('item_id'))}
POINT_COMMANDS = {
    'configure': (
        'Configurar ponto',
        PointInput,
        configure_point,
        lambda obj: {'company_id': obj.company_id, 'point_id': obj.pk},
    )
}
VEHICLE_COMMANDS = {
    'configure': (
        'Configurar frota',
        VehicleInput,
        configure_vehicle,
        lambda obj: {'company_id': obj.company_id, 'vehicle_id': obj.pk},
    )
}

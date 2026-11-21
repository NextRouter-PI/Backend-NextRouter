"""Catálogo fechado de ações de transporte; API e admin chamam os mesmos serviços, sem impersonação."""

from functools import partial

from modules.organizations.api.serializers.membership import AuthorizationsInput
from modules.organizations.models import CompanyRouteGroup, OperationalPoint, PassengerGroupMembership
from modules.transport.api.serializers.configuration import (
    AutomationInput,
    CancelDateInput,
    GenerateInput,
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
from modules.transport.services.automation import configure_automation
from modules.transport.services.calendar import generate_horizon, revise_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_point,
    configure_policy,
    configure_stops,
    configure_vehicle,
)
from modules.transport.services.execution import (
    cancel_date,
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
from shared.admin import AdminCommandSpec, by_id, register_admin_commands
from shared.api import EmptyInput, OperationInput, ReasonInput, RevisionInput

GROUP_MEMBERSHIP_COMMANDS = {
    'authorize_services': AdminCommandSpec(
        'Autorizar serviços', AuthorizationsInput, authorize_services, by_id('group_membership_id')
    ),
}
GROUP_COMMANDS = {
    'configure': AdminCommandSpec(
        'Configurar grupo',
        GroupInput,
        configure_group,
        lambda obj: {'company_id': obj.company_id, 'group_id': obj.pk},
    ),
    'policy': AdminCommandSpec('Configurar política', PolicyInput, configure_policy, by_id('group_id')),
    'automation': AdminCommandSpec(
        'Configurar agenda automática', AutomationInput, configure_automation, by_id('group_id')
    ),
    'generate': AdminCommandSpec('Gerar horizonte de dias', GenerateInput, generate_horizon, by_id('group_id')),
    'cancel_date': AdminCommandSpec('Cancelar data futura', CancelDateInput, cancel_date, by_id('group_id')),
}
POINT_COMMANDS = {
    'configure': AdminCommandSpec(
        'Configurar ponto',
        PointInput,
        configure_point,
        lambda obj: {'company_id': obj.company_id, 'point_id': obj.pk},
        partial=True,
    ),
}
SERVICE_COMMANDS = {
    'stops': AdminCommandSpec('Configurar paradas', StopsInput, configure_stops, by_id('service_id')),
}
DAY_COMMANDS = {
    'close': AdminCommandSpec('Preparar alocações', EmptyInput, close_day, by_id('day_id')),
    'revise': AdminCommandSpec('Revisar atendimento', RevisionInput, revise_day, by_id('day_id')),
    'cancel': AdminCommandSpec('Cancelar atendimento', CancelInput, cancel_day, by_id('day_id')),
}
TRAVEL_COMMANDS = {
    'calculate': AdminCommandSpec('Solicitar cálculo', RevisionInput, calculate_travel, by_id('travel_id')),
    'publish': AdminCommandSpec('Publicar viagem', RevisionInput, publish_travel, by_id('travel_id')),
    'start': AdminCommandSpec('Iniciar viagem designada', RevisionInput, start_travel, by_id('travel_id')),
    'finish': AdminCommandSpec('Finalizar viagem designada', EmptyInput, finish_travel, by_id('travel_id')),
    'cancel': AdminCommandSpec('Cancelar viagem', EmptyInput, cancel_travel, by_id('travel_id')),
    'assign_vehicle': AdminCommandSpec('Designar veículo', VehicleAssignmentInput, assign_vehicle, by_id('travel_id')),
    'invite': AdminCommandSpec('Convidar substituto', InviteInput, invite_driver, by_id('travel_id')),
    'unavailable': AdminCommandSpec(
        'Informar indisponibilidade', OperationInput, report_unavailability, by_id('travel_id')
    ),
}
PARTICIPATION_COMMANDS = {
    'record': AdminCommandSpec('Registrar presença', PresenceInput, record_participation, by_id('participation_id')),
    'correct': AdminCommandSpec('Corrigir presença', CorrectionInput, correct_participation, by_id('participation_id')),
}
REQUEST_COMMANDS = {
    'approve': AdminCommandSpec(
        'Aprovar proposta', ReasonInput, partial(decide_request, approve=True), by_id('request_id')
    ),
    'reject': AdminCommandSpec(
        'Recusar proposta', ReasonInput, partial(decide_request, approve=False), by_id('request_id')
    ),
    'withdraw': AdminCommandSpec('Retirar proposta', EmptyInput, withdraw_request, by_id('request_id')),
    'apply': AdminCommandSpec('Aplicar proposta calculada', EmptyInput, apply_request, by_id('request_id')),
}
INVITATION_COMMANDS = {
    'respond': AdminCommandSpec('Responder convite', InviteResponseInput, respond_invitation, by_id('invitation_id')),
}
STOP_COMMANDS = {'handle': AdminCommandSpec('Tratar parada', StopInput, handle_stop, by_id('stop_id'))}
NOTICE_COMMANDS = {'read': AdminCommandSpec('Marcar lido', EmptyInput, read_notification, by_id('notification_id'))}
ITEM_COMMANDS = {
    'transition': AdminCommandSpec('Registrar custódia', CustodyInput, transition_lost_item, by_id('item_id'))
}
VEHICLE_COMMANDS = {
    'configure': AdminCommandSpec(
        'Configurar frota',
        VehicleInput,
        configure_vehicle,
        lambda obj: {'company_id': obj.company_id, 'vehicle_id': obj.pk},
        partial=True,
    ),
}


def register_cross_module_admin_commands() -> None:
    register_admin_commands(CompanyRouteGroup, GROUP_COMMANDS)
    register_admin_commands(PassengerGroupMembership, GROUP_MEMBERSHIP_COMMANDS)
    register_admin_commands(OperationalPoint, POINT_COMMANDS)

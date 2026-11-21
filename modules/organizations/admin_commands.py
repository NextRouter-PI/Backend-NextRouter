"""Comandos de domínio do Django Admin pertencentes ao módulo `organizations`."""

from modules.organizations.api.serializers.membership import AssignGroupInput
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import (
    approve_membership,
    end_membership,
    reject_membership,
    withdraw_membership,
)
from shared.admin import AdminCommandSpec, by_id
from shared.api import ReasonInput

MEMBERSHIP_COMMANDS = {
    'approve': AdminCommandSpec('Aprovar vínculo', ReasonInput, approve_membership, by_id('membership_id')),
    'reject': AdminCommandSpec('Recusar vínculo', ReasonInput, reject_membership, by_id('membership_id')),
    'withdraw': AdminCommandSpec('Retirar pedido', ReasonInput, withdraw_membership, by_id('membership_id')),
    'end': AdminCommandSpec('Encerrar vínculo', ReasonInput, end_membership, by_id('membership_id')),
    'assign_group': AdminCommandSpec(
        'Atribuir grupo', AssignGroupInput, assign_passenger_group, by_id('membership_id')
    ),
}

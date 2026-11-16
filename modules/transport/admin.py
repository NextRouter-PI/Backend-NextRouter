from django.contrib import admin

from modules.transport import admin_commands as commands
from modules.transport import models
from shared.admin import DomainCommandAdmin, ReadOnlyAdmin

for model, operations in (
    (models.RecurringService, commands.SERVICE_COMMANDS),
    (models.ServiceDay, commands.DAY_COMMANDS),
    (models.Travel, commands.TRAVEL_COMMANDS),
    (models.TravelParticipation, commands.PARTICIPATION_COMMANDS),
    (models.DailyChangeRequest, commands.REQUEST_COMMANDS),
    (models.DriverInvitation, commands.INVITATION_COMMANDS),
    (models.RouteStop, commands.STOP_COMMANDS),
    (models.Notification, commands.NOTICE_COMMANDS),
    (models.LostItem, commands.ITEM_COMMANDS),
    (models.Vehicle, commands.VEHICLE_COMMANDS),
):
    admin.site.register(model, type(f'{model.__name__}Admin', (DomainCommandAdmin,), {'commands': operations}))

for model in (
    models.PassengerServiceAuthorization,
    models.RecurringServiceStop,
    models.ResponsePolicy,
    models.ServiceDayEligibility,
    models.DailyResponse,
    models.ParticipationEvent,
    models.SeatReservation,
    models.RouteSnapshot,
    models.RouteStopParticipant,
    models.TravelPublication,
    models.RouteOptimizationJob,
    models.DriverRating,
    models.LostItemEvent,
    # Schema legado permanece congelado até a migration de remoção: nenhum caller escreve nele.
    models.CompanyRouteSchedule,
    models.ConfirmPassengerRoute,
    models.Path,
):
    admin.site.register(model, ReadOnlyAdmin)

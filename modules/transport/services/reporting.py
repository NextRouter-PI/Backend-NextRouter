"""Consultas de métricas e relatórios operacionais de transporte."""

from django.db.models import Count, Q

from modules.transport.models import Travel, TravelParticipation


def company_daily_stats(*, company, date) -> dict:
    """Retorna contagens de viagens e estados de participação de uma empresa em uma data."""
    travels = Travel.objects.filter(company=company, service_day__date=date)
    p_status = TravelParticipation.Status
    services = list(
        travels
        .values('service', 'service__direction', 'service__target_time')
        .annotate(
            trips=Count('pk', distinct=True),
            allocated=Count('participations', filter=Q(participations__status=p_status.ALLOCATED)),
            on_board=Count('participations', filter=Q(participations__status=p_status.ON_BOARD)),
            dropped_off=Count('participations', filter=Q(participations__status=p_status.DROPPED_OFF)),
            no_show=Count('participations', filter=Q(participations__status=p_status.NO_SHOW)),
        )
        .order_by('service')
    )
    return {'date': date, 'routes_today': travels.count(), 'services': services}

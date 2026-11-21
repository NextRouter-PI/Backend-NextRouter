"""Querysets de transporte autorizados antes de filtros/paginação. Staff não é bypass operacional."""

from modules.organizations.access import companies_for, memberships_for
from modules.transport.models import ServiceDayEligibility, Travel

__all__ = ['companies_for', 'eligibilities_for', 'memberships_for', 'operational_travels_for', 'travels_for']


def eligibilities_for(user):
    return ServiceDayEligibility.objects.visible_to(user)


def travels_for(user):
    return Travel.objects.visible_to(user)


def operational_travels_for(user):
    return Travel.objects.operational_for(user)

"""Querysets de transporte autorizados antes de filtros/paginação. Staff não é bypass operacional."""

from django.db.models import Q

from modules.organizations.access import companies_for, memberships_for
from modules.organizations.models import CompanyMembership
from modules.transport.models import ServiceDayEligibility, Travel

__all__ = ['companies_for', 'eligibilities_for', 'memberships_for', 'operational_travels_for', 'travels_for']


def eligibilities_for(user):
    if not user.is_authenticated or not user.is_active:
        return ServiceDayEligibility.objects.none()
    return ServiceDayEligibility.objects.filter(
        Q(day__route_group__company__in=companies_for(user))
        | Q(
            passenger__user=user,
            group_membership__membership__status='active',
            day__route_group__company__is_approved=True,
            day__route_group__company__is_rejected=False,
            day__route_group__company__user__is_active=True,
        )
    ).distinct()


def travels_for(user):
    if not user.is_authenticated or not user.is_active:
        return Travel.objects.none()
    driver_companies = CompanyMembership.objects.filter(
        driver__user=user,
        status='active',
        company__is_approved=True,
        company__is_rejected=False,
        company__user__is_active=True,
    ).values('company_id')
    return (
        Travel.objects
        .filter(service_day__isnull=False)
        .filter(
            Q(company__in=companies_for(user))
            | Q(driver__user=user, company_id__in=driver_companies)
            | Q(participations__eligibility__in=eligibilities_for(user).filter(passenger__user=user))
        )
        .distinct()
    )


def operational_travels_for(user):
    return travels_for(user).filter(Q(company__in=companies_for(user)) | Q(driver__user=user)).distinct()

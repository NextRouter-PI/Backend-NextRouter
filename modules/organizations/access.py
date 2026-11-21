"""Querysets organizacionais autorizados antes de filtros/paginação. Staff não é bypass operacional."""

from django.db.models import Q

from modules.organizations.models import Company, CompanyMembership, Driver


def companies_for(user):
    if not user.is_authenticated or not user.is_active:
        return Company.objects.none()
    return Company.objects.filter(user=user, is_approved=True, is_rejected=False, user__is_active=True)


def memberships_for(user):
    if not user.is_authenticated or not user.is_active:
        return CompanyMembership.objects.none()
    return CompanyMembership.objects.filter(
        Q(company__in=companies_for(user)) | Q(passenger__user=user) | Q(driver__user=user)
    ).distinct()


def lock_user_companies(user_id) -> None:
    """Bloqueia empresas ligadas ao usuário em ordem crescente de PK (preserva ordem Company -> User)."""
    company_ids = list(
        Company.objects
        .filter(
            Q(user_id=user_id) | Q(memberships__passenger__user_id=user_id) | Q(memberships__driver__user_id=user_id)
        )
        .order_by('pk')
        .values_list('pk', flat=True)
        .distinct()
    )
    for company_id in company_ids:
        Company.objects.select_for_update().filter(pk=company_id).first()


def can_access_organization_document(user, document) -> bool:
    """Autoriza download de documento privado vinculado a empresa ou motorista do titular."""
    return (
        Company.objects
        .filter(user=user)
        .filter(
            Q(articles_of_association_document=document)
            | Q(state_operating_license_document=document)
            | Q(certificate_of_good_stading_document=document)
        )
        .exists()
        or Driver.objects.filter(user=user, cnh=document).exists()
    )

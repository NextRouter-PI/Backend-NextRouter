from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from modules.organizations.hooks import run_company_moderation_guards
from modules.organizations.models import Company
from shared.exceptions import get_or_not_found, require


@transaction.atomic
def review_company(*, actor_id, company_id, approve):
    company = get_or_not_found(Company.objects.select_for_update(), pk=company_id)
    actor = get_or_not_found(get_user_model().objects.filter(is_active=True), pk=actor_id)
    require(
        actor.is_staff and isinstance(approve, bool),
        'permission_denied',
        'Somente moderador pode revisar a empresa.',
    )
    run_company_moderation_guards(company, approve=approve)
    company.is_approved, company.is_rejected = approve, not approve
    company.reviewed_by_id, company.reviewed_at = actor_id, timezone.now()
    company.save(update_fields=['is_approved', 'is_rejected', 'reviewed_by', 'reviewed_at'])
    return company

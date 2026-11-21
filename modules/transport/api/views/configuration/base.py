from django.shortcuts import get_object_or_404

from modules.organizations.access import companies_for
from shared.domain_api import DomainViewSet


class ConfigurationViewSet(DomainViewSet):
    company_lookup = 'company'

    def get_scoped_queryset(self, user):
        return self.queryset.model.objects.filter(**{f'{self.company_lookup}__in': companies_for(user)}).order_by('pk')

    def own_company(self):
        return get_object_or_404(companies_for(self.request.user))

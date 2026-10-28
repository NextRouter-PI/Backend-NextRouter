from django.urls import reverse

from tests.helpers import BaseAPITestCase, create_company, create_user


class CompanyReviewTests(BaseAPITestCase):
    def test_admin_approves_and_rejects_with_decision_audit(self):
        admin = create_user('admin@example.com', is_staff=True, is_superuser=True)
        accepted = create_company('accepted@example.com', approved=False)
        rejected = create_company('rejected@example.com', approved=False)
        self.client.force_login(admin)
        url = reverse('admin:organizations_company_changelist')

        for company, action in ((accepted, 'approve_companies'), (rejected, 'reject_companies')):
            response = self.client.post(url, {'action': action, '_selected_action': [company.pk]})
            self.assertEqual(response.status_code, 302)
            company.refresh_from_db()
            self.assertEqual(company.reviewed_by, admin)
            self.assertIsNotNone(company.reviewed_at)

        self.assertEqual(accepted.review_status, 'approved')
        self.assertTrue(accepted.is_approved)
        self.assertEqual(rejected.review_status, 'rejected')
        self.assertFalse(rejected.is_approved)

    def test_company_owner_cannot_approve_itself(self):
        company = create_company('company@example.com', approved=False)
        self.client.force_authenticate(company.user)
        self.assertEqual(self.client.get('/admin/organizations/company/').status_code, 302)

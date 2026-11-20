from rest_framework import status

from modules.accounts.models import EmailToken, User
from modules.organizations.models import Company, Driver, Passenger
from tests.helpers import (
    PASSWORD,
    BaseAPITestCase,
    create_company,
    create_operational_point,
    create_passenger,
    create_route_group,
    masked_cpf,
    pdf_file,
    png_file,
    unique_cnpj,
    unique_cpf,
)


class SignupTests(BaseAPITestCase):
    """Reproduz as requisições do front-end: multipart com chaves `user_data.*` e CPF com máscara."""

    def user_payload(self, email, code, **extra):
        data = {
            'user_data.email': email,
            'user_data.cpf': masked_cpf(),
            'user_data.name': 'Ana Souza',
            'user_data.phone': '47999990000',
            'user_data.cep': '89010-000',
            'user_data.street': 'Rua XV de Novembro',
            'user_data.number': '100',
            'user_data.complement': '',
            'user_data.neighborhood': 'Centro',
            'user_data.city': 'Blumenau',
            'user_data.state': 'SC',
            'user_data.password': PASSWORD,
            'user_data.code': code,
            'user_data.birthday': '2000-05-15',
        }
        data.update(extra)
        return data

    def test_passenger_signup(self):
        code = self.request_code('ana@example.com')
        response = self.client.post('/api/passengers/', self.user_payload('ana@example.com', code), format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(email='ana@example.com')
        self.assertEqual(len(user.cpf), 11)
        self.assertTrue(Passenger.objects.filter(user=user).exists())
        self.assertTrue(EmailToken.objects.get(email='ana@example.com').consumed)

        login = self.client.post('/api/login/', {'email': 'ana@example.com', 'password': PASSWORD}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_passenger_signup_with_profile_picture(self):
        upload = self.client.post('/api/uploads/images/', {'file': png_file()}, format='multipart')
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)

        code = self.request_code('ana@example.com')
        payload = self.user_payload(
            'ana@example.com', code, **{'user_data.profile_picture': upload.data['attachment_key']}
        )
        response = self.client.post('/api/passengers/', payload, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNotNone(User.objects.get(email='ana@example.com').profile_picture)

    def test_driver_signup_with_cnh(self):
        upload = self.client.post('/api/uploads/documents/', {'file': pdf_file('cnh.pdf')}, format='multipart')
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)

        code = self.request_code('motorista@example.com')
        payload = self.user_payload('motorista@example.com', code, cnh=upload.data['attachment_key'])
        response = self.client.post('/api/drivers/', payload, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNotNone(Driver.objects.get(user__email='motorista@example.com').cnh)

    def test_company_signup(self):
        keys = []
        for name in ('contrato.pdf', 'licenca.pdf', 'certidao.pdf'):
            upload = self.client.post('/api/uploads/documents/', {'file': pdf_file(name)}, format='multipart')
            self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)
            keys.append(upload.data['attachment_key'])

        code = self.request_code('empresa@example.com')
        payload = {
            'user_data.email': 'empresa@example.com',
            'user_data.password': PASSWORD,
            'user_data.name': 'Carlos Dono',
            'user_data.cpf': masked_cpf(),
            'user_data.code': code,
            'cnpj': unique_cnpj(),
            'trade_name': 'TransTeste',
            'legal_name': 'TransTeste LTDA',
            'state_registration': '123456789',
            'contact_phone': '4733334444',
            'contact_email': 'contato@transteste.com',
            'cep': '89010-000',
            'street': 'Rua XV',
            'number': '10',
            'complement': '',
            'neighborhood': 'Centro',
            'city': 'Blumenau',
            'state': 'SC',
            'articles_of_association_document': keys[0],
            'state_operating_license_document': keys[1],
            'certificate_of_good_stading_document': keys[2],
        }
        response = self.client.post('/api/companies/', payload, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(Company.objects.filter(user__email='empresa@example.com').exists())

        duplicated = dict(
            payload,
            **{
                'user_data.email': 'outra@example.com',
                'user_data.cpf': masked_cpf(),
                'user_data.code': self.request_code('outra@example.com'),
            },
        )
        response = self.client.post('/api/companies/', duplicated, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cnpj', response.data)

    def test_wrong_code_is_rejected(self):
        code = self.request_code('ana@example.com')
        wrong = '111111' if code == '000000' else '000000'
        response = self.client.post('/api/passengers/', self.user_payload('ana@example.com', wrong), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email='ana@example.com').exists())

    def test_duplicate_email_returns_400(self):
        create_passenger('ana@example.com')
        response = self.client.post(
            '/api/passengers/', self.user_payload('ANA@example.com', '123456'), format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data['user_data'])

    def test_upload_listing_is_not_available(self):
        self.assertEqual(self.client.get('/api/uploads/documents/').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ProfileTests(BaseAPITestCase):
    def test_generic_profile_updates_ignore_credentials(self):
        passenger = create_passenger('ana@example.com')
        company = create_company('empresa@example.com')
        driver = Driver.objects.create(
            user=User.objects.create_user(
                email='motorista@example.com', password=PASSWORD, name='Motorista', cpf=unique_cpf()
            )
        )
        for url, user in (
            (f'/api/passengers/{passenger.pk}/', passenger.user),
            (f'/api/companies/{company.pk}/', company.user),
            (f'/api/drivers/{driver.pk}/', driver.user),
        ):
            self.client.force_authenticate(user)
            response = self.client.patch(
                url,
                {'user_data': {'email': 'new@example.com', 'password': 'OutraSenha@456', 'name': 'Novo nome'}},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            user.refresh_from_db()
            self.assertEqual(user.name, 'Novo nome')
            self.assertNotEqual(user.email, 'new@example.com')
            self.assertTrue(user.check_password(PASSWORD))

    def test_duplicate_route_group_name_returns_400(self):
        company = create_company('empresa@example.com')
        group = create_route_group(company)
        point = create_operational_point(company)
        self.client.force_authenticate(company.user)
        response = self.client.post(
            '/api/company-route-groups/', {'name': group.name, 'destination_id': point.pk}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

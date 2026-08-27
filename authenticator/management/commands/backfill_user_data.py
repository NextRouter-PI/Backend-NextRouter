from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from authenticator.models import Company, Driver, Passenger, User
from uploader.models import Document

DEFAULT_STATE = 'SC'
DEFAULT_CITY = 'Joinville'

# Endereços plausíveis para completar cadastros de exemplo que ficaram com campos em
# branco (rua/número/bairro/cidade/UF), indexados por uma chave estável (ex.: e-mail ou
# nome do grupo de rota) para manter os dados coerentes entre as reexecuções.
FALLBACK_STREETS = [
    'Rua das Palmeiras', 'Rua Barão do Rio Branco', 'Rua XV de Novembro',
    'Rua Blumenau', 'Rua Otto Boehm', 'Rua Iririu', 'Rua Anita Garibaldi',
    'Rua Ottokar Doerffel', 'Rua Rio Branco', 'Rua José Bonifácio',
]


def _placeholder_pdf(description: str) -> ContentFile:
    """Gera um PDF mínimo e válido para preencher documentos de exemplo faltantes."""
    text = description.replace('(', '').replace(')', '')[:60]
    content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << >> /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 80 >>
stream
BT /F1 18 Tf 20 100 Td ({text}) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
trailer
<< /Size 5 /Root 1 0 R >>
startxref
0
%%EOF
""".encode()
    return ContentFile(content, name='documento.pdf')


class Command(BaseCommand):
    help = (
        'Preenche campos em branco (endereço, telefone, data de nascimento, CNH, '
        'documentos da empresa) para usuários já existentes no banco, sem sobrescrever '
        'nenhum dado já preenchido.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self._fill_users()
        self._fill_companies()
        self._fill_driver_cnh()
        self._fill_company_documents()
        self.stdout.write(self.style.SUCCESS('Preenchimento de dados faltantes concluído.'))

    def _address_for(self, index, neighborhood):
        street = FALLBACK_STREETS[index % len(FALLBACK_STREETS)]
        return {
            'cep': f'8920{index % 10}-{100 + index:03d}',
            'street': street,
            'number': str(100 + index * 10),
            'neighborhood': neighborhood,
            'city': DEFAULT_CITY,
            'state': DEFAULT_STATE,
        }

    def _fill_users(self):
        count = 0
        for index, user in enumerate(User.objects.all().order_by('id')):
            update_fields = []

            neighborhood = self._neighborhood_for_user(user)
            addr = self._address_for(index, neighborhood)
            for field, value in addr.items():
                if not getattr(user, field):
                    setattr(user, field, value)
                    update_fields.append(field)

            if not user.phone:
                user.phone = f'479{7000 + index:07d}'[:11]
                update_fields.append('phone')

            if not user.birthday:
                import datetime

                user.birthday = datetime.date(1990, (index % 12) + 1, (index % 28) + 1)
                update_fields.append('birthday')

            if update_fields:
                user.save(update_fields=update_fields)
                count += 1
                self.stdout.write(f'  Usuário atualizado: {user.email} ({", ".join(update_fields)})')

        self.stdout.write(self.style.SUCCESS(f'{count} usuário(s) atualizados.'))

    def _neighborhood_for_user(self, user):
        driver = Driver.objects.filter(user=user).select_related('route_group').first()
        if driver and driver.route_group:
            return driver.route_group.name.split(' - ')[0]

        passenger = Passenger.objects.filter(user=user).select_related('route_group').first()
        if passenger and passenger.route_group:
            return passenger.route_group.name.split(' - ')[0]

        company = Company.objects.filter(user=user).first()
        if company:
            return 'Centro'

        return 'Centro'

    def _fill_companies(self):
        count = 0
        for index, company in enumerate(Company.objects.all().order_by('id')):
            update_fields = []
            addr = self._address_for(index, 'Centro')
            for field, value in addr.items():
                if not getattr(company, field):
                    setattr(company, field, value)
                    update_fields.append(field)

            if not company.contact_phone:
                company.contact_phone = f'479999{9000 + index:04d}'[:11]
                update_fields.append('contact_phone')

            if not company.contact_email:
                company.contact_email = f'contato{index}@{company.trade_name.lower().replace(" ", "")}.com.br'[:255]
                update_fields.append('contact_email')

            if not company.state_registration:
                company.state_registration = f'{100000000 + index}'
                update_fields.append('state_registration')

            if not company.legal_name:
                company.legal_name = f'{company.trade_name} LTDA'
                update_fields.append('legal_name')

            if update_fields:
                company.save(update_fields=update_fields)
                count += 1
                self.stdout.write(f'  Empresa atualizada: {company.trade_name} ({", ".join(update_fields)})')

        self.stdout.write(self.style.SUCCESS(f'{count} empresa(s) atualizadas.'))

    def _fill_driver_cnh(self):
        count = 0
        for driver in Driver.objects.filter(cnh__isnull=True).select_related('user'):
            description = f'CNH de {driver.user.name}'
            document = Document.objects.create(file=_placeholder_pdf(description), description=description)
            driver.cnh = document
            driver.save(update_fields=['cnh'])
            count += 1
            self.stdout.write(f'  CNH criada para: {driver.user.email}')

        self.stdout.write(self.style.SUCCESS(f'{count} CNH(s) criada(s).'))

    def _fill_company_documents(self):
        document_fields = {
            'articles_of_association_document': 'Contrato Social',
            'state_operating_license_document': 'Licença de Operação',
            'certificate_of_good_stading_document': 'Certidão Negativa',
        }
        count = 0
        for company in Company.objects.all():
            update_fields = []
            for field, label in document_fields.items():
                if getattr(company, field) is None:
                    description = f'{label} de {company.trade_name}'
                    document = Document.objects.create(file=_placeholder_pdf(description), description=description)
                    setattr(company, field, document)
                    update_fields.append(field)

            if update_fields:
                company.save(update_fields=update_fields)
                count += len(update_fields)
                self.stdout.write(f'  Documentos criados para: {company.trade_name} ({", ".join(update_fields)})')

        self.stdout.write(self.style.SUCCESS(f'{count} documento(s) de empresa criado(s).'))

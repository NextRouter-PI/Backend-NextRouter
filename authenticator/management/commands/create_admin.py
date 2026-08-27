import os

from django.core.management.base import BaseCommand

from authenticator.models import User


class Command(BaseCommand):
    help = (
        'Cria (ou atualiza a senha de) um superusuário de forma não interativa, lendo '
        'DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD e DJANGO_SUPERUSER_CPF do '
        'ambiente. Pensado para rodar automaticamente no passo de release do deploy '
        '(plataformas como o Fabroku não oferecem um terminal interativo para o '
        "'createsuperuser' padrão). Se as variáveis não estiverem definidas, não faz "
        'nada e termina com sucesso, para nunca quebrar o deploy.'
    )

    def handle(self, *args, **options):
        email = os.getenv('DJANGO_SUPERUSER_EMAIL')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
        cpf = os.getenv('DJANGO_SUPERUSER_CPF', '00000000000')
        name = os.getenv('DJANGO_SUPERUSER_NAME', 'Administrador')

        if not email or not password:
            self.stdout.write(
                'DJANGO_SUPERUSER_EMAIL/DJANGO_SUPERUSER_PASSWORD não definidos, pulando criação do superusuário.'
            )
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'name': name, 'cpf': cpf, 'is_staff': True, 'is_superuser': True},
        )

        if created:
            user.set_password(password)
            user.save(update_fields=['password'])
            self.stdout.write(self.style.SUCCESS(f'Superusuário criado: {email}'))
            return

        if not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['is_staff', 'is_superuser'])

        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write(self.style.SUCCESS(f'Superusuário já existia, senha atualizada: {email}'))

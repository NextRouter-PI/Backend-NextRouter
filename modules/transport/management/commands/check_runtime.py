from django.core.management.base import BaseCommand, CommandError

from app.runtime_checks import check_runtime


class Command(BaseCommand):
    help = 'Confere dependências, schema, estáticos e identidade do artefato; nunca aplica migrations.'

    def add_arguments(self, parser):
        parser.add_argument('--backend-only', action='store_true')

    def handle(self, *args, **options):
        try:
            check_runtime(require_frontend=not options['backend_only'])
        except Exception:
            raise CommandError(
                'Runtime indisponível: confira serviços, storage, migrations, estáticos e artefato identificado.'
            ) from None
        self.stdout.write('Runtime validado; persistência/backup e navegador exigem validações próprias.')

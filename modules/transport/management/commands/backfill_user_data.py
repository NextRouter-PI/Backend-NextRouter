from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Desativado: não fabrica documentos ou endereços pessoais para preencher dados operacionais.'

    def handle(self, *args, **options):
        raise CommandError('Backfill legado removido. Configure pontos operacionais e use fixtures explícitas em dev.')

"""Regressões da instalação limpa, inclusive referências externas ao usuário UUID."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, models
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


class MigrationSchemaTests(TestCase):
    def test_user_is_created_as_uuid_in_first_migration(self):
        loader = MigrationLoader(None)
        initial = loader.project_state([('authenticator', '0001_initial')])
        user = initial.apps.get_model('authenticator', 'User')
        self.assertIsInstance(user._meta.pk, models.UUIDField)
        self.assertTrue(user._meta.pk.primary_key)
        self.assertEqual(user._meta.pk.get_internal_type(), get_user_model()._meta.pk.get_internal_type())

    def test_all_migrated_user_references_have_matching_column_type_and_foreign_key(self):
        user = get_user_model()
        target = (user._meta.db_table, user._meta.pk.column)
        checked = set()
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, user._meta.db_table)
            user_type = next(column.type_code for column in description if column.name == user._meta.pk.column)
            for model in apps.get_models(include_auto_created=True):
                fields = [
                    field
                    for field in model._meta.local_fields
                    if isinstance(field, models.ForeignKey) and field.remote_field.model is user
                ]
                if not fields:
                    continue
                description = connection.introspection.get_table_description(cursor, model._meta.db_table)
                columns = {column.name: column.type_code for column in description}
                constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                for field in fields:
                    with self.subTest(model=model._meta.label, field=field.name):
                        self.assertEqual(columns[field.column], user_type)
                        self.assertTrue(
                            any(
                                constraint['foreign_key'] == target and constraint['columns'] == [field.column]
                                for constraint in constraints.values()
                            )
                        )
                    checked.add(model._meta.label)
        # Inclui FKs de terceiros e as duas tabelas M2M da identidade.
        self.assertTrue(
            {
                'admin.LogEntry',
                'token_blacklist.OutstandingToken',
                'authenticator.User_groups',
                'authenticator.User_user_permissions',
                'organizations.CompanyMembership',
                'router.ParticipationEvent',
            }
            <= checked
        )

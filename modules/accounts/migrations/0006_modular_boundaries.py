from django.db import migrations


MODEL_MODULES = {
    'company': 'organizations',
    'companyroutegroup': 'organizations',
    'driver': 'organizations',
    'passenger': 'organizations',
    'driverrating': 'router',
}


def move_content_types(apps, schema_editor, reverse=False):
    content_types = apps.get_model('contenttypes', 'ContentType').objects.using(schema_editor.connection.alias)
    for model, module in MODEL_MODULES.items():
        source, target = (module, 'authenticator') if reverse else ('authenticator', module)
        original = content_types.filter(app_label=source, model=model)
        if original.exists():
            if content_types.filter(app_label=target, model=model).exists():
                raise RuntimeError(f'ContentType duplicado para {target}.{model}; resolva antes de migrar.')
            # Conserva o ID referenciado por permissões, grupos e histórico do admin.
            original.update(app_label=target)


def restore_content_types(apps, schema_editor):
    move_content_types(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ('authenticator', '0005_usersession'),
        ('router', '0005_modular_boundaries'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.DeleteModel(name='DriverRating'),
            migrations.DeleteModel(name='Passenger'),
            migrations.DeleteModel(name='Driver'),
            migrations.DeleteModel(name='CompanyRouteGroup'),
            migrations.DeleteModel(name='Company'),
        ]),
        migrations.RunPython(move_content_types, restore_content_types),
        migrations.AlterModelOptions(
            name='emailtoken',
            options={'ordering': ('-created_at',), 'verbose_name': 'Código de e-mail', 'verbose_name_plural': 'Códigos de e-mail'},
        ),
        migrations.AlterModelOptions(
            name='usersession',
            options={'verbose_name': 'Sessão de usuário', 'verbose_name_plural': 'Sessões de usuários'},
        ),
    ]

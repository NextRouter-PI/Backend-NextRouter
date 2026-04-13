from django.db import models


class Company_Admin_Permission(models.Model):
    admin = models.OneToOneField(
        'Company_Admin',
        on_delete=models.PROTECT,
        related_name='permissions'
    )
    approve_passenger_contracts = models.BooleanField(default=False)
    approve_drivers_contracts = models.BooleanField(default=False)
    access_route_log = models.BooleanField(default=False)
    access_company_settings = models.BooleanField(default=False)
    generate_registration_links = models.BooleanField(default=False)
    create_new_admins = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Permissões de Administrador da Empresa"
        verbose_name_plural = "Permissões de Administradores das Empresas"

    def __str__(self):
        return f"Permissões de {self.admin.register_email}"

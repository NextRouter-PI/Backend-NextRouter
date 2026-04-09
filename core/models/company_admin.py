from django.db import models


class Company_Admin(models.Model):
    company = models.ForeignKey('Company', on_delete=models.PROTECT)
    register_email = models.EmailField(max_length=255, unique=True)

    class Meta:
        verbose_name = 'Administrador de Empresa'
        verbose_name_plural = 'Administradores de Empresa'

    def __str__(self):
        return self.register_email

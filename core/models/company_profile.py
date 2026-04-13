from django.db import models


class Company_Profile(models.Model):
    logo_url = models.CharField(max_length=255)
    biography = models.TextField()
    company = models.ForeignKey('Company', on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Perfil de Empresa'
        verbose_name_plural = 'Perfis de Empresa'

    def __str__(self):
        return self.company.company_name

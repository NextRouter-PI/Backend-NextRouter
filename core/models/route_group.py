from django.db import models


class Route_Group(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    group_name = models.CharField(max_length=100)
    common_address_passengers = models.TextField()

    class Meta:
        verbose_name = 'Grupo de Rota'
        verbose_name_plural = 'Grupos de Rota'

    def __str__(self):
        return f"Grupo de Rota {self.group_name} - Empresa: {self.company.company_name}"

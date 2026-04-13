from django.db import models


class Driver_Job_Opening(models.Model):
    company = models.ForeignKey('Company', on_delete=models.PROTECT)
    description = models.TextField()
    region = models.TextField()
    requirements = models.TextField()

    class Meta:
        verbose_name = 'Vaga_de_Motorista'
        verbose_name_plural = 'Vagas de Motorista'

    def __str__(self):
        return f'{self.company} - {self.region}'

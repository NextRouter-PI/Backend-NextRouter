from django.db import models


class Confirmed_Passenger(models.Model):
    passenger = models.ForeignKey('Passenger', on_delete=models.PROTECT)
    passenger_address = models.TextField()
    route = models.ForeignKey('Route', on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Passageiro_Confirmado'
        verbose_name_plural = 'Passageiros Confirmados'

    def __str__(self):
        return f'{self.passenger} - {self.route}'

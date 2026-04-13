from django.db import models


class Confirmed_Passenger(models.Model):
    passenger = models.ForeignKey('Passenger', on_delete=models.PROTECT)
    passenger_address = models.TextField()
    route = models.ForeignKey('Route', on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Confirmar Pasajero'
        verbose_name_plural = 'Confirmar Pasajeros'

    def __str__(self):
        return f'{self.passenger} - {self.route}'

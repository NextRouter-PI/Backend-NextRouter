from django.db import models


class Passenger(models.Model):
    home_address = models.TextField()
    register_phone = models.CharField(max_length=45)
    register_email = models.EmailField()
    passenger_cpf = models.CharField(max_length=14)
    password_hash = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Passageiro'
        verbose_name_plural = 'Passageiros'

    def __str__(self):
        return self.passenger_cpf

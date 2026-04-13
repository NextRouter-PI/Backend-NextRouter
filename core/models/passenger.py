from django.db import models


class Passenger(models.Model):
    home_address = models.TextField()
    register_phone = models.CharField(max_length=45)
    register_email = models.EmailField()
    passenger_cpf = models.CharField(max_length=14)
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE)
    password_hash = models.CharField(max_length=255)
    group = models.ForeignKey('Route_Group', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Passageiro'
        verbose_name_plural = 'Passageiros'

    def __str__(self):
        return f'Passageiro: {self.profile.first_name} {self.profile.last_name}'

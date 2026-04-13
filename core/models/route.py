from django.db import models


class Route(models.Model):
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE)
    route_type = models.CharField(max_length=20)
    started_at = models.DateTimeField()
    real_time_driver_tracking = models.TextField()
    finished_at = models.DateTimeField(null=True, blank=True)
    trip_report = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Rota'
        verbose_name_plural = 'Rotas'

    def __str__(self):
        return f'Rota de {self.driver} - {self.route_type}'

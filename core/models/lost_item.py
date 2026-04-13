from django.db import models


class Lost_Item(models.Model):
    route_session = models.ForeignKey('Route', on_delete=models.PROTECT)
    passenger = models.ForeignKey('Passenger', on_delete=models.PROTECT)
    item_description = models.TextField()
    reported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Item Perdido'
        verbose_name_plural = 'Itens Perdidos'

    def __str__(self):
        return f'Item Perdido: {self.item_description}'

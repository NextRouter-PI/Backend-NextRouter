from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.driver import Driver
from authenticator.models.user import User

MIN_SCORE = 1
MAX_SCORE = 5


class DriverRating(models.Model):
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        verbose_name=_('Motorista'),
        related_name='ratings',
    )

    passenger = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('Passageiro'),
        related_name='driver_ratings_given',
    )

    travel = models.ForeignKey(
        'router.Travel',
        on_delete=models.CASCADE,
        verbose_name=_('Viagem'),
        related_name='driver_ratings',
        null=True,
        blank=True,
    )

    score = models.PositiveSmallIntegerField(
        verbose_name=_('Nota'),
        validators=[MinValueValidator(MIN_SCORE), MaxValueValidator(MAX_SCORE)],
    )

    comment = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Comentário'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data da avaliação'),
    )

    class Meta:
        verbose_name = _('Avaliação de motorista')
        verbose_name_plural = _('Avaliações de motoristas')
        db_table = 'authenticator_driver_rating'
        constraints = (
            models.UniqueConstraint(fields=['driver', 'passenger', 'travel'], name='unique_rating_per_travel'),
        )
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.score}/5 para {self.driver.user.name.title()} por {self.passenger.name.title()}'

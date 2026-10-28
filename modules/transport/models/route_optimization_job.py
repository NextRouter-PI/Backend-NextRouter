from typing import ClassVar

from django.db import models

from modules.transport.models.path import Path


class RouteOptimizationJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        RUNNING = 'running', 'Processando'
        DONE = 'done', 'Concluído'
        FAILED = 'failed', 'Falhou'

    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='optimization_jobs')
    passenger_ids = models.JSONField()
    start = models.JSONField()
    end = models.JSONField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=255, blank=True)
    available_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=['status', 'available_at'])]

    def __str__(self) -> str:
        return f'Job #{self.pk} - {self.status}'

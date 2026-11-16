from typing import ClassVar

from django.db import models


class RouteOptimizationJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        RUNNING = 'running', 'Processando'
        DONE = 'done', 'Concluído'
        FAILED = 'failed', 'Falhou'

    snapshot = models.ForeignKey('router.RouteSnapshot', on_delete=models.PROTECT, related_name='optimization_jobs')
    input_revision = models.PositiveIntegerField()
    frozen_input = models.JSONField(default=dict, blank=True)
    claim_token = models.UUIDField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=255, blank=True)
    available_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=['status', 'available_at'])]
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(input_revision__gte=1),
                name='job_input_revision_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(claim_token__isnull=True, claim_expires_at__isnull=True)
                | models.Q(claim_token__isnull=False, claim_expires_at__isnull=False),
                name='job_claim_pair',
            ),
            models.CheckConstraint(
                condition=~models.Q(status='running') | models.Q(claim_token__isnull=False),
                name='new_running_job_requires_claim',
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=['pending', 'running', 'done', 'failed']), name='job_status_valid'
            ),
        ]

    def __str__(self) -> str:
        return f'Job #{self.pk} - {self.status}'

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        from .validation import related_values

        snapshot = related_values(self, 'snapshot', 'base_revision', 'input_data')
        if snapshot and (
            snapshot['base_revision'] != self.input_revision or snapshot['input_data'] != self.frozen_input
        ):
            raise ValidationError('A revisão e as entradas do job devem corresponder ao snapshot.')

"""Logs por allowlist: não serializa request, mensagem livre, argumentos ou traceback."""

import json
import logging
from datetime import UTC, datetime
from math import isfinite

ALLOWED_EVENTS = frozenset({'worker_cycle', 'worker_stopped', 'email_delivery_failed'})
ALLOWED_NUMERIC_FIELDS = {
    'worker_cycle': ('schedules', 'days', 'jobs', 'duration_ms'),
}


def _valid_nonnegative_number(value) -> bool:
    return type(value) in (int, float) and isfinite(value) and value >= 0


class OperationalFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'time': datetime.fromtimestamp(record.created, UTC).isoformat(),
            'level': record.levelname,
            'event': 'runtime_event',
        }
        op_event = getattr(record, 'op_event', None)
        if isinstance(op_event, str) and op_event in ALLOWED_EVENTS:
            payload['event'] = op_event
            op_fields = getattr(record, 'op_fields', None)
            allowed_keys = ALLOWED_NUMERIC_FIELDS.get(op_event, ())
            if isinstance(op_fields, dict) and allowed_keys:
                for key in allowed_keys:
                    value = op_fields.get(key)
                    if _valid_nonnegative_number(value):
                        payload[key] = int(value)
        elif record.msg == 'worker_cycle schedules=%d days=%d jobs=%d duration_ms=%d' and (
            isinstance(record.args, tuple)
            and len(record.args) == 4
            and all(_valid_nonnegative_number(value) for value in record.args)
        ):
            payload['event'] = 'worker_cycle'
            payload.update(zip(('schedules', 'days', 'jobs', 'duration_ms'), map(int, record.args), strict=True))
        elif record.msg == 'worker_stopped reason=%s':
            payload['event'] = 'worker_stopped'
        elif record.msg == 'email_token_delivery_failed reason=%s':
            payload['event'] = 'email_delivery_failed'

        status = getattr(record, 'status_code', None)
        if type(status) is int and 100 <= status <= 599:
            payload['status'] = status
        return json.dumps(payload, sort_keys=True)

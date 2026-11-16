"""Logs por allowlist: não serializa request, mensagem livre, argumentos ou traceback."""

import json
import logging
from datetime import UTC, datetime
from math import isfinite


class OperationalFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'time': datetime.fromtimestamp(record.created, UTC).isoformat(),
            'level': record.levelname,
            'event': 'runtime_event',
        }
        if record.msg == 'worker_cycle schedules=%d days=%d jobs=%d duration_ms=%d' and (
            isinstance(record.args, tuple)
            and len(record.args) == 4
            and all(type(value) in (int, float) and isfinite(value) and value >= 0 for value in record.args)
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

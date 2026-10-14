"""Small, flushed supervisor event log; never records credentials or payloads."""
from datetime import datetime, timezone
import json
import time


class SessionJournal:
    def __init__(self, path):
        self.path = path
        # Fail before starting workers if the diagnostic destination is unusable.
        with path.open('x', encoding='utf-8'):
            pass

    def record(self, event, **details):
        row = dict(utc=datetime.now(timezone.utc).isoformat(),
                   monotonic_s=time.monotonic(), event=event, **details)
        try:
            with self.path.open('a', encoding='utf-8') as output:
                output.write(json.dumps(row, ensure_ascii=True) + '\n')
                output.flush()
        except OSError as error:
            # A full disk must not interrupt the controlled shutdown path.
            print('[SUPERVISOR LOG FAILED]', self.path, str(error), flush=True)

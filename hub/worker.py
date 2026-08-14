"""Background consumer: drain topics with retry + DLQ (already in FileBus.consume)."""
from __future__ import annotations

import time

from hub.bus import TOPICS, bus
from hub.db import init_db


def main() -> None:
    init_db()
    print("worker listening on", TOPICS)
    while True:
        n = 0
        for topic in TOPICS:
            n += bus.consume(topic, lambda env: None)
        if n:
            print("processed", n, "backlog", bus.backlog())
        time.sleep(2)


if __name__ == "__main__":
    main()

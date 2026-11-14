"""Allow the sequential Piper (45 s) + Rhubarb probe (up to 60 s) to finish.

Loaded automatically by Gunicorn from this working directory. Explicit CLI or
GUNICORN_CMD_ARGS values take precedence; use at least 130 s there for the probe.
"""

timeout = 130

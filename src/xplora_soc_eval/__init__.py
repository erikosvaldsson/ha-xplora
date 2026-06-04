"""Evaluation harness for pyxplora-api focused on battery SoC supervision.

Goal: assess whether pyxplora-api is a viable foundation for a Home Assistant
integration that monitors battery state-of-charge across multiple watches.
"""

from .main import main

__all__ = ["main"]

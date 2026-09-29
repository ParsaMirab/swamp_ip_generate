"""Conversation states used by the admin panel."""

from __future__ import annotations

from enum import IntEnum


class AdminState(IntEnum):
    """States of the admin conversation."""

    WAITING_FOR_IP = 1

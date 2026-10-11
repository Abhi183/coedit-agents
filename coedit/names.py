"""Stable, human-readable agent names when none is configured."""

from __future__ import annotations

import os
import random

_ADJECTIVES = ("amber", "brisk", "calm", "deft", "eager", "fleet", "keen", "lucid", "nimble", "quiet")
_ANIMALS = ("otter", "heron", "lynx", "finch", "badger", "ibis", "marten", "newt", "osprey", "vole")


def agent_name() -> str:
    """COEDIT_AGENT if set, else a random adjective-animal pair seeded from the pid."""
    configured = os.environ.get("COEDIT_AGENT", "").strip()
    if configured:
        return configured
    rng = random.Random(os.getpid())
    return f"{rng.choice(_ADJECTIVES)}-{rng.choice(_ANIMALS)}"

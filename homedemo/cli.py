"""Command-line options shared by `python -m homedemo` and `python -m homedemo.play`."""
from __future__ import annotations

import argparse

from .contracts import Settings


def add_decider_args(ap: argparse.ArgumentParser) -> None:
    """Shared by python -m homedemo and homedemo.play."""
    defaults = Settings()
    ap.add_argument("--escalate", default=defaults.escalate_to, choices=["bedrock", "12b"],
                    help="who decides when the 2B is unsure (cascade mode)")
    ap.add_argument("--decider-2b-url", default=defaults.decider_2b_url)
    ap.add_argument("--decider-12b-url", default=defaults.decider_12b_url)
    ap.add_argument("--bedrock-region", default=defaults.bedrock_region)
    ap.add_argument("--bedrock-profile", default=defaults.bedrock_profile,
                    help="AWS profile for Bedrock ('' = default credential chain)")


def settings_from_args(a: argparse.Namespace, **extra) -> Settings:
    return Settings(decider_mode=a.mode, escalate_to=a.escalate, decider_2b_url=a.decider_2b_url,
                    decider_12b_url=a.decider_12b_url, bedrock_profile=a.bedrock_profile or None,
                    bedrock_region=a.bedrock_region, **extra)

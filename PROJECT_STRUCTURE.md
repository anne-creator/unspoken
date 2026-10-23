# Unspoken project structure

Author: Anne. License: MIT, with third-party notices preserved.

## Structure

`homedemo/` contains the simulator, event bus, agents, model adapters, scenarios and FastAPI web interface. `tests/` mirrors those modules. `eval/` contains evaluation cases, runners and dated reports. `deploy/` contains portable systemd/Nginx installation scripts and the opt-in BF16 CPU patch. `docs/` documents public hosting.

## Workflow

Install with `python -m pip install -e '.[dev]'`, run `python -m pytest -q`, and use `python -m homedemo --mode fake` for local UI development. Real inference requires a separate 2B model server; cascade mode additionally uses Bedrock. Commit functional changes separately and update relevant documentation.

## Inputs and outputs

Scenario steps and browser actions generate simulated sensor events. The 2B model and optional Haiku escalation propose actions. Plain-code policy permits, asks or denies; the actuator changes simulated devices and sends simulated notifications. REST and SSE expose the shared home to the UI. The root welcome page serves the walkthrough; `/demo` serves the interactive application.

## Data and features

No model weights or runtime traces are checked in. The walkthrough video is included as a self-hosted media asset. Third-party UI/3D assets retain their licenses. Python dependencies and model revisions are pinned for the deployment scripts. Hosted mode limits selectable models, reports model health, identifies simulated inputs and actual compute location, and avoids fake-model fallback in real modes.

## Public release

This repository is assembled from reviewed project files using separate commits. It excludes private hosting bundles, account-specific provisioning, credentials, local workspace paths, operational resource inventories and local activity history. Changes to the public project should be made in this checkout.

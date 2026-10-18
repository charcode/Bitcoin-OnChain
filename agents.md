# Agents Guide

This file is the canonical bootstrap document for AI agents working in this repository.

## Required Reading Order

1. Read this file fully.
2. Read [architecture.md](architecture.md).
3. Read [dev-protocol.md](dev-protocol.md).
4. Read [todo.md](todo.md).
5. Read [README.md](README.md).
6. Recursively read any Markdown files linked from those files before proposing architecture changes or editing code.

If there is a conflict between documents, prefer the most specific document for the task and record the inconsistency in `todo.md`.

## Project Mission

Build a disciplined Bitcoin on-chain research system that:

- Connects to a local Bitcoin Knots node.
- Pulls historical blocks and live mempool transactions.
- Uses round-number resonance and stencil-style analysis to estimate BTC/USD from on-chain behavior.
- Keeps exchange price feeds out of the core estimator path.

## Non-Negotiable Architectural Constraints

- The core estimator must remain explainable.
- RPC access must remain encapsulated behind dedicated clients.
- Historical analysis and live mempool analysis must stay separate at the module level.
- Optional external prices may be used only for evaluation, monitoring, or comparison, not as direct estimator inputs.
- Constants and heuristics must be documented when changed.

## Agent Expectations

- Read before editing.
- Update documentation when behavior or architecture changes.
- Prefer small, reviewable changes over broad rewrites.
- Avoid adding hidden coupling between API routes, background tasks, and estimator logic.
- Add or update tests when changing deterministic logic.
- Preserve a clean separation between ingestion, feature extraction, inference, and presentation.

## Working Model

Treat the codebase as four layers:

1. Data acquisition from Knots RPC and optional Fulcrum.
2. Domain transforms such as output filtering, bucketing, and histogram construction.
3. Estimation logic such as RNR scoring and stencil alignment.
4. Delivery layers such as FastAPI routes and the frontend dashboard.

New code should fit one layer cleanly. If a feature crosses layers, define explicit interfaces instead of reaching across modules directly.

## Documentation Rules

- Keep root Markdown files current.
- Document major assumptions, especially around round-dollar anchors, transaction eligibility filters, histogram ranges, and smoothing constants.
- Do not leave architecture decisions implicit in code alone.

## Research Discipline

- Favor reproducibility over convenience.
- Make experimental code easy to isolate or remove.
- Prefer named calibration datasets and fixtures over magic constants with no provenance.
- When adding a heuristic, state what signal it is trying to capture and how it can fail.

## Definition Of Done

A task is not done until:

- The code change is coherent and scoped.
- Documentation is updated if behavior changed.
- Tests were added or existing test coverage was evaluated.
- Risks, assumptions, and unresolved questions are surfaced clearly.

## Linked Documents

- [architecture.md](architecture.md)
- [dev-protocol.md](dev-protocol.md)
- [todo.md](todo.md)
- [README.md](README.md)
- [claude.md](claude.md)
- [gemini.md](gemini.md)

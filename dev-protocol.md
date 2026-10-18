# Development Protocol

This document defines the engineering protocol for the Bitcoin On-Chain project. All contributors and AI agents should follow it.

## Core Principles

- Prefer correctness over speed of delivery.
- Prefer modularity over convenience.
- Prefer deterministic logic over opaque heuristics.
- Prefer explainable estimators over black-box models.
- Keep operational code separate from research experiments.

## Architectural Protocol

### 1. Encapsulation

- Do not spread Bitcoin RPC calls across the codebase.
- Put network access behind dedicated clients and small interfaces.
- Do not let API handlers contain business logic.
- Keep background loop orchestration separate from inference code.
- Keep estimator internals independent from UI concerns.

### 2. Modularity

Each module should have one clear responsibility:

- Ingestion modules fetch or cache blockchain data.
- Transform modules filter, normalize, bin, and summarize outputs.
- Inference modules score hypotheses and produce estimates.
- Presentation modules expose responses or render charts.

If a file starts doing two or more of these jobs, split it.

### 3. Pure Logic First

For any algorithmic change:

- Put the core math into pure functions where possible.
- Keep inputs and outputs explicit.
- Avoid hidden state.
- Avoid using live RPC dependencies inside scoring functions.

This is mandatory for resonance scoring, histogram construction, and stencil placement logic.

## Testing Protocol

### 1. Unit Tests Are Mandatory For Deterministic Logic

Any change to the following areas should include unit tests:

- Round-number scoring
- Grid aggregation
- Histogram smoothing
- Stencil slide selection
- Neighbor-slide interpolation
- Transaction inclusion and exclusion rules
- Distribution binning

### 2. Integration Tests

Add integration tests for:

- RPC client behavior against mocked node responses
- API routes with valid and invalid parameters
- Historical block range resolution
- Error paths for timeout, empty data, and unavailable dependencies

### 3. Fixture Strategy

- Use small, named fixtures for synthetic transactions and output histograms.
- Add historical block fixtures for known periods when testing stencil behavior.
- Do not make tests depend on a live node unless explicitly marked as manual or integration-only.

### 4. Regression Discipline

When fixing a bug:

1. Reproduce it in a test.
2. Fix it.
3. Keep the test.

## Code Organization Protocol

### Allowed dependencies

- API modules may depend on core modules and models.
- Core modules may depend on shared models and types.
- RPC modules should not depend on API modules.
- Frontend code must never define backend business logic.

### Avoid

- Circular imports
- Route-level data science logic
- Shared mutable global state for estimator internals
- Copy-pasted threshold constants across files

## Configuration Protocol

- All runtime tuning must come from config or named constants.
- Environment variables should have clear defaults and names.
- If a config value changes the meaning of an estimator, document it in `README.md` and relevant research notes.
- Experimental flags should be clearly labeled and easy to disable.

## Documentation Protocol

Update Markdown docs when:

- A module boundary changes
- A new subsystem is introduced
- A heuristic is added or recalibrated
- Setup or runtime steps change
- The meaning of an API response changes

At minimum, update `README.md`. If the change affects agent workflow or engineering policy, update `agents.md` or this file too.

### Feature Continuity Protocol

To make interrupted work recoverable:

- Before substantial implementation work, add the active feature at the top of `todo.md`.
- Maintain a root `feature-progress.md` file for the feature currently in progress.
- Update `feature-progress.md` as work advances so another session can resume after an app crash or interrupted run.
- `feature-progress.md` should include:
  - objective
  - current status
  - files being changed
  - completed steps
  - next steps
  - known blockers or open questions

If the active feature changes, move the old entry down in `todo.md` and overwrite `feature-progress.md` with the new active work.

## Review Protocol

Every meaningful change should be checked for:

- Correctness
- Testability
- Modularity
- Encapsulation
- Failure handling
- Documentation drift

Reviewers should look specifically for hidden coupling between:

- RPC transport and estimator logic
- Historical block analysis and live mempool analysis
- External price comparison code and the core estimator

## Bitcoin-Specific Best Practices

- Keep all BTC-to-USD inference assumptions explicit.
- Document which round-dollar anchors matter and why.
- Validate transaction filters carefully to avoid sampling bias.
- Treat coinbase, OP_RETURN-heavy, and anomalous witness structures deliberately rather than incidentally.
- Be explicit about whether a metric is based on mempool, historical blocks, or both.
- Keep time-window logic and block-range logic deterministic and reviewable.

## Safety Protocol For Research Claims

- Do not present the estimator as a trading oracle.
- Distinguish clearly between experimental signals and validated signals.
- When comparing against external prices, label that path as evaluation or monitoring.
- Record confidence limitations and known failure modes.

## Delivery Checklist

Before closing a task, verify:

- Architecture still respects module boundaries.
- New logic is covered by tests or a documented testing gap exists.
- Docs reflect the current state.
- New constants and heuristics are named and explained.
- The change can be understood without reverse-engineering intent from the implementation.

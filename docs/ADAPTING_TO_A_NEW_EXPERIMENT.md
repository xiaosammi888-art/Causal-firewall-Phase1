# Adapting the Causal Firewall to a New Experiment

## Purpose

The reusable contribution is the separation between experiment-specific content and a stable information-control workflow. A new study should replace the experiment contract, access registry, response schema, and outcome coding while retaining the policy engine, packet builder, request audit, outcome lock, and release process.

## What remains stable

- tagged fields with declared provenance;
- centralized policy evaluation;
- participant, arm, and stage scope checks;
- deny-by-default handling of missing or unknown fields;
- canonical packet and request hashing;
- stateless provider-request construction;
- strict response validation and single-write outcome locking;
- deterministic fault injection;
- public-data sanitization and allowlist-based release building.

## What must be replaced

- source experiment and citation;
- population claim and persona construction;
- treatment arms and participant-visible stimuli;
- legal response schema;
- deterministic outcome coding;
- human benchmark, if one is available and licensed for use;
- experiment-specific prohibited fields and canaries;
- behavioral design, estimands, sample size, and analysis plan.

## Adaptation workflow

### 1. Create a new study identity

Assign a new study ID and semantic contract version. Do not overwrite `CF-P1-001`. Record the source citation, intended inferential role, population claim, and whether the run is engineering, developmental, or confirmatory.

### 2. Write the experiment contract

Create a machine-readable contract that freezes:

- source materials and their hashes;
- treatment arms and assignment rules;
- participant-visible instructions and legal options;
- response schema;
- deterministic outcome coding;
- field order and request configuration;
- planned estimands and benchmark references;
- registered canaries and prohibited information.

The contract should be reviewed before any provider call. A changed contract must receive a new version and invalidate authorization based on the old hash.

### 3. Register every field

For every workflow field, record:

- direct information label;
- upstream lineage;
- participant scope;
- treatment-arm scope;
- stage scope;
- whether the field is required, optional, or prohibited.

Derived summaries must retain the most restrictive label in their lineage. A new or unlabeled field should fail closed rather than silently enter the model context.

### 4. Build the clean participant packet

Construct persona information before treatment exposure. Add only the current arm's scenario and legal response options. Ensure that identifiers, replicate labels, research hypotheses, expected effects, human outcomes, and audit findings are absent from model-visible content unless the contract explicitly defines a legitimate participant-facing role.

### 5. Register study-specific faults

Retain the common F0–F7 suite and add faults suggested by the new workflow. Examples include retrieval contamination, shared memory, planner summaries, tool outputs, reviewer feedback, retries, and cross-participant state. Each fault should specify the carrier, prohibited source, expected policy decision, and expected model-visible hash.

### 6. Pass zero-cost gates

Before enabling a network transport:

1. validate contract and policy schemas;
2. run unit tests;
3. run deterministic packet-level fault tests;
4. serialize the exact provider-shaped requests without sending them;
5. verify canary exclusion and clean-hash invariance;
6. generate and review the complete execution schedule.

### 7. Add paid execution only after review

Use staged call-count and cost gates. Begin with connectivity and clean-path micro-smokes, then test the architecture matrix, model-parameter compatibility, and only then the full run. The transport should send one request, store no conversation state, expose no tools unless required by the contract, and contain no automatic retry loop.

### 8. Lock outcomes and separate audit

Validate one legal response, deterministically derive the outcome, and prevent later writes. Audit components may inspect packets, requests, decisions, and hashes but must never send audit findings back to the simulated participant.

## Minimum acceptance criteria for a new worked example

- the clean request contains every required participant-facing field;
- opposite-arm and research-restricted information is absent;
- derived restricted content remains restricted under renaming or summarizing;
- missing labels fail closed;
- model-visible requests are hash-invariant across hidden research cues under
  the firewall architecture;
- outcome coding is deterministic and single-write;

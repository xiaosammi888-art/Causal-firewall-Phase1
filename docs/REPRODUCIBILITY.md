# Phase 1 Reproduction Guide

From the repository root, run:

```bash
python3 scripts/reproduce_study0_offline.py
```

## Software requirements

- Python 3.10 or later;
- no required third-party Python packages;
- macOS only for the included Keychain helper;
- internet access and a funded provider account only for paid replication.

The policy file uses JSON syntax within a `.yaml` file. JSON is a subset of YAML 1.2, which allows the standard library to load the policy without PyYAML.

## Reproduction stages

### Stage 1 Contract and policy

`experiments/CF-P1-001/experiment_contract.json` fixes the source materials, population claim, treatment arms, response schema, deterministic outcome code, human benchmark, prohibited information, field order, and canaries.

`experiments/CF-P1-001/access_policy.yaml` defines label ranks, respondent permissions, field provenance, arm scope, and deny-by-default rules. Editing either file changes its hash and invalidates downstream dry-run authorization.

### Stage 2 Deterministic fault audit

```bash
python3 scripts/run_no_api_audit.py
```

This stage compares four architectures under F0 through F7: clean input, shared history, contaminated summary, reused session, contaminated retry, tool leakage, auditor backflow, and label loss. It makes no model call. The purpose is to prove packet-level reachability and fail-closed behavior before provider code is enabled.

### Stage 3 Provider request audit

```bash
python3 scripts/run_provider_dry_run.py
```

This stage serializes the exact Responses request shape. It checks that D contains no forbidden field or canary, that its model-visible hash matches the clean request under F0 through F6, and that F7 cannot be serialized. It also checks that storage is disabled, tools are empty, and conversation state is absent. The adapter contains no HTTP method.

### Stage 4 Live engineering gates

The historical paid sequence was:

1. one neutral connectivity request;
2. four clean-path D requests across two arms;
3. twenty-four architecture-arm-cue requests;
4. one `temperature: 1.0` compatibility request;
5. 288 developmental behavioral requests.

Each command required an exact paid-call count and a dollar cap. The 288-call runner wrote every completed outcome immediately, printed progress after each 24 calls, stopped on an invalid response, and performed no automatic retry.

These historical calls do not need to be repeated to reproduce the published analysis. Use the sanitized data in `data/CF-P1-001`.

### Stage 5 Public analysis

The public outcome file contains one row per API draw. Recalculate the 24 cell
rates, Delta, Gamma, shared no-cue baseline, and Clopper-Pearson intervals from
`study0_behavioral_smoke_v2_public.csv`. Compare the result with
`study0_analysis.json`.

Verify release integrity with:

```bash
python3 scripts/verify_public_release.py
```

## Paid replication

Paid replication creates a new run and must be described as such. A provider may retire a snapshot, change infrastructure, or return different stochastic draws even when request bytes are unchanged.

On macOS, store a key without writing it to disk:

```bash
./scripts/configure_openai_keychain.sh --expect-suffix YOUR_KNOWN_SUFFIX
python3 scripts/check_openai_keychain.py --expect-suffix YOUR_KNOWN_SUFFIX
```

On Linux or Windows, provide `OPENAI_API_KEY` through a shell or secret manager. Do not create a dotenv file. Then follow the commands in the root README, using current dry-run and gate paths. Read each script's `--help` before execution.

## Expected differences in an independent replication

An independent replication should reproduce deterministic hashes only when the contract, policy, request adapter, model snapshot, and canonical serialization are identical. Behavioral draws may differ. A changed provider snapshot, temperature, prompt, source material, schema, or policy defines a new version and should receive a separate run identifier.

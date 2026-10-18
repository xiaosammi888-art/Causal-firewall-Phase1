#Study 0 Technical and Experimental Guide

## Purpose and result

Study 0 built and tested one complete causal-firewall workflow for an LLM-simulated experiment. The workflow starts with a human-readable experiment, converts it into a machine-readable contract, enforces field-level information rules before the model call, locks the behavioral outcome, and audits every request without feeding audit information back to the respondent.
The system passed every registered technical gate. The behavioral smoke also showed directional cue sensitivity when hidden research expectations reached A (monolithic prompt), B (default multi-agent), or C (manual whitelist). D (causal firewall) blocked those expectations. 

## Source experiment

The pilot is Gordon-Hecker et al. (2017), Experiment 1b, identified as JEP_4_1b in the Cui et al. (2025) replication archive. Tal and Gal are equally deserving of one indivisible concert ticket. In the human-allocation arm, the respondent gives the ticket to Tal, gives it to Gal, or discards it. In the random-allocation arm, the respondent gives the ticket to Tal, gives it to Gal, or discards it. In the random-allocation arm, the respondent uses a random device or discards the ticket. The binary outcome is whether the ticket is discarded.
The human benchmark was 25 of 88 discards under human allocation and 7 of 90 under random allocation, a risk difference of 0.2063. The minimal synthetic persona did not claim to reproduce the original student population.

## Information model

The system classifies each field before it reaches the respondent:

| Information class | Example | Respondent access |
|---|---|---:|
| Participant visible | Current scenario and legal options | Allowed |
| Participant self | Frozen pre-treatment persona state | Allowed for the same participant |
| Research restricted | Hypothesis and expected direction | Denied |
| Embargoed result | Human benchmark | Denied |
| System only | Session and retry state | Denied |
| Audit only | Leakage findings | Denied |

A derived field inherits the most restrictive label in its lineage. This rule is what distinguishes C from D when a participant-visible summary was derived from a restricted hypothesis.

## System components

`PopulationBuilder` creates the minimal persona before treatment presentation. `PolicyEngine` evaluates the declared label, inherited labels, participant, arm, stage, and registry entry. `PacketBuilder` includes only allowed fields in a canonical order and refuses to run when a required field disappears.
`OpenAIResponsesDryRunAdapter` converts the approved packet into a stateless request with strict JSON output, no tools, `store: false`, and no conversation identifier. `OutcomeLock` accepts one legal choice and derives `discard_reward`; it rejects later writes. The audit code records decisions and hashes but never sends restricted values back to the respondent.
The live transport sends exactly one request and contains no retry loop. Paid runner scripts implement call-count and cost gates outside the transport.

## Architecture conditions
  
A places every field in one model-visible packet. It represents a monolithic prompt that relies on instructions rather than enforcement.
B also passes every field but represents information received through a default multi-agent handoff. Its distinct carrier is `handoff_history`.
C starts with a fresh context and a field-name whitelist. It blocks unknown names but cannot detect that an apparently acceptable summary inherited restricted content.
D starts with a fresh context and uses the same workflow fields as C. It applies registered labels, provenance inheritance, arm scope, participant scope, and deny-by-default rules before serialization.

## Fault tests

F0 is the clean workflow. F1 injects opposite-arm information through shared history. F2 injects the hypothesis through a derived summary whose direct label looks permissible. F3 reuses session content. F4 carries context through a retry. F5 returns the embargoed human result through a tool. F6 sends auditor
feedback backward. F7 removes a required label.

D removed every injected field in F1 through F6 while preserving the clean packet hash. F7 stopped before request serialization. C failed specifically when a whitelisted operational field contained restricted lineage, showing the incremental value of provenance-aware labels over field names alone.

## Behavioral design

The final design used one canonical persona and twelve independent API draws in each of 24 architecture-arm-cue cells. Replicate identifiers appeared only in API metadata. The factors were four architectures, two allocation arms, and three research-hypothesis cues: none, aligned, and reversed. This produced 288 calls.

For each architecture and cue, Delta was the difference in discard rates between human and random allocation. Gamma was aligned Delta minus reversed Delta. Positive Gamma means that the treatment-effect estimate changed in the direction of the hidden research expectation.

## Execution sequence

The project did not begin with 288 paid calls. It first passed 48 unit tests, 8 of 8 deterministic firewall gates, 8 of 8 provider-request gates, a neutral connectivity request, four clean-path calls, a 24-cell architecture probe, a 288-row zero-cost schedule audit, and one temperature compatibility request.

The final run fixed `gpt-5.4-mini-2026-03-17`, reasoning effort `none`, temperature 1.0, maximum output 64 tokens, strict structured output, no tools, and `store: false`. All 288 calls completed. The run produced 75,168 input tokens, 3,930 output tokens, and 79,098 total tokens. Estimated cost was USD 0.074061.

## Results

Gamma was 0.500 in A, 0.250 in B, 0.417 in C, and 0.083 in D. All exposed architectures therefore showed a positive directional contrast. D's inference payload was identical across cue labels, so its small difference was sampling variation.

The no-cue requests were byte-equivalent across architectures and can be pooled. The model discarded in 48 of 48 human-allocation draws and 3 of 48 random-allocation draws, for Delta 0.9375. The model therefore reproduced the human benchmark's direction but greatly overstated its magnitude.

The result separates two validity questions. The firewall answered whether prohibited research information reached the respondent. It did not answer whether the resulting respondent behaved like the human target population.

## Public release

Raw paid-run artifacts remain local. The public CSV contains the experimental factors, choices, deterministic outcomes, token use, and request-equivalence hashes. It removes provider response identifiers, authorization metadata, and local paths. The release manifest records a SHA-256 digest for every public file. The offline reproduction script verifies those hashes and reruns all deterministic tests without an API key.

## References
Gordon-Hecker, T., Rosensaft-Eshel, D., Pittarello, A., Shalvi, S., & Bereby-Meyer, Y. (2017). Not taking responsibility: Equity trumps efficiency in allocation decisions. Journal of Experimental Psychology: General, 146(6), 771–775. https://doi.org/10.1037/xge0000273
Cui, Z., Li, N., & Zhou, H. (2025). A large-scale replication of scenario-based experiments in psychology and management using large language models. Nature Computational Science, 5, 627–634. https://doi.org/10.1038/s43588-025-00840-7

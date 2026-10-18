# Study 0 public data codebook

`study0_behavioral_smoke_v2_public.csv` contains one row per API response draw. The response identifier and local authorization record were removed. Hashes are retained to verify request equivalence and information-flow invariance.

- `architecture`: A monolithic, B default handoff, C manual whitelist, or D labeled firewall.
- `arm`: human allocation or random allocation.
- `cue`: no research hypothesis, aligned hypothesis, or reversed hypothesis.
- `choice`: model output after strict schema validation.
- `discard_reward`: deterministic binary coding of `choice`.
- `model_visible_hash`: hash of instructions, input, and structured-output schema.
- `inference_payload_hash`: hash of every inference-relevant request field except API metadata.
- `carrier_present` and `canary_present`: whether the designated hidden-information carrier or canary reached the participant packet.
- `retry_id`: zero for every released row because content retries were prohibited.

`study0_cell_results.csv` contains cell counts, discard rates, and exact 95 percent Clopper Pearson intervals. `study0_analysis.json` contains Delta and Gamma estimands and the shared no-cue baseline.

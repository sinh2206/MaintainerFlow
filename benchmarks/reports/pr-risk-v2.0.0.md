# PR Risk Benchmark 2.0.0

Split: `test` (30 samples). Dataset: synthetic, manually reviewed, `CC0-1.0`; the split was fixed before runner execution.

| Strategy | Macro F1 | Accuracy | FP | FN | Brier | p95 ms | Est. USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Static-only | 0.6678 | 0.6667 | 0 | 7 | 0.2083 | 0.036400 | 0.000000 |
| AI-only | 0.5693 | 0.5667 | 2 | 9 | 0.2763 | 0.014100 | 0.005400 |
| Hybrid | 0.8380 | 0.8333 | 2 | 3 | 0.1537 | 0.010300 | 0.005400 |
| Hybrid+History | 0.9129 | 0.9000 | 2 | 1 | 0.0943 | 0.011100 | 0.006000 |

## Hybrid benefit

- Macro-F1 gain over the best single strategy: `0.1702`.
- False-negative reduction versus Static-only: `4`.
- Additional false-negative reduction from history: `2`.

Latency is locally measured and may vary. Cost is modeled; no provider call or charge occurred. The AI strategy is an offline deterministic proxy, not a hosted-model claim. A production provider, model version, tokenizer, cache policy or pricing change requires a new report version.

The committed report contains aggregate metrics and synthetic sample fingerprints only—no secrets, prompts, raw private source, Issue bodies or PR diffs.

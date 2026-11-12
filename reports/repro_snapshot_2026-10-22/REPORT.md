# VLFM ObjectNav reproduction — preliminary evaluation report

## 1. Objective

Evaluate the VLFM ObjectNav pipeline in the available Habitat environment
and compare its results with an OracleFBE frontier-exploration baseline.

This is a preliminary, single-scene evaluation, not a full reproduction of
all results reported in the original paper.

## 2. Experimental setup

- Repository commit: 584ed56008754fde7997d904983607def8328322
- Dataset: MP3D ObjectNav
- Split: train
- Scene: 17DRP5sb8fy
- Evaluation episode count: 50 per method
- Both 50-episode configurations specify seed=100 and shuffle=True.
- The exact episode IDs used by both historical runs could not be
  independently recovered. A reconstructed candidate list did not match
  the first failed episode ID visible in the OracleFBE log (11251).
  Therefore, the two historical runs are treated as independent
  single-scene evaluations, not as a verified paired comparison.
- Additional preliminary VLFM run: 5 episodes
- Trained PPO checkpoint: not used
- Habitat simulator rendering: software rendering fallback
  (`habitat_sim.gpu_device_id=-1`) because the EGL GPU configuration failed.
- Environment details and package versions are recorded in environment.txt
  and pip_freeze.txt.
- Evaluation configuration: vlfm_config.yaml

## 3. Aggregate results

| Method | Episodes | Successes | SR | SPL | SoftSPL | Mean reward | Mean distance to goal | Target detected | Stop called |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| VLFM, preliminary | 5 | 4 | 0.80 | 0.4609 | 0.4924 | 5.2848 | 0.7582 | 1.00 | 1.00 |
| VLFM | 50 | 23 | 0.46 | 0.2798 | 0.3699 | 4.0550 | 2.1833 | 0.78 | 0.78 |
| OracleFBE | 50 | 7 | 0.14 | 0.1028 | 0.2686 | 1.0926 | 4.0875 | 0.18 | 0.18 |

The 5-episode preliminary result is reported separately and is not pooled
with the 50-episode evaluation.

## 4. OracleFBE failure analysis

The saved OracleFBE log contains 43 failure records among 50 episodes:

| Failure reason | Count |
|---|---:|
| never_saw_target_did_not_travel_stairs_feasible | 40 |
| false_positive | 2 |
| false_negative | 1 |
| Total failures | 43 |

The remaining 7 episodes were successful, consistent with the aggregate
success rate of 14%.

The dominant failure category indicates that the evaluation's target-seen
and stair-feasibility logic is important when interpreting the baseline.
It does not, by itself, establish the underlying cause of each failure.

No equivalent per-episode VLFM failure distribution is reported because a
complete VLFM evaluation log was not found among the saved artifacts.

## 5. Code and infrastructure changes

The saved source patch records two changes:

1. `torch.load(..., weights_only=False)` was used to support loading
   legacy checkpoint objects with the installed PyTorch version.
2. The HTTP request timeout in `vlfm/vlm/server_wrapper.py` was increased
   from 1 to 30 seconds to accommodate slower server responses.

These changes are documented for reproducibility. In particular, the
timeout change may affect whether slow requests complete successfully and
must be considered when comparing runs.

The repository also contains generated data, downloaded weights, model
directories, outputs, and other untracked artifacts. These should not be
mistaken for source-code changes to the original method.

## 6. Investigation of false-positive failures

Inspection of `was_false_positive()` identified a potential boundary-handling
issue: negative grid indices can be accepted by NumPy as indices from the
end of an array instead of raising `IndexError`.

This is a code-level concern, not a confirmed explanation for any particular
episode. No code correction or rerun was performed as part of this
preliminary evaluation, and the reported metrics remain unchanged.

## 7. Limitations

- Evaluation was restricted to one scene and the training split.
- The 50-episode results are preliminary and do not establish generalization
  across scenes or the full benchmark.
- The trained PPO checkpoint was not used.
- OracleFBE and VLFM have different exploration mechanisms; this comparison
  is descriptive and does not establish equivalence of their information
  access or operating conditions.
- Software rendering was used after the configured EGL GPU path failed.
- A complete VLFM log for the 50-episode run was not found. Its aggregate
  metrics are taken from the saved results CSV.
- No statistical confidence intervals or multi-scene aggregate are claimed.
- Although both 50-episode configurations specify the same seed, matching
  episode IDs were not verified. The difference between their aggregate
  metrics is descriptive and must not be interpreted as a paired estimate.
- The possible grid-boundary issue remains unverified against individual
  failure episodes.

## 8. Conclusion

The VLFM pipeline was executed in the available environment and produced
a 50-episode single-scene result of SR=0.46, SPL=0.2798, and SoftSPL=0.3699.
OracleFBE produced SR=0.14, SPL=0.1028, and SoftSPL=0.2686 under the recorded
setup.

These results document a successful preliminary experimental run, but they
are insufficient to claim full reproduction of the original paper's
benchmark results. The experiment is reported without selecting episodes,
changing thresholds to improve metrics, or modifying results after the run.

## 9. Supporting artifacts

- `environment.txt`
- `git_commit.txt`
- `git_status.txt`
- `pip_freeze.txt`
- `vlfm_config.yaml`
- `vlfm_results.csv`
- `vlfm_source_changes.patch`
- `oracle_fbe_50ep.log`


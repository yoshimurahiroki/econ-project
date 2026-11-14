## Observed data and executable specifications

- `run` estimates the replacement, latent replacement, discrete and continuous-time entry, capacity-product choice, and dynamic adoption models from the CSV, Parquet or Arrow IPC table named by `data.path`; a relative path resolves against the specification's directory.
- Parquet and Arrow require `pyarrow` in the selected environment.
- The `data.columns` object maps every semantic field below to its actual table column.
- Column names must be unique; missing entries, invalid numbers, duplicate panel keys and inconsistent transitions stop the run.
- Results preserve the source path, SHA-256, row count, column map, model-specific IDs and their SHA-256, the specification hash and the producer hash.
- The policy scenario uses the estimated parameters and the supplied change.
- The continuous-time and capacity-product games also accept calibrated primitives when no data are supplied.

- Optional `data_record:{path,sha256}` binds the [existing construction record](../../../econ-data/references/research-data.md#constructed-variables-and-analysis-samples).
- The runner verifies the record and canonical table hashes through `bind_data_record`, resolves `data.path` from that record and preserves `data.columns`.
- An explicitly supplied `data.path` must identify the same table; it may be omitted when the record supplies it.
- `sample.row_id` in the record identifies each table row separately from a model's entity ID.
- The saved result carries the variable definitions in `variables` and the adopted construction specification, transformations, sample flow and actual membership comparison in `data_construction`.
- Model primitives and estimators remain those in the dynamic specification.

- For the reset-to-zero replacement, latent replacement, entry, capacity and adoption routes, `sample.included_ids` contains the identities of all validated observations supplied to the calculation.
- Native reset-then-usage replacement maps its returned `choice_sample_keys` to the canonical row IDs; its choice likelihood uses periods 1 onward.
- `data_construction.fitted_sample.additional_excluded_ids` records the resulting exclusions.
- The existing `require_common:true` condition requires exact equality with construction membership.
- The respy adapter retains native input keys under `sample.input_sample_keys` and sets `included_ids_available:false`; adopted SMM callbacks determine their own moment samples.
- A respy record with `require_common:true` fails the existing common-sample guard.
- Existing `data` specifications remain compatible.

- The two replacement models require `id`, `period`, `state`, `action`, and `next_state`.
- Each ID has unique consecutive nonnegative integer periods; action 0 maintains and advances state to `min(state+1,S-1)`, and action 1 replaces and resets to 0.
- The next row for an ID must begin in the preceding row's next state.
- The latent model requires a balanced panel with common observed periods.
- The discrete entry game requires `id`, `period`, `state`, `action_1`, `action_2`, and `next_state`; states index activity pairs `(0,0),(0,1),(1,0),(1,1)`, and the next-state index is `2*action_1+action_2`.
- Each firm's action is its next active status.
- The same panel key, timing and next-state checks apply.
- The capacity-product panel uses the same six columns with actions 0–3 and next-state index `4*action_1+action_2`.
- Continuous-time opportunity records use `id`, `period`, `state`, `firm`, `action`, and `next_state`, where firm 0 or 1 observes its revision opportunity and action 1 toggles its activity.
- Records must be ordered consecutive opportunities within each market, with a next state consistent with the recorded firm and action.

- Dynamic durable adoption requires one row per consecutive state index with `state`, `price`, `adoptions`, and `cohort_size`.
- Counts must give interior shares and prices must be nonnegative.
- Rows describe fresh cohorts of initially nonowners; the transition matrix and permanent taste distribution are supplied as fixed primitives.
- The state-specific counts determine shares for joint inversion.
- Price variation identifies the linear price coefficient under the specified exogeneity condition.

For example, a replacement specification is:

```json
{
  "model": "replacement",
  "data": {"path": "panel.csv", "columns": {"id": "bus", "period": "month", "state": "mileage", "action": "replace", "next_state": "next_mileage"}},
  "options": {"discount_factor": 0.9, "states": 5, "initial_costs": [0.2, 1.6], "finite_horizon": 8, "replacement_cost_change": 0.5},
  "adopted": {"source": "describe the observed panel and sampling design"},
  "scenario": {"description": "replacement cost rises by 0.5 utility units"}
}
```

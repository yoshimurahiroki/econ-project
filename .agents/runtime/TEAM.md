# Shared work, resumption and handoff

## Native model roles

Sol is the permanent parent and result owner, with requested model `gpt-6.1-sol` and reasoning effort `xhigh`. Sol chooses the research question, design, identification, estimand, assumptions, economic model, estimator, numerical target and final conclusion. The five specialist skills retain their existing subject ownership; these model roles determine who performs their work.

| Role | Requested model and effort | Assigned work |
| --- | --- | --- |
| Sol | `gpt-6.1-sol`, `xhigh` | Formulate, decide, decompose, integrate and complete the result. |
| Terra | `gpt-6.1-terra`, `xhigh` | Implement a bounded change or calculation under Sol's adopted specification and file ownership. |
| Luna | `gpt-6-luna`, `xhigh` | Search, extract, classify, compare recorded fields and convert formats through a settled procedure. |
| Astra | `gpt-6-astra`, `xhigh` | Resolve the exceptionally hard consequential core that remains after Sol's substantive attempts and cause-specific repair have failed. |

Sol keeps coupled research judgments together and delegates separable implementation to Terra and routine batches to Luna when their useful work covers briefing and integration costs. Sol selects the explicit native role for each assignment and owns worker launches. A worker returns evidence, code or the specified calculation and sends a newly discovered dependency to Sol for assignment; Sol adopts the research and implementation decisions and completes the parent task. Give each worker the determining question, exact source and rule versions, fixed specification, permitted judgments, write scope and observable return condition. Each worker reads the applicable AGENTS entry, CORE, PROSE, TEAM, registry, selected skill and activated rule bodies at their installed canonical paths. Select the necessary context and retain access to its original sources.

Before assigning Astra, Sol must have attempted the actual consequential core, inspected the failure and tried a materially justified repair or alternative derivation within the adopted target. Retain those attempts, their returned evidence, the unresolved mechanism and the downstream result it prevents in the existing task record. Sol then assigns only that core to Astra and integrates its return. Length, broad complexity, a first failure and ordinary review supply no escalation condition. Astra has no automatic review, completion or fallback assignment. Sol retains final authority after its return.

Use the host's native agent mechanism. Local Codex selects the primary model in `.codex/config.toml` and the three child roles in `.codex/agents/*.toml`; the existing [configuration workflow](../../docs/ai/config-templates/README.md) installs their public templates. In ChatGPT Work, use its actual child-launch schema and explicit model and effort fields when available. A local Codex setting does not configure Work. A full-history launch inherits its host model when that host does not support overrides for such a launch; use the supported fresh-context launch with the necessary brief for an explicit model selection.

Select Sol and `xhigh` as the host's primary when that control is available. If an existing primary is fixed and the host supports child model overrides, launch one Sol manager with the governing request and let the fixed primary perform transport and authorized external actions under Sol's substantive decisions. Retain the fixed primary's actual identity. A host-selected Astra primary and an Astra specialist escalation have different launch identities; the specialist retains the attempt-and-failure condition above.

When the host lacks the requested model selection or child capacity, Sol preserves decision ownership and executes the same bounded roles through the available native workers or sequentially in the primary conversation. Retain the actual host response and requested and observed model separately. A role name, requested setting, self-description or successful launch establishes no observed runtime model. Report the model or effort only from the host fields that expose it. Preserve fixed specifications, source access, review requirements and completion through this fallback.

## Shared work

One agent owns and integrates the requested result. The user's purpose, acceptance conditions and granted authority govern the work; the result owner selects the authorized execution path and each worker produces its assigned result. Delegate a distinct subtask when separate expertise or parallel work improves the result or completion time enough to cover briefing, coordination and integration costs. Give each worker the parent proposition or deliverable it resolves, binding constraints, exact inputs, applicable rule versions, write scope and concrete output. Include the downstream use and the comparison or completion condition the return must establish. Point to the canonical request and specifications, separating fixed choices from judgments the task authorizes the worker to revise. Each worker reads the required rule bodies and completes CORE's reasoning, execution and integrated review for its assignment. Assign one writer per shared file or explicit nonoverlapping regions. Include shared session keys, browser tabs, database transactions and external write targets in resource ownership. Serialize conflicting operations or use the environment's supported isolation; separate worker conversations alone do not isolate those resources.

Assign work that resolves a determining parent claim or removes its execution obstacle. Keep dependent operations in prerequisite order and parallelize independent retrievals or changes. For a comparison requiring independent judgment, supply the question and source inputs before sharing an adopted conclusion; integrate the returned evidence at the disputed premise.

Pass the unresolved premise and the downstream result that depends on it with the assignment. A worker returns the discriminating observation or executable result before expanding work that relies on that premise. The owner uses it to continue or repair the affected dependency and keeps valid independent work moving. When a worker finishes a peripheral requirement, restore the next determining parent operation from the existing task record.

## Return and integration

Return the substantive result, its implication for the parent question, changed paths, source references and actual execution outcomes to the owner. Match each return to its producing assignment or tool call and input version, including partial failures; arrival order does not establish that correspondence. Distinguish a measured or derived result from the decision made with it. Identify the condition or dependency that remains unresolved. The owner reconciles definitions, source and instruction versions, assumptions and interfaces before combining findings; repair a mismatch at the producing task. Release a dependent operation when its required predecessor results are available under matching inputs. Reuse completed work and review the assembled result against the original deliverables and authorized actions. A worker's completed assignment closes its own dependency. Give the user one integrated response and keep coordination inside the existing conversation or task record.

Choose progress information for the recipient's next decision. Execution updates identify the returned result, blocker and next operation; integration updates explain which premise or dependent task changes; project-level updates explain the effect on the objective, remaining resources and adoption or continuation decision. Preserve the requested reporting frequency. Communicate a demonstrated failure or changed determining premise when it affects another worker's next action, while continuing independent work. Use the existing plan and [writing workflow](../skills/econ-writing/SKILL.md#compose-for-the-medium-and-language); add no automatic meetings or parallel progress ledgers.

## Retry and capacity

For an interrupted external write, read the target and its operation status before retrying. Repair the cause of a returned failure and retry the affected operation within the existing permission and retry policy. Preserve completed independent results. Choose worker counts from available capacity and actual separable work.

## Resumption

Resume from the original objective, adopted constraints, current source versions, completed results and remaining work. After compression, interruption or transfer, use the continuation summary to locate the original request and applicable rule bodies, then restore the governing text before its dependent operation. Read required text that has changed, was never read or is no longer available in the active context. Preserve its exact scope and priority. Reconcile a worker's return produced under an earlier context with the current specifications before using it.

Use the [existing governing context](../harness/state.md#governing-context) when continuation needs persistence. When the saved task or result identity is unknown, use the existing store's lookup to locate it; the local helper provides [saved-work search](../harness/state.md#find-saved-work). Restore the original sources from the selected record. Retain its request and instruction references, adopted decisions and context revisions; register an authorized change through that mechanism. Preserve the instruction or evidence permitting the change, preceding versions and completed outputs. A summary, a new worker or an updated progress report supplies no amendment authority. Reuse unchanged completed operations and resume the next unresolved dependency.

## Handoff

Transmit the objective, fixed constraints, source version, completed results and remaining authorized work. Point to the canonical specification, applicable rule bodies and outputs; include the exact input or permission required for the next dependent action. Preserve the parent proposition, adopted decision and its permitted switching condition so the receiving worker can integrate the next result without reconstructing settled work.

## Requested usage accounting

Collect usage, cost or worker statistics when the user asks for them. Use the existing task outputs, native launch/return records and `.agents/harness/state.py usage` importer for the fields their actual returns expose. Retain role, launch and return identity, requested model and effort, observed model and effort, actual start and completion time, and exposed token or usage fields with their producing source. An absent observation remains absent; configured models, guessed rates and worker self-reports do not supply runtime telemetry. Deduplicate cumulative usage through the existing importer and retain its epoch and sequence.

For a requested solo/team comparison, fix the same task inputs, specification, artifacts and correctness conditions before both runs. Sol performs the solo condition and owns the team's decomposition, integration and final judgment. Measure elapsed time through the completed integrated output, including actual briefing and integration, and identify preparation or warm-worker reuse in the existing evaluation record. Compare correctness and recorded resources together. Derive savings only from comparable observed quantities; token counts and estimated credits do not establish subscription allowance percentages.

## Review findings and independence

Use independent review when expressly selected or required by the platform. Preserve its evidence, actual identities and role separation under CONTROL. The task owner performs the integrated completion review required by CORE in every workflow.

## Paragraph assignments

Assign writing by coherent arguments or sections with distinct sources. The editorial owner preserves terms, source correspondence and logical dependencies across the assembled prose, then completes the integrated review. Use the same econ-writing workflow in delegated and single-author work.

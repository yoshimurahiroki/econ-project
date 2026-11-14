# Project procedure

Project work treats the project as an economic decision: who decides, what each allocation of work and resources produces, and which allocation the objective selects. Every mode runs the [economist's procedure](../../../runtime/ECONOMIST.md) first; this file adds the steps for each mode. Fill each block in the worksheet.

## P1. Mode

| Request | Mode | Steps |
| --- | --- | --- |
| Clarify requirements, scope or approach | `clarify` | P2, P3 |
| Write or improve an executable prompt | `prompt` | P2, P4 |
| Complete an assigned contribution in a case | `contribute` | P2, P5 |
| Run a project: work, people, resources, dates, handover | `manage` | P2, P6, P7, P8 |

## P2. Project decision

```
Decision maker and decision:      who chooses what, by when
Objective:                        the outcome the project serves, in its units
Feasible actions:                 the options, with their resource use and dates
Information and incentives:       who knows what; what each participant is rewarded for
Fixed requirements and authority: what cannot change, and who may change what
Completion condition:             the observable state that ends the work
```

When the division of work matters, model it before assigning: effort and measurement (CONTRACT-01, CONTRACT-07), decision rights (CONTRACT-08), team production and coordination (CONTRACT-05, CONTRACT-09); capacity and queues (MATH-04, MATH-07, MATH-09); waiting and information (INFO-02, DYN-07). Search the knowledge library with the project's words before choosing.

## P3. Clarify

1. List the consequential alternatives under the same fixed requirements and recommend one with its reason and switching condition.
2. Ask the user only for information or judgment that changes the result; one focused question at a time, continuing independent work meanwhile. A clear request needs no interview.
3. For a complex change, write in this order: observable requirements, the adopted design, the implementation steps ordered by dependency, and the interface, ownership and failure cases that matter.

## P4. Prompt

The prompt carries: objective, actual targets and inputs (bodies or accessible paths), adopted criteria, constraints, authority, the necessary order, outputs and completion conditions. Keep the quantities, prohibitions and decisions of a supplied draft. Then read the prompt as its executor would: can the executor find each input, take the first action and recognize completion? Repair what fails. Deliver the prompt first.

## P5. Contribute

```
Assignment and parent premise:   the proposition or artifact it completes
Inputs and versions:
Acceptance condition:
Result and its implication for the parent:
```

Complete the calculation, source comparison or artifact through the specialist skill and return the result with its version; when new evidence changes it, update the consumers.

## P6. Manage: work and allocation

1. Connect the final judgment to the propositions it needs, each proposition to the evidence and work that settles it, and each piece of work to its owner, capacity and consumers.
2. Rank work by its effect on the final judgment and the feasible action, relative to its time and cost; work that changes no decision is dropped.
3. Compare complete feasible allocations under the objective, decision rights and deadlines, counting displaced use of shared capacity and delay; choose with the [action selection](../../../runtime/ECONOMIST.md#selecting-an-action) rule.
4. Persistent projects use the state tools: `project-bind` binds the definitions, argument and sources; `project-view --view forecast` computes feasibility, waits, finish dates and costs under an order (repeat with `--priority TASK` and `--capacity JSON` to compare proposals); the adopted comparison is saved as `project_judgment` ([state](../../../harness/state.md#project-work)).

## P7. Manage: changes, dates and recovery

1. Keep target, approved, forecast and actual dates apart.
2. On new evidence or a delay, name the changed premise and its consumers; `project-impact` separates schedule effects from invalidated results and returns the affected and reusable tasks.
3. Compare recovery actions, adopt one under the authority that holds, bind the amendment to its previous version, and rebuild only the affected results.

## P8. Manage: discussion, contact, artifacts and handover

- **Discussion and interviews:** hold a discussion only to settle a real premise or decision; ask for concrete choices, dates and contrasting cases tied to the model; record decisions with actor, date and changed condition, and keep proposals as proposals.
- **Contact drafts:** return the complete message with recipient, purpose, timing, the information requested and the supporting material. Messages stay drafts until the user instructs sending through the actual service.
- **Artifacts:** reports, proposals, figures and slides come from econ-writing, bound to their saved results.
- **Outcomes and handover:** define adoption and outcome measures with population, period, units and denominator; deliver usable artifacts and instructions to the receiving owner, with the remaining obligations and who measures the outcome.

All text follows [WRITING](../../../runtime/WRITING.md).

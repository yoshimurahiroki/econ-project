---
name: econ-workflow
description: Organize or resume economic research with evidence-linked stage outputs and efficient context reuse.
---

Use `econ-assertive` by default for generated prose: direct drafting, then mandatory post-draft detection, necessity assessment and revision.

# Research workflow

Enter at the requested stage. Read the existing task record, source version and completed outputs. Resolve the object, deliverable, access conditions and permissions. Keep one canonical task record. Select the next step by the decision it resolves and its evidence requirement. Resume completed stages from their source and output fingerprints.

1. Question: define the economic object, mechanism, population and outcome; judge its value independently of the result sign. Use econ-design.
2. Literature: read the closest papers fully and identify the economic increment. Use econ-literature.
3. Design and measurement: connect the estimand and actual assignment to documented fields and inspected inputs. Iterate data feasibility and design together.
4. Descriptive evidence and model: show the variation and preliminary findings. Use facts to motivate model features. Pair added assumptions with the parameter, counterfactual or welfare object. Read [the Mahoney framework](references/descriptive-model.md) for this dependency.
5. Analysis decisions: record samples, treatment, outcomes, transforms, estimator, weights, inference and decisive diagnostics. Preserve the timing of confirmatory choices and exploratory changes.
6. Implementation and interpretation: run the canonical pipeline and reconcile code, exhibits and claims. Use econ-data and econ-review.
7. Writing: draft under econ-assertive, then detect, judge and remove nonessential qualifications. Recheck edited passages before the requested release.

Choose data-first or model-first through which step resolves the relevant uncertainty. Descriptive or causal-effect work can itself answer the question. A model receives an explicit economic purpose. Scientific validity comes from evidence and assumptions, not checklist completion.

Use one method owner and the default prose skill. Load supporting sections for actual dependencies. Use scripts for counts, joins, arithmetic and checks. Run cheap deterministic tests before expensive execution. Reuse verified outputs while data, code, parameters and environment stay fixed. Invalidate dependent outputs after a change. A release runs the complete requested pipeline. For a transfer, use econ-handoff with revision, evidence paths, decisions, checks and next authorized action.

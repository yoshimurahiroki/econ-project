# Economics operation index

Generated from registry/operations.json. Read runtime/CORE.md once; select the final operation below. Support continues the same task.

- econ-design / design: Choose a research question, model, identification strategy, study design or policy action.
- econ-data / execute: Acquire, transform, join, calculate, estimate or change research data and code.
- econ-literature / investigate: Find and select source information that resolves a research question or citation task.
- econ-writing / compose: Compose the requested prose from authorized materials.
- econ-writing / revise: Revise supplied prose within the authorized content-change scope.
- econ-writing / translate: Translate the requested passage into the target language.
- econ-writing / convert: Convert settled content into the requested medium and format.
- econ-writing / guidance: Answer questions about prose principles and examples.
- econ-writing / explain: Explain a specified source's economic claims, theory, methods or results.
- econ-writing / profile: Create or revise a reusable prose profile and functional fictional examples.
- econ-review / assess: Assess the specified claim or artifact and return findings and proposed repairs.
- econ-review / assess+repair: Assess the specified target and repair it within the requested change scope.

Compatibility names:

- econ-workflow: {"required_rules": ["core.all"], "resolve_owner_by": "requested_final_operation", "runtime_action": "boundary"}
- econ-assertive: {"operation_id": "econ-writing:guidance"}
- econ-edit: {"operation_id": "econ-writing:revise"}
- EDIT: {"default_input": "immediately_preceding_answer", "operation_id": "econ-writing:revise"}
- econ-handoff: {"requested_section": "Handoff", "required_rules": ["core.all", "team.handoff"], "resolve_owner_by": "existing_result_owner", "runtime_action": "handoff"}
- econ-paper: {"operation_id": "econ-writing:explain"}
- econ-style: {"operation_id": "econ-writing:profile"}

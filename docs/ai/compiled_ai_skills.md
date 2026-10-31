# Economics operation index

Generated from registry/operations.json. Read runtime/CORE.md once; select the final operation below. Support continues the same task.

- econ-design / design: Choose a research question, model, identification strategy, study design or policy action.
- econ-data / execute: Acquire, transform, join, calculate, estimate or change research data and code.
- econ-data / equity: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
- econ-literature / investigate: Find and select source information that resolves a research question or citation task.
- econ-writing / compose: Compose academic prose and research materials from the adopted sources.
- econ-writing / revise: Revise supplied prose, including natural Japanese, spoken explanations and requests such as 自然な日本語に, 何を言いたいの, 直訳っぽい, 口頭で説明して and わかりやすく短く.
- econ-writing / translate: Translate supplied prose into natural Japanese or English while preserving its claims and sources.
- econ-writing / convert: Convert adopted content into a paper, slides, research site or requested format.
- econ-writing / guidance: Explain a concrete writing decision and show the needed revision.
- econ-writing / explain: Explain a paper, theory, institution, method or result through its question, mechanism, evidence and answer.
- econ-writing / profile: Create or revise a reusable writing profile only when explicitly requested.
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
- explain-before-shorten: {"operation_id": "econ-writing:revise"}
- econ-equity: {"operation_id": "econ-data:equity"}

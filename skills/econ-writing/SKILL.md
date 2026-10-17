---
name: econ-writing
description: Compose, revise, translate, convert or explain economics content, give writing guidance, and create explicitly requested writing profiles.
---

# Write the requested economics artifact

Inherit the task boundary from [CORE](../../runtime/CORE.md) and the owner assignment from [operation registry](../../registry/operations.json). Support calls keep the parent's input, authority and completion conditions. Use [PROSE](../../runtime/PROSE.md) for information selection, connections, language and profile selection.

Input: requested text or research records, reader, purpose, language, medium, content-change scope, selected profile and supplied template; for explanation, the specified paper or passage version; for profile work, supplied examples and the existing profile. Choose the mode by the requested final operation. Explanation, translation and medium conversion retain one artifact owner.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `compose`: Compose the requested prose from authorized materials. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `revise`: Revise supplied prose within the authorized content-change scope. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `translate`: Translate while preserving propositions and paragraph functions. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `convert`: Convert settled content into the requested medium and format. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `guidance`: Answer questions about prose principles and examples. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `explain`: Explain a specified source's economic claims, theory, methods or results. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `profile`: Create or revise a reusable prose profile and functional fictional examples. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
<!-- END GENERATED MODES -->

## Compose

Build new prose from the authorized research records and exhibits. For a complete paper or paper-wide reconstruction, use [paper argument](references/paper-workflow.md#establish-the-argument-from-the-research) and [paper structure](references/paper-workflow.md#design-the-papers-argument). For an Abstract, Introduction or specialist section, read only [section composition](references/paper-workflow.md#compose-the-requested-section). A short passage, talk or memo uses PROSE directly.

Obtain an unresolved model implication, source passage or calculation only when it determines the requested claim. Keep available passages and exhibits whose inputs are unchanged. For a requested operational plan, resolve choices with [DECIDE](../../runtime/DECIDE.md) before describing the selected actions and completion conditions.

## Revise

Revise the specified text and scope; EDIT alone selects the preceding answer. Preserve substantive claims, populations, quantities, signs, citations, equations, measured uncertainty, conditions and inference meaning. Reorder and reconnect retained claims to answer the requested question. Correct facts or add source findings only when requested. Use section composition for a whole-paper revision and medium instructions for a talk or site. Compare the revision with the original under [meaning preservation](../../runtime/PROSE.md#preserve-meaning-across-languages), then return the revised text.

## Translate

Express the supplied claims and paragraph functions in the target language. Use [meaning preservation](../../runtime/PROSE.md#preserve-meaning-across-languages) to retain comparisons, logical relations, modality, quantities and uncertainty while choosing the target language's syntax and vocabulary. Select profile examples only for unresolved language choices. Return the translation in the requested scope and format.

## Convert

Map established content into the requested medium and make its display, references and format work. Carry forward the adopted research meaning and numerical results. Apply the medium and production instructions below; resolve only dependencies needed for that conversion.

## Guidance

Answer the requested question about prose principles or examples using the relevant PROSE section and profile function. Explain the writing choice and its effect on the reader's interpretation. If the user requests revised text, use revise mode and return that text.

## Explain

Explain the specified paper or passage in the requested form. Apply [meaning preservation](../../runtime/PROSE.md#preserve-meaning-across-languages) to the source argument and results.

### Read and select the argument

Read the specified version and sections needed for the requested explanation under [CORE's resource-selection rule](../../runtime/CORE.md). Identify the edition and passage locations used through requested citations or existing references. Update existing source records when the request includes that update or subsequent work uses those version and location details. The explanation is complete when it answers the requested questions. For a whole-paper explanation, select content around the paper's question and contribution, including after specialist-section work. For a named passage, read other sections when needed to explain its terms, reasoning or role in the argument.

### Develop the connected explanation

Use these questions to select and connect the paper's economic content:

1. **What is the research question?** Identify the behavior, outcome or relationship the author seeks to explain.

2. **Why does the question matter?** Explain the incentives, mechanism or theoretical problem at stake and how the setting helps answer it.

3. **How does the paper answer it?** Explain the central mechanism and comparison or model. Connect empirical outcomes, variation, measurement and method to the result they identify. In theory, connect the assumptions and decisive reasoning to the proposition. Explain a distinctive solution to an identification or measurement problem when it determines the answer.

4. **What are the results?** State the findings, magnitudes and economic meaning that answer the question. Include a policy implication when it forms part of the central result. Compress secondary estimates that establish the same claim.

5. **What does the paper add?** Compare the finding with the closest research and explain how its distinctive reasoning, measurement or comparison changes understanding of the question. Use cited papers for this comparison and econ-literature when a needed source remains unresolved.

### Complete the requested explanation

Explain what the paper's findings and reasoning establish for its question. Use econ-design for a technical dependency and econ-literature for a missing source, then integrate their returns. Deliver the requested explanation in its citation format. An explicit validity, defect or correction assessment is owned by [econ-review](../econ-review/SKILL.md). Continue a requested translation or medium conversion in the corresponding writing mode under the same owner and inherited meaning.

## Profile

Use only for an explicit profile-creation or update request. Input: reader, purpose, languages, products, supplied complete examples and existing profile.

### Select source passages

Define the profile's reader, purpose, languages and products. Read the supplied examples and existing profile; obtain additional material when the request requires it. Select connected passages that demonstrate how an economic question, comparison, finding and contribution determine the writing. Include empirical or theoretical examples when they demonstrate a distinct choice needed for the target prose.

Use the requested published version. Record its edition and passage boundaries when needed for the requested comparison or continuation. Read relevant subsections, exhibits and footnotes; inspect page images when extraction obscures the text. Select examples by language, passage function and medium. Derive Japanese terms and sentence connections from their use in connected passages.

### Derive principles and worked examples

Identify what information each passage selects, how its sentences connect that information and which technical details advance its argument. Turn each choice into a rule naming the passage condition and the writing action it calls for. Demonstrate those rules with complete original examples under the common prose rule.

Use an Abstract and Introduction from the same research content when their different depth illustrates the rule. Preserve defined populations, conditions, numbers and conclusions in the worked argument. Label fictional studies and invented quantities. Apply [the cross-language meaning checks](../../runtime/PROSE.md#preserve-meaning-across-languages) to counterparts. Preserve useful functioning examples; add one only when it teaches a distinct writing decision. Let examples demonstrate choices; do not turn their paragraph counts, vocabulary or order into required templates.

### Use a requested opening or comparison

For a requested opening, continue in compose mode with the study body, reader, language and intended function. If the task requests a comparison with an unseen reference, preserve the specified input boundary and complete draft before reading that reference. Save a brief, argument plan or source record when required for the requested comparison or continuation.

For explicit assessment, use econ-review to compare content selection, reasoning and expression against the same study content. Keep the fixed brief and separate inputs when the user requests an independent comparison. Return assessment findings to the profile work only when profile revision is requested.

### Save the profile

Save reusable runtime profiles as operational principles and complete original fictional examples at the requested destination. Construct the examples' settings, quantities and prose to demonstrate the intended writing choices; label the examples as fictional. Keep third-party prose, excerpts, production history and comparison history out of runtime instructions and profiles. Store input identities, versions, reading scope, source locations or comparison records separately only when needed for the requested research, comparison or continuation. Keep factual claims and their supporting citations in the requested research output and its source record. For an authorized profile test, hold source facts fixed, produce representative target prose and report the changes observed in that prose. Claims about improved writing require a comparison that can attribute the improvement to the profile change.

A repository-save request without a path updates docs/ai/custom-style.md after reading it. Use [the profile-selection rule](../../runtime/PROSE.md#select-the-profile) for adoption or switching.

### Organize selective reading

Give the profile a stable ID and an entry page naming its reader, language and medium. Organize original examples by the writing decision they teach: conclusion and comparison, institution and mechanism, quantities and relationship type, revision or translation, and Abstract or Introduction function. Provide language-specific section links. Add an example only when the existing examples do not teach the required decision.

Preserve useful extended arguments as optional language-specific examples. Read an extended Introduction when cumulative reasoning across paragraphs needs a model; use a short functional example for a local choice. Keep adopted profile principles available without requiring all example bodies. Saving a profile does not adopt it as the project default; change writing_profile only on an explicit adoption or switching request.

## Compose for the medium and language

Use the supplied template, bibliography and notation. For figure selection, captions or explanation, read [descriptive exhibits](references/paper-workflow.md#choose-and-explain-descriptive-exhibits); use econ-data for required calculations and saved-result management. Size text and exhibits for the requested viewing format. Read the following medium-specific section only when that medium or production operation is requested.

## Compose a talk

For a talk, select exhibits and spoken explanations in the order listeners need within its duration. Preserve the supplied theme, notation and language support. Use the existing presentation or Beamer entry point; follow the render section only when a compiled artifact is requested.

## Compose a research site

For a research site, establish canonical URLs and generated-content owners before changing pages or links. Preserve navigation, language counterparts and deep links. Generate numerical exhibits from saved analysis objects. Preserve the existing site theme, notation and language support.

## Render the requested artifact

For a requested compiled or rendered artifact, read its Make target and template and use the existing Markdown, QMD, LaTeX, Beamer or site entry point. Preserve canonical research files, theme and language support. Build through the authorized entry point and inspect the result. Repair rendering defects and deliver the requested output. A completed section or build returns to remaining requested work. Follow [EXECUTION](../../runtime/EXECUTION.md) for a build and [state](../../harness/state.md) only when version-linked persistent outputs are needed.

## Output

The requested finished text, explanation, guidance, profile or artifact, with the adopted research meaning, quantities and output format preserved.

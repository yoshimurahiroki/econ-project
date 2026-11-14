# Context layer

Specific knowledge overrides general knowledge; general knowledge fills the gaps. Before step 1 of the [economist's procedure](../ECONOMIST.md), read:

1. **Country context** in this folder for the economy the question is about (`japan.md`). It names the data sources, institutions and conventions that replace the agent's default, US-centred choices.
2. **Project context** in `work/context.md` of the user's project, when it exists: the population, data holdings, earlier decisions, conventions and constraints of this project.

Record the files read in worksheet section 1 (`Context read:`) and tag decisions taken from them `[context: file]`. When the context and the agent's general knowledge disagree, the context wins and the worksheet names the disagreement.

## Project context file

`work/context.md` holds what stays true across tasks in one project:

```
Population and unit:        <who and what is observed>
Data holdings:              <datasets, their location, vintage and access conditions>
Adopted definitions:        <variables and samples settled earlier, with the worksheet that settled them>
Institutional facts:        <rules, dates and actors that shape the identification>
Conventions:                <units, deflators, fiscal or calendar years, rounding, language of output>
Constraints:                <confidentiality, computing, deadlines>
```

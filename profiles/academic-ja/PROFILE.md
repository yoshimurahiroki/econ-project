# Japanese economics writing profiles

Profile family: academic-ja. Language: Japanese.

## Principles

Apply [PROSE Common output](../../runtime/PROSE.md#common-output) to every element selected from this profile.

The first three profiles contain the samples adopted from the user’s uploaded manuscript. The seminar-slide profile presents the first sample's study as a talk, in the register of Japanese graduate lecture slides: noun-phrase headings, plain-form bullets without a terminal stop, 「、」 punctuation and 「項目: 内容」 definitions. Read the complete selected sample and ground adopted Japanese expressions and visual elements in corresponding Japanese originals. The body files retain the uploaded Japanese prose. Equations, mathematical variables and Greek letters use LaTeX notation. Keep selection instructions in this index.

## Select a profile

| Writing task | Profile ID | Complete sample |
|---|---|---|
| Explain an institution, identification, estimates and policy calculations | `academic-ja-childcare-employment` | [夕刻預かり事業と母親の就業](childcare-employment.md) |
| Explain a choice model, identification, estimation and counterfactual demand | `academic-ja-attention-plan-choice` | [料金プラン選択における注意の推定](attention-plan-choice.md) |
| Review empirical studies through their settings, methods and estimates | `academic-ja-equipment-subsidy` | [設備更新補助の投資効果](equipment-subsidy.md) |
| Present a study as seminar or research-meeting slides | `academic-ja-slides-seminar` | [夕刻預かり事業と母親の就業：研究報告スライド](slides-seminar.md) |

Each row is a separate registered writing profile and example. Use `academic-ja.` followed by the filename stem as the example ID. Select the complete sample closest to the current writing task.

```sh
python scripts/route_registry.py read academic-ja-attention-plan-choice.all
python scripts/route_registry.py read econ-writing:compose --user-profile academic-ja-equipment-subsidy --stage compose
```

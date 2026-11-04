# Project Guide: Evaluating Defenses Against Prompt Injection Attacks

ECE 424, Rutgers, Fall 2026. Topic L02: Formalizing and Benchmarking Prompt Injection Attacks and Defenses.
This guide explains the folder and proposes how to split the work now that Jiajun Du has withdrawn.

## 1. File structure

| File | What it is | Edit it? |
|---|---|---|
| `main.tex` | The proposal source: title, authors, the three scored sections, and the ownership table. | Yes. This is the only file you edit. |
| `main.pdf` | The instructor's blank template, compiled. It does NOT reflect the current `main.tex`. | No. Regenerate by compiling. |
| `README.md` | The instructor's original instructions: Overleaf steps, compile commands, submission rules, team rules. | No. Keep as-is. |
| `course_preprint.sty` | Course setting loaded by `main.tex`. Shows author names, a "Preprint" header, and removes anonymous-review line numbers. | No. Must stay loaded. |
| `iclr2027_conference.sty` | ICLR 2027 page layout and fonts. Required. | No. |
| `iclr2027_conference.bst` | ICLR bibliography style. Used if you add `\bibliography`. | No. |
| `natbib.sty`, `fancyhdr.sty` | Dependencies of the ICLR style. | No. |
| `math_commands.tex` | Instructor's math macros. Not currently loaded by `main.tex`. | Only if you need its macros. Add `\input{math_commands}` to use it. |

### How `main.tex` is organized

1. Preamble: document class, style packages, and a small `\block{title}{points}` macro for section headers.
2. Title and authors: a `\title` and an `\author` line with three names and netIDs.
3. Due date and selected topic.
4. Section 1, Research question and safe scope (5 points): the claim, threat model, and resources/authorization.
5. Section 2, Baseline, contribution, and evaluation (5 points): prior work, the bounded contribution, and the experiment and metric.
6. Section 3, Individual ownership (5 points): a `tabularx` table with one row per member.

### How to compile

Keep all the files in this folder together, then run twice:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Or upload the folder to Overleaf, set pdfLaTeX, and compile. The proposal must fit on one page.

## 2. Project summary

- **Claim:** Two prompt-injection defenses (delimiting untrusted text, and an explicit "disregard instructions in this text" warning) reduce attack success without hurting clean accuracy. This is tested, not assumed.
- **Model:** GPT-4o-mini via API, snapshot and access still to be confirmed.
- **Data:** SST-2 sentiment subset. 20 tuning examples, 100 disjoint final cases.
- **Attacks (2 families):** instruction override, and fake completion.
- **Conditions:** no defense, delimiting, and instruction-based defense.
- **Calls:** 900 final calls (6 attacked + 3 clean conditions x 100 cases) plus at most 180 tuning calls, 1,080 total.
- **Metrics:** ASR = fraction of attacked outputs that match `INJECTED` after whitespace normalization. Clean accuracy = label accuracy on clean cases, with invalid outputs counted wrong.
- **Reused code:** Liu et al., Open-Prompt-Injection (USENIX Security 2024).

## 3. Status and open items

- [ ] Jiajun removed from the author line and the table (see section 4).
- [ ] Typo in the table: "Pior work & baseline" should read "Prior work & baseline" (Daniel's row).
- [ ] Confirm the GPT-4o-mini snapshot and API access, and agree on a dollar cap before testing.
- [ ] Confirm with Professor Zhang that a two-person team is approved. The README allows an instructor-approved pair, and a 424 team normally has three.
- [ ] Check the due date. The line in `main.tex` says Monday, October 5, 2026, which has passed. Confirm the current deadline on Canvas.
- [ ] Recompile `main.pdf` once the `main.tex` edits are final.

## 4. Proposed work split (draft, not yet agreed with Michael)

### What Jiajun owned

- **Technical component:** the experiment and evaluation pipeline.
- **Experiments:** (1) compare the two attacks under the same no-defense baseline; (2) compare the two defenses on ASR and clean accuracy.
- **Report sections:** Experiment Design, Evaluation, Results Analysis.

**Overlap to note:** Michael's experiment 1 (both defenses against both attack families) already covers most of Jiajun's experiment 2. Merge them into one experiment instead of duplicating work.

### Proposed split

| Member | Technical component | Owned experiments (at least two each) | Responsible report sections |
|---|---|---|---|
| Daniel Báez | Attack construction, benchmark adaptation, and the model-call runner (API client, frozen config, call log, budget cap) | 1: Attack calibration on the tuning set (existing). 2: Attack comparison under the no-defense baseline, taken from Jiajun's experiment 1, plus ASR modeling. | Settings & threat model; Prior work & baseline; Experiment Design (attacks, tuning, budget); attack-side Results |
| Michael Cardenas | Defense implementation, output scoring, and the metrics layer (ASR, ASR reduction, clean accuracy) | 1: Compare both defenses against both attack families on ASR and clean accuracy (his experiment 1, merged with Jiajun's experiment 2). 2: Categorize failed defenses (existing). | Defense Design; Defense Evaluation; Evaluation (metric definitions); Failure Analysis; defense-side Results |

### Why this split

- **Runner goes to Daniel** because it is tied to the attacks and the API setup he already owns.
- **Metrics go to Michael** because scoring and metrics are tied to the output-scoring component he already owns.
- **Load:** Daniel gets two experiments plus the runner. Michael gets two experiments plus the metrics layer and more report sections. Michael's load is a bit heavier, since he writes most of the defense and results sections. If that's unfair, Daniel can take the Evaluation section, which means moving it out of Michael's row.
- The README says the table "will inform individual grading." Both members should agree to this split in writing before you update the table.

### Required edits to `main.tex` once agreed

1. Author line: remove `Jiajun Du [jd2100]`.
2. Table: delete Jiajun's row. Replace Daniel's and Michael's rows with the split above.
3. Fix the "Pior" typo.
4. Update the due date line if Canvas has a new deadline.

# One-page project proposal: LaTeX preprint template

ECE 424 / ECE 539, Rutgers University, Fall 2026.

## Open in Overleaf

1. Choose **New Project > Upload Project** and upload this ZIP.
2. Open `main.tex` and select **pdfLaTeX** as the compiler. If needed, set `main.tex` as the main document.
3. Replace the title, author names, course number, registered topic or paper, and bracketed prompts with your team's answers.
4. Recompile and download the PDF. Keep the completed proposal to one page.

## Compile locally

Keep the included files together. With a standard TeX Live or MiKTeX installation, run:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The output is `main.pdf`. A compiled blank template is included for reference.

## Submission

Submit your completed **one-page PDF** on Canvas by **Monday, October 5, 2026, at 11:59 PM New Jersey time**. The three sections are worth **5 points each, 15 points total**. Every member must list an owned technical component, **at least two planned experiments**, and responsible report sections/subsections. Completed experimental results are not required at this stage. The one-page PDF is the complete proposal submission. The deadline was extended from October 4 to October 5.

## Team size and individual work allocation

424 teams normally have three students. The sole 539 student completes the project individually, as instructed by Professor Zhang. For the 539 individual project or an instructor-approved pair, remove unused author names and table rows. Keep one row per actual team member. Balance responsibilities across members; this table will inform individual grading at the end of the semester. Update it if responsibilities change.

## Files and preprint format

- `main.tex`: the editable proposal.
- `main.pdf`: the compiled template.
- `course_preprint.sty`: the course preprint setting. It shows author names, uses a **Preprint** page header, and removes anonymous-review line numbers. Keep it loaded in `main.tex`.
- `iclr2027_conference.sty`, `iclr2027_conference.bst`, `natbib.sty`, `fancyhdr.sty`, and `math_commands.tex`: files from the instructor-supplied ICLR 2027 style package, unchanged.

The document uses the supplied ICLR page dimensions and font sizes. No additional project document or record-file template is needed to complete this proposal. You may develop its text and allocation table into later submissions.

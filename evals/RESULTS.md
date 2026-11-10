# Initial behavior evaluation — 2026-11-10

Ten offline runs used five existing synthetic cases: one run with the packaged skill and one without it
for each case. Each agent started with a fresh context and the same inherited model configuration. The
baseline could inspect the same input files but had no skill copy. Both arms could write implementation
artifacts. Network access, game execution, installations and reading other projects were forbidden.

| Case | Without skill | With skill |
| --- | ---: | ---: |
| Invented Pawn native | 3/4 | 4/4 |
| Entrance versus safe arrival | 4/4 | 4/4 |
| Scan miss versus original-script absence | 3/3 | 3/3 |
| Unrecovered engine function | 3/3 | 3/3 |
| Wrong-build hook address | 4/4 | 4/4 |
| Total rubric criteria | **17/18** | **18/18** |

The single baseline miss is narrow: it refused the unsupported native and declined to invent a formula,
but did not explicitly label the underlying single-player fat/speed premise unverified. The skill answer
did. Both arms avoided the major unsupported implementations, including an unchecked teleport or hook.

Skill answers consistently supplied file hashes, build qualification and explicit limits. They were also
longer. This is evidence that the prescribed reporting structure was followed, not evidence of lower cost,
higher speed, or a general improvement in coding capability. No token or latency comparison was measured.

## Method and reproducibility limits

- The existing `graders/*.md` criteria were reviewed manually against the saved answers and action records.
  Grading was not blinded. [results.json](results.json) records each criterion's pass/fail, output hashes,
  answer word counts and the borderline baseline decision so it can be challenged.
- Each case/arm ran once. There were no statistical significance tests, repeated seeds or cross-model
  comparisons. These are five research-error cases, not comprehensive implementation-quality coverage.
- Runs used separate working directories and explicit scope restrictions, not separate virtual machines.
  Action records were written by the agents; they are not independent execution traces.
- The engine snippet, executable, include and script bytes were generated fixtures. The tests did not
  validate GTA behavior, geometry, a live server or compiled Pawn/C++ output. Both entrance implementations
  were explicitly unfinished scaffolds pending real arrival evidence.
- Full answers, action records and generated artifacts were retained privately with the release preparation
  evidence. No proprietary game files were used or published. The result hashes identify that record.
- Evaluation used the renamed candidate before its private known-build record was removed. Both synthetic
  executables were unknown under that table and remain unknown with the shipped empty table. The research
  workflow and tool behavior exercised by these cases are unchanged; publication documentation was added later.

To repeat, create a fresh empty directory per case/arm, execute that case's `place-files.sh` there, and
give a fresh agent the body of `prompt.md` without the grader or expected outcome. Copy only the skill folder
into the skill arm. Keep model configuration and permitted tools equal, save answers and artifacts, then
apply the same rubric. The shell setup scripts currently assume a Linux-like evaluation runner.

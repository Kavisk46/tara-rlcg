"""Statistical-analysis infrastructure for the TARA evaluation harness (M11).

Implements exactly the procedures fixed in advance by `EXPERIMENT_PLAN.md`
§6: Wilcoxon signed-rank (primary paired comparison), Holm-Bonferroni
(multiple-comparisons correction), matched-pairs rank-biserial
correlation (effect size), BCa bootstrap (confidence intervals),
McNemar's test (paired binary outcomes), and Spearman rank correlation
(H1/H5). Every function is tested against a toy dataset with a
known-by-hand significance outcome, per `ROADMAP.md` M10's own testing
requirement for this kind of code.

**This module is infrastructure, not an executed analysis.** Per this
milestone's own explicit instruction: "Add statistical analysis
infrastructure but do not run final hypothesis tests until the dataset
and experimental protocol are frozen." No function here is called
anywhere in this codebase against real experimental results -- TIQS has
no annotated data yet (M9), and no real experiment has been run (M10's
and M11's own instructions both explicitly prohibit that). These
functions exist so that, once TIQS and the experimental protocol are
frozen, running H1-H5 is a matter of calling already-tested code, not
writing new statistical code under time pressure.
"""
from __future__ import annotations

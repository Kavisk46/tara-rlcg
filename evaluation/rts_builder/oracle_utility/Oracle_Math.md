# Oracle_Math.md — RTS Builder Oracle Utility (Milestone 6)

The complete mathematical formulation this subsystem implements. Every
symbol here corresponds to a named field on `RelevanceJudgment`,
`QualityMetrics`, or `StrategyOracleRow` (`models.py`), a pure function
in `metrics.py`, or a step in `computer.OracleUtilityComputer.compute`.
Aligned with, and where noted extending, `docs/DATASET_BUILDER_SPEC.md`
§8-9's already-established formulation from this project's earlier
research-planning phase.

## Notation

For a fixed query $Q$ against repository $R$: let $s \in \{\text{lexical},
\text{dense}, \text{graph}, \text{hybrid}\}$ index the four Retrieval
Executor strategies. Let $\text{retrieved}_s = [f_1, f_2, \ldots]$ be
strategy $s$'s ranked, ordered list of retrieved file paths
(`StrategyResult.retrieved_files`, already sorted by descending score).
Let $\text{rel}: \text{file path} \to \mathbb{R}_{\geq 0}$ be the
ground-truth relevance grade function from `RelevanceJudgment.relevance_grades`
(a file absent from the mapping has $\text{rel}(f) = 0$), and let
$\text{Relevant} = \{f : \text{rel}(f) > 0\}$.

## 1. Retrieval Quality Metrics

### Recall@k

$$
\text{Recall@k}(s) = \begin{cases} \dfrac{|\{f_1,\ldots,f_k\} \cap \text{Relevant}|}{|\text{Relevant}|} & \text{if } |\text{Relevant}| > 0 \\ 0 & \text{if } |\text{Relevant}| = 0 \end{cases}
$$

$k$ = `OracleUtilitySettings.quality_metrics_k` (default 10), shared
with NDCG@k. Implementation: `metrics.recall_at_k`.

### MRR (per-query Reciprocal Rank)

$$
\text{MRR}(s) = \begin{cases} \dfrac{1}{\min\{\, i : f_i \in \text{Relevant} \,\}} & \text{if such an } i \text{ exists} \\ 0 & \text{otherwise} \end{cases}
$$

Named `mrr` on `QualityMetrics` per the requirement's own naming, but
this is one query's Reciprocal Rank, not a Mean — the *Mean* in "Mean
Reciprocal Rank" is a later, out-of-scope aggregation across many
queries' Oracle Utility results (averaging this field's value across
rows). Implementation: `metrics.reciprocal_rank`.

### NDCG@k

Using the standard exponential-gain formulation:

$$
\text{gain}(r) = 2^r - 1 \qquad \text{DCG@k}(s) = \sum_{i=1}^{k} \frac{\text{gain}(\text{rel}(f_i))}{\log_2(i+1)}
$$

$$
\text{IDCG@k} = \sum_{i=1}^{k} \frac{\text{gain}(r^{*}_i)}{\log_2(i+1)}, \quad r^{*}_1 \geq r^{*}_2 \geq \cdots \text{ the top-}k\text{ grades in } \text{rel}(\cdot)\text{'s range, sorted descending}
$$

$$
\text{NDCG@k}(s) = \begin{cases} \dfrac{\text{DCG@k}(s)}{\text{IDCG@k}} & \text{if } \text{IDCG@k} > 0 \\ 0 & \text{if } \text{IDCG@k} = 0 \end{cases}
$$

$\text{IDCG@k}$ is identical for every strategy $s$ on a given query
(it depends only on $\text{rel}(\cdot)$, not on any strategy's
retrieval), computed once per query in principle; this implementation
recomputes it per strategy for simplicity (see `Architecture.md`'s
Design Decisions) since it is cheap relative to retrieval itself.
Implementation: `metrics.ndcg_at_k`.

### Context Precision

$$
\text{ContextPrecision}(s) = \begin{cases} \dfrac{|\text{retrieved}_s \cap \text{Relevant}|}{|\text{retrieved}_s|} & \text{if } |\text{retrieved}_s| > 0 \\ 0 & \text{if } |\text{retrieved}_s| = 0 \end{cases}
$$

Deliberately **not** truncated to $k$ — computed over the *entire*
`retrieved_s` set, unlike Recall@k/NDCG@k. This metric answers "of
what would actually be handed to an LLM as context, how much of it is
useful," which depends on everything actually retrieved (bounded by
each strategy's own `top_k` from Retrieval Executor, not by
`quality_metrics_k`), not an independent ranking-evaluation cutoff.
Implementation: `metrics.context_precision`.

### Composite Quality Score

$$
\text{Quality}(Q, R, s) = w_{\text{recall}} \cdot \text{Recall@k}(s) + w_{\text{mrr}} \cdot \text{MRR}(s) + w_{\text{ndcg}} \cdot \text{NDCG@k}(s) + w_{\text{precision}} \cdot \text{ContextPrecision}(s)
$$

$$
w_{\text{recall}} + w_{\text{mrr}} + w_{\text{ndcg}} + w_{\text{precision}} = 1, \qquad w_{\text{recall}} = w_{\text{mrr}} = w_{\text{ndcg}} = w_{\text{precision}} = \tfrac{1}{4} \text{ (default)}
$$

Since every term is already in $[0, 1]$ and the weights form a convex
combination, $\text{Quality}(Q,R,s) \in [0, 1]$ by construction — the
same "already bounded to $[0,1]$ by construction" property
`docs/DATASET_BUILDER_SPEC.md` §8 states of its own (single-metric)
$\text{Quality}$ term. Settings:
`quality_recall_weight`/`quality_mrr_weight`/`quality_ndcg_weight`/`quality_context_precision_weight`,
validated to sum to $1.0$. Implementation: `computer.OracleUtilityComputer._compute_quality`.

## 2. Latency Normalization

$$
\text{Latency}_{\text{norm}}(Q, R, s) = \text{normalize\_scores}\big(\{\, s' \mapsto \text{latency\_ms}(s') \;:\; s' \in \{\text{lexical},\text{dense},\text{graph},\text{hybrid}\} \,\}\big)(s)
$$

Using `tara.retrieval.utils.normalize_scores` (min-max to $[0,1]$),
**reused unmodified**, applied to the 4-element latency vector for this
query only — the same function and the same "normalize within this
query's candidate group, not globally" design
`docs/DATASET_BUILDER_SPEC.md` §8 specifies (there, over a 7-element
vector; here, over Retrieval Executor's actual 4). `latency_ms` is each
`StrategyResult.retrieval_latency_ms`, measured under the frozen
latency protocol (`evaluation.rts_builder.retrieval_executor.latency_protocol`)
— embedding generation, vector search, graph traversal, and score
computation are counted; index construction, repository loading, and
model download are not (see that module for the full protocol).

If all four strategies have identical latency, `normalize_scores`
maps every one of them to $1.0$ (its own documented all-tied
convention, not a special case introduced here) — every strategy is
then penalized identically, so this cannot corrupt the *relative*
ranking among strategies, only shift every `utility_score` down by the
same constant `beta`. See `REVIEW_RESPONSE.md`.

## 3. Utility Computation

$$
\text{Utility}(Q, R, s) = \alpha \cdot \text{Quality}(Q, R, s) - \beta \cdot \text{Latency}_{\text{norm}}(Q, R, s)
$$

$$
\alpha > 0, \qquad \beta \geq 0, \qquad \alpha = 1.0,\ \beta = 0.1 \text{ (default)}
$$

**Relationship to `docs/DATASET_BUILDER_SPEC.md` §8's original formula**
$\text{Utility} = \text{Quality} - \lambda \cdot \text{Latency}_{\text{norm}}$:
this is a deliberate generalization, adding an independent weight
$\alpha$ on the Quality term (the original formula is the special case
$\alpha = 1$). The default $\beta = 0.1$ is chosen to exactly match
that document's proposed $\lambda = 0.1$ default, so `alpha=1.0,
beta=0.1` (this subsystem's actual default) reproduces the original
formula's output exactly. Neither $\alpha$ nor $\beta$ is a validated
constant — `docs/DATASET_BUILDER_SPEC.md` §14's requirement for a
$\lambda$-sensitivity sweep before any single value is frozen for a
released dataset applies equally to $\beta$ here. Unlike the Quality
sub-weights (a convex combination, validated to sum to 1), $\alpha$ and
$\beta$ are **not** required to sum to anything — this is a trade-off
formula, not a blend. Settings: `utility_quality_weight` ($\alpha$),
`utility_latency_weight` ($\beta$). Implementation:
`computer.OracleUtilityComputer.compute`.

Note $\text{Utility}(Q,R,s)$ is **not** bounded to $[0,1]$: with
$\alpha=1$, its range is $[-\beta, 1]$; more generally $[-\beta\alpha^{-1}\alpha, \alpha]$
i.e. $[-\beta \cdot 1, \alpha \cdot 1] = [-\beta, \alpha]$, since
$\text{Quality} \in [0,1]$ and $\text{Latency}_{\text{norm}} \in [0,1]$.

## 4. Strategy Ranking

### Rank

$$
\text{rank}(s) = 1 + \big|\{\, s' \neq s : (\text{Utility}(s') , \text{latency\_ms}(s') , \text{name}(s')) \prec (\text{Utility}(s) , \text{latency\_ms}(s), \text{name}(s)) \,\}\big|
$$

i.e. strategies are totally ordered by the tuple $(-\text{Utility}(s),\ \text{latency\_ms}(s),\ \text{name}(s))$
ascending — first by descending Utility, ties broken by ascending raw
latency (**the cheaper strategy ranks higher** — same principle as
`docs/DATASET_BUILDER_SPEC.md` §9, adapted; see `Architecture.md`'s
Design Decisions for why raw *measured* latency is used here instead
of that document's static `RETRIEVER_EXECUTION_PRIORITY` table), and
any remaining exact duplicate broken by strategy name (alphabetical),
guaranteeing $\text{rank}$ is always a strict bijection onto $\{1,2,3,4\}$
regardless of how many ties occur. `is\_best\_strategy}(s) = [\text{rank}(s) = 1]$.

### Tie Detection (informational, does not affect `rank`)

$$
\text{tied\_with}(s) = \{\, s' \neq s : |\text{Utility}(s') - \text{Utility}(s)| < \varepsilon \,\}, \qquad \varepsilon = \texttt{tie\_epsilon} = 0.02 \text{ (default, proposed, pilot-calibrated)}
$$

Matches `docs/DATASET_BUILDER_SPEC.md` §9's tie definition and proposed
default exactly.

### Confidence

$$
\text{label\_confidence} = \operatorname{clip}\!\left(\frac{\text{Utility}_{(1)} - \text{Utility}_{(2)}}{\max(\text{Utility}_{(1)},\, \epsilon_0)},\ 0.0,\ 1.0\right)
$$

where $\text{Utility}_{(1)}, \text{Utility}_{(2)}$ are the top-1 and
top-2 utility values after ranking, and $\epsilon_0 = \texttt{confidence\_epsilon}$
(default $10^{-6}$). Matches `docs/DATASET_BUILDER_SPEC.md` §9's
formula exactly, including its query-level (not per-strategy) scope: a
**single value per query**, computed once, and repeated identically on
all four of that query's `StrategyOracleRow`s — a ranker training on
the long-format table sees the same confidence value on every row for
a given query, exactly matching that document's stated design ("A
single scalar per query ... repeated across that query's seven rows").
Implementation: `computer.OracleUtilityComputer._rank_strategies`.

## 5. Output Schema

Every `StrategyOracleRow` (see `models.py`) carries every symbol
above for one `(Q, R, s)` triple: `quality.recall_at_k`, `quality.mrr`,
`quality.ndcg`, `quality.context_precision`, `quality.quality_score`,
`latency_ms`, `latency_normalized`, `utility_score`, `rank`,
`is_best_strategy`, `label_confidence`, `tied_with`. Four rows (one per
strategy) per query, matching `docs/DATASET_BUILDER_SPEC.md` §10's
long-format design: the **full per-strategy utility vector is
retained**, not collapsed to a single best-strategy label — the
explicit requirement `docs/methodology/RANKER_DESIGN.md` established
for Learning-to-Rank training data during this project's earlier
research-planning phase.

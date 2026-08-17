# Schema example — NOT real TIQS data

Everything in this directory is a **synthetic, illustrative fixture**
used to (a) demonstrate the TIQS file formats defined in
`evaluation/tiqs/models.py` and `../TIQS_SCHEMA.md`, and (b) serve as
test input for `evaluation/tiqs/validation.py`'s test suite.

**No query in this directory was authored by a real annotator, and no
label here reflects a real annotation decision.** Per DATASET_PLAN.md's
own status line, TIQS annotation under the protocol this schema
formalizes has not yet been performed. `repository_id`, `annotator_id`,
and `query_text` values here are deliberately, unmistakably fake
(`example-repo`, `example-annotator-a`, query text prefixed
`[SCHEMA EXAMPLE]`) so this content can never be mistaken for a real
dataset row if it is copied out of context.

Do not treat any content here as evidence of dataset progress, and do
not extend this directory with additional "example" queries as a
substitute for actually running the annotation protocol in
`DATASET_PLAN.md` §10.

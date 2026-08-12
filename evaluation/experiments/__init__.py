"""Experiment packages for the TARA project.

Sits alongside `evaluation.rts_builder` (the frozen dataset-construction
pipeline). Nothing under `evaluation.experiments` may import from or
modify `evaluation.rts_builder`'s *behavior* -- experiment code is a
downstream *consumer* of the RTS dataset and, where noted, of the
frozen Feature Extraction / Retrieval Executor subsystems, never a
redesign of them.
"""

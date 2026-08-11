# Architecture Decision Records

Short, dated records of decisions that are expensive to reverse — the ones a
future contributor will want the *why* for, not just the *what*. Each ADR
states the context, the decision, and the alternatives that were rejected and
why. They are immutable once accepted: a later decision that changes course
gets its own ADR that supersedes the earlier one.

| ADR                                                                            | Status   | Summary                                                                                   |
| ------------------------------------------------------------------------------ | -------- | ----------------------------------------------------------------------------------------- |
| [0001](0001-consolidate-retrieval-and-inference.md)                            | Proposed | Collapse to a single hybrid store (Elasticsearch) and self-hosted inference; retire Chroma |

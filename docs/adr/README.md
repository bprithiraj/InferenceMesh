# Architecture decision record

The following decisions are accepted for the initial architecture. A later change requires a numbered ADR explaining evidence and migration impact.

| ID | Decision | Rationale |
| --- | --- | --- |
| ADR-001 | Keep InferenceMesh in a repository separate from the portfolio | The system stays runnable while the portfolio remains a presentation layer |
| ADR-002 | Begin as a modular Python service | Avoid network boundaries and duplicated contracts before scaling evidence exists |
| ADR-003 | Use vLLM for text and Triton for embeddings/reranking | Each serving engine has a distinct, testable responsibility |
| ADR-004 | Defer Ray Serve | It requires a real multi-stage workload, not a résumé keyword |
| ADR-005 | Apply hard eligibility filters before weighted scoring | Safety and capability constraints cannot be traded for latency |
| ADR-006 | Decouple online routing snapshots from MLflow availability | Control-plane failure must not interrupt serving |
| ADR-007 | Implement exact cache before semantic cache | Correctness and isolation precede hit-rate optimization |
| ADR-008 | Keep Kafka off the synchronous inference path | Batch backlog cannot increase online token latency |
| ADR-009 | Expose sanitized demo data, not infrastructure consoles | Recruiters can inspect behavior without receiving administrative access |
| ADR-010 | Publish complete benchmark context | Hardware-free performance numbers are not credible evidence |

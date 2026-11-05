# The_Auditor Skill
(Please note that The_Auditor does actually exist yet)

## Overview
`The_Auditor` acts as the reconciliation and validation layer for the Document Intelligence Orchestra. It aggregates evidence from multiple chunks to provide a verified "ground truth" in the form of a fact history that extends beyond a single chunk.

## Core Functionality
- **Evidence Aggregation**: Collects the "atomic" claims and evidence produced by `The_Reader`.
- **Conflict resolution**: Identified discrepancies where different chunks or sources provide conflicting information.
- **Audit Logging**: Maintains a persistent history of facts, claims, and verification statuses.
- **Facthistory**: Manages the "FactHistory" problem-ensuring that the system knows what it has resolved across different processing runs.

## Integration
- **Inputs**: Records from `The_Reader` and the current state of the `FactHistory`.
- **Outputs**: Verified Findings and Audit Records.
- **Role in Orchestra**: The fial arbiter of "What the system knows" versus "What the model concludes".

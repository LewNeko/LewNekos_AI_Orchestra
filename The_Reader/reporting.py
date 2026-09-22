"""
reporting.py
------------
Human-readable rendering of ReaderResult objects. Pure presentation - no
verification, parsing, or pipeline logic lives here.
"""


def print_final_report(results):
    """Print each ReaderResult as the claim/evidence/revision tree, not a
    flat answer field - so the chain that produced current_value is visible."""
    for r in results:
        print(f"""
Fact
|
+-- Question
|     {r.question}  ({r.fact_type})
|
+-- Initial claim
|     Value: {r.initial_claim.value}
|     Evidence: "{r.initial_claim.evidence.quote}\"""")
        if r.evidence_repair is not None:
            print(f"""|
+-- Evidence repair
|     New evidence: "{r.evidence_repair.quote}\"""")
        if r.support_judgment is not None:
            print(f"""|
+-- Support judgment
|     {r.support_judgment.verdict}""")
        if r.corrected_claim is not None:
            print(f"""|
+-- Corrected claim
|     Value: {r.corrected_claim.value}
|     Evidence: "{r.corrected_claim.evidence.quote}\"""")
        if r.revision is not None:
            print(f"""|
+-- Revision
|     {r.revision.operation} {r.revision.amount}
|     Evidence: "{r.revision.evidence.quote}\"""")
        print(f"""|
+-- Status: {r.status}""")
        if r.reason:
            print(f"|     reason: {r.reason}")
        print(f"""|
`-- Current value
      {r.current_value}
""")
        print("----------------")

"""Scoring service – combines Layer-1 and Layer-2 results into a final verdict.

Authoritative scoring formula (overrides spec.md Section 2):

    S_final = S_DB × (0.60 × S_rule + 0.40 × S_visual)

- S_DB ∈ {0, 1}: 1 if batch exists in DB, else 0 (multiplicative hard gate).
- S_rule ∈ [0, 100]: deterministic score from DB gate (100 = match, 0 = mismatch).
- S_visual ∈ [0, 100]: external AI / visual inspection score.

Verdict bands:
    80–100  → GENUINE
    50–79   → REVIEW_RECOMMENDED
    0–49    → SUSPECTED_COUNTERFEIT

This is one isolated, named function so the formula can be swapped later.
"""


def compute_final_score(s_db: int, s_rule: int, s_visual: float) -> tuple[float, str]:
    """Compute the final authenticity score and verdict.

    Parameters
    ----------
    s_db : int
        Database gate flag. 1 if batch exists, 0 otherwise.
    s_rule : int
        Deterministic rule score (0 or 100).
    s_visual : float
        AI / visual inspection score in [0, 100].

    Returns
    -------
    tuple[float, str]
        ``(authenticity_score, verdict)``
    """

    if s_db == 0:
        score = 0.0
    else:
        score = s_db * (0.60 * s_rule + 0.40 * s_visual)

    # Clamp to [0, 100]
    score = max(0.0, min(100.0, score))

    if score >= 80:
        verdict = "GENUINE"
    elif score >= 50:
        verdict = "REVIEW_RECOMMENDED"
    else:
        verdict = "SUSPECTED_COUNTERFEIT"

    return (round(score, 2), verdict)

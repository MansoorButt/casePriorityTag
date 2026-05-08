def calculate_priority_score(signals: dict) -> tuple[int, list[dict]]:
    """
    Returns (score, breakdown_list).
    Score is 0-100. Breakdown explains every point added.
    """
    score = 0
    breakdown = []

    # ── 1. Case type weight (max 35 pts) ─────────────────────────────────────
    type_weights = {
        "terrorism":  35,
        "murder":     30,
        "rape":       28,
        "kidnapping": 28,
        "drug":       22,
        "robbery":    20,
        "corruption": 18,
        "fraud":      15,
        "civil":      10,
        "property":    8,
        "other":       5,
    }
    case_type = signals.get("case_type", "other").lower()
    type_pts  = type_weights.get(case_type, 5)
    score += type_pts
    breakdown.append({
        "signal":  "Case type",
        "detail":  case_type.capitalize(),
        "points":  type_pts,
        "max":     35,
    })

    # ── 2. Time waiting (max 25 pts) ─────────────────────────────────────────
    days = int(signals.get("days_waiting", 0))
    if   days > 365: wait_pts = 25
    elif days > 180: wait_pts = 18
    elif days > 90:  wait_pts = 10
    elif days > 30:  wait_pts = 5
    else:            wait_pts = 2
    score += wait_pts
    breakdown.append({
        "signal":  "Time waiting",
        "detail":  f"{days} days pending",
        "points":  wait_pts,
        "max":     25,
    })

    # ── 3. Accused in custody (max 20 pts) ───────────────────────────────────
    if signals.get("accused_in_custody"):
        score += 20
        breakdown.append({
            "signal": "Accused in custody",
            "detail": "Liberty at stake — expedite hearing",
            "points": 20,
            "max":    20,
        })

    # ── 4. Vulnerable persons (max 15 pts) ───────────────────────────────────
    if signals.get("involves_minor"):
        score += 15
        breakdown.append({
            "signal": "Minor involved",
            "detail": "Child victim or accused",
            "points": 15,
            "max":    15,
        })
    elif signals.get("involves_woman"):
        score += 10
        breakdown.append({
            "signal": "Woman involved",
            "detail": "Female victim or accused",
            "points": 10,
            "max":    15,
        })
    elif signals.get("involves_elder"):
        score += 8
        breakdown.append({
            "signal": "Elderly involved",
            "detail": "Senior citizen victim or accused",
            "points": 8,
            "max":    15,
        })

    # ── 5. Adjournments (max 5 pts) ──────────────────────────────────────────
    adj = int(signals.get("adjournment_count", 0))
    if   adj > 7: adj_pts = 5
    elif adj > 3: adj_pts = 3
    elif adj > 1: adj_pts = 1
    else:         adj_pts = 0
    if adj_pts > 0:
        score += adj_pts
        breakdown.append({
            "signal": "Adjournments",
            "detail": f"{adj} delays recorded",
            "points": adj_pts,
            "max":    5,
        })

    final_score = min(score, 100)

    return final_score, breakdown


def get_tag(score: int) -> str:
    if score >= 75: return "Critical"
    if score >= 40: return "Medium"
    return "Routine"


def get_tag_color(tag: str) -> str:
    return {"Critical": "#ef4444", "Medium": "#f59e0b", "Routine": "#10b981"}[tag]

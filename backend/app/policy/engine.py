import logging
import operator as py_op
from typing import Any
from ..models import SOPDefinition, PolicyResult

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

OPERATORS = {
    "eq": py_op.eq,
    "neq": py_op.ne,
    "gt": py_op.gt,
    "gte": py_op.ge,
    "lt": py_op.lt,
    "lte": py_op.le,
    "in": lambda actual, allowed: actual in allowed if allowed is not None else False,
    "contains": lambda container, item: item in container if container is not None else False,
}


def evaluate_condition(condition: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, str]:
    if "all" in condition:
        items = condition["all"]
        sub_results = [evaluate_condition(c, facts) for c in items]
        all_passed = all(res[0] for res in sub_results)
        detail = "all(" + " AND ".join(res[1] for res in sub_results) + ")"
        return all_passed, detail

    if "any" in condition:
        items = condition["any"]
        sub_results = [evaluate_condition(c, facts) for c in items]
        any_passed = any(res[0] for res in sub_results)
        detail = "any(" + " OR ".join(res[1] for res in sub_results) + ")"
        return any_passed, detail

    if "not" in condition:
        passed, detail = evaluate_condition(condition["not"], facts)
        return not passed, f"not({detail})"

    if "fuzzy_score" in condition:
        cfg = condition["fuzzy_score"]
        factors = cfg.get("factors", [])
        threshold = float(cfg.get("threshold", 0.5))
        op_name = cfg.get("operator", "gte")

        total_weight = 0.0
        weighted_score = 0.0
        factor_details = []

        for f in factors:
            f_name = f.get("field")
            actual = facts.get(f_name)
            weight = float(f.get("weight", 1.0))
            total_weight += weight

            if actual is None:
                return False, f"fuzzy factor '{f_name}' unavailable in facts"

            opt_min = float(f.get("optimal_min", actual))
            opt_max = float(f.get("optimal_max", actual))
            tolerance = float(f.get("tolerance", 10.0))

            # Triangular / trapezoidal fuzzy membership function
            if opt_min <= actual <= opt_max:
                factor_score = 1.0
            elif actual < opt_min:
                diff = opt_min - actual
                factor_score = max(0.0, 1.0 - (diff / tolerance))
            else:
                diff = actual - opt_max
                factor_score = max(0.0, 1.0 - (diff / tolerance))

            weighted_score += factor_score * weight
            factor_details.append(f"{f_name}={actual}(score={factor_score:.2f})")

        final_score = (weighted_score / total_weight) if total_weight > 0 else 0.0
        op_func = OPERATORS.get(op_name, py_op.ge)
        passed = bool(op_func(final_score, threshold))
        detail = f"fuzzy_score({final_score:.2f} {op_name} {threshold}, factors: [{', '.join(factor_details)}]) => {passed}"
        return passed, detail

    field = condition.get("field")
    op_name = condition.get("operator")
    target_value = condition.get("value")

    if not field or not op_name:
        return False, "invalid_condition_syntax"

    actual_value = facts.get(field)
    if actual_value is None:
        return False, f"{field} unavailable in facts"

    op_func = OPERATORS.get(op_name)
    if not op_func:
        logger.error("Unsupported policy operator: %s", op_name)
        return False, f"unsupported operator '{op_name}'"

    try:
        passed = bool(op_func(actual_value, target_value))
    except (TypeError, ValueError) as err:
        logger.debug("Evaluation error for %s %s %s: %s", field, op_name, target_value, err)
        passed = False

    return passed, f"({field}={actual_value} {op_name} {target_value}) => {passed}"


def evaluate_policies(
    sops: list[SOPDefinition],
    activity: str,
    facts: dict[str, Any],
) -> PolicyResult:
    trace: list[dict[str, Any]] = []
    applicable = [s for s in sops if activity in s.activities]

    if not applicable:
        return PolicyResult(
            outcome="no_match",
            trace=[{"info": f"No SOP definitions registered for activity '{activity}'"}],
        )

    matched: list[SOPDefinition] = []
    missing_data_detected = False

    for sop in applicable:
        passed, detail = evaluate_condition(sop.conditions, facts)
        trace.append({
            "sop_id": sop.id,
            "title": sop.title,
            "severity": sop.severity,
            "priority": sop.priority,
            "matched": passed,
            "detail": detail,
        })
        if "unavailable in facts" in detail:
            missing_data_detected = True

        if passed:
            matched.append(sop)

    if not matched:
        if missing_data_detected:
            return PolicyResult(
                outcome="insufficient_data",
                trace=trace,
            )
        return PolicyResult(
            outcome="no_match",
            trace=trace,
        )

    # Deterministic winner selection: highest severity first, then highest priority
    winner = max(
        matched,
        key=lambda s: (SEVERITY_WEIGHTS.get(s.severity, 0), s.priority),
    )

    return PolicyResult(
        outcome="matched",
        sop_id=winner.id,
        title=winner.title,
        severity=winner.severity,
        priority=winner.priority,
        guidance=winner.guidance,
        trace=trace,
    )

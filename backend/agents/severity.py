"""Deterministic severity rubric (POL-004 section 1). The LLM never sets or changes severity."""

PRIVILEGED_ACCOUNT_TYPES = {"admin"}
HIGH_CRITICALITY = {"high", "critical"}


def rate_severity(account_type: str, asset_criticalities: list[str],
                  unauthorized_access: bool, impact_confirmed: bool = False) -> str:
    """
    critical: unauthorized access AND evidence of severe impact (privileged changes / data transfer)
    high:     privileged account + unauthorized/expired access + (2+ assets OR a high/critical asset)
    medium:   unauthorized/expired access otherwise, or privileged activity on a high/critical asset
    low:      anything else that was flagged
    """
    privileged = account_type in PRIVILEGED_ACCOUNT_TYPES
    touches_high = any(c in HIGH_CRITICALITY for c in asset_criticalities)
    if unauthorized_access and impact_confirmed:
        return "critical"
    if privileged and unauthorized_access and (len(asset_criticalities) >= 2 or touches_high):
        return "high"
    if unauthorized_access or (privileged and touches_high):
        return "medium"
    return "low"

def validate_context(context: dict, partial: bool = False) -> bool:
    """
    Validates that the context dictionary conforms to the required schema.
    Raises ValueError if validation fails.
    """
    required_keys = {
        "keyword": (str, type(None)),
        "category": (str, type(None)),
        "source": (str, type(None)),
        "agenda_brief": (str, type(None)),
        "draft_html": (str, type(None)),
        "verification_report": (dict, type(None)),
        "published_post_id": (str, type(None)),
        "published_url": (str, type(None))
    }
    
    allowed_keys = {
        "keyword", "category", "source", "agenda_brief", "draft_html",
        "verification_report", "published_post_id", "published_url",
        "pdf_path", "persona", "source_platform", "trends"
    }
    
    # Check for any completely unknown keys
    for key in context:
        if key not in allowed_keys:
            raise ValueError(f"Schema validation error: Unexpected key '{key}' in context")
            
    # Check that all required keys are present
    for key, expected_types in required_keys.items():
        if key not in context:
            if partial:
                continue
            raise ValueError(f"Schema validation error: Missing required key '{key}'")
            
        value = context[key]
        if not isinstance(value, expected_types):
            raise ValueError(f"Schema validation error: Key '{key}' has type {type(value).__name__}, expected {expected_types}")
            
    # Check structure of verification_report if present and not None
    vr = context.get("verification_report")
    if vr is not None:
        if "is_passed" not in vr:
            raise ValueError("Schema validation error: 'verification_report' must contain 'is_passed' key")
        if not isinstance(vr["is_passed"], bool):
            raise ValueError(f"Schema validation error: 'verification_report.is_passed' must be a boolean, got {type(vr['is_passed']).__name__}")
        if "issues" not in vr:
            raise ValueError("Schema validation error: 'verification_report' must contain 'issues' key")
        if not isinstance(vr["issues"], list):
            raise ValueError(f"Schema validation error: 'verification_report.issues' must be a list, got {type(vr['issues']).__name__}")
        # Verify that all items in issues are strings
        for issue in vr["issues"]:
            if not isinstance(issue, str):
                raise ValueError(f"Schema validation error: All items in 'verification_report.issues' must be strings, got {type(issue).__name__}")
                
    return True

def get_initial_context() -> dict:
    """
    Returns an initialized context dict matching the schema with default/empty/None values.
    """
    return {
        "keyword": None,
        "category": None,
        "source": None,
        "agenda_brief": None,
        "draft_html": None,
        "verification_report": None,
        "published_post_id": None,
        "published_url": None
    }

def create_default_context() -> dict:
    """
    Alias/wrapper for get_initial_context() to support alternative names.
    """
    return get_initial_context()

"""Random, non-identifying ID generation for analyses and sessions."""
import uuid


def new_analysis_id() -> str:
    return f"an_{uuid.uuid4().hex[:16]}"


def new_sample_id() -> str:
    return f"smp_{uuid.uuid4().hex[:16]}"


def new_session_id() -> str:
    return f"ses_{uuid.uuid4().hex[:12]}"

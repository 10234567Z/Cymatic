import bcrypt


def hash_pin(raw_pin: str) -> str:
    """
    Takes the raw DTMF digits (e.g. "4729") and returns a bcrypt hash.
    The hash is what gets stored in Supabase — never the raw digits.
    """
    return bcrypt.hashpw(raw_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(raw_pin: str, stored_hash: str) -> bool:
    """
    Checks the entered PIN against the stored bcrypt hash.
    Returns True if correct, False if wrong.
    """
    return bcrypt.checkpw(raw_pin.encode("utf-8"), stored_hash.encode("utf-8"))

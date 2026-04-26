from app.models.session import CallSession, CallState

# In-memory store: { "CA1a2b3c...": CallSession(...) }
_sessions: dict[str, CallSession] = {}


def create(call_sid: str, phone_number: str, state: CallState) -> CallSession:
    session = CallSession(
        call_sid=call_sid,
        phone_number=phone_number,
        state=state,
    )
    _sessions[call_sid] = session
    return session


def get(call_sid: str) -> CallSession | None:
    return _sessions.get(call_sid)


def update(call_sid: str, **kwargs) -> CallSession | None:
    session = _sessions.get(call_sid)
    if not session:
        return None
    updated = session.model_copy(update=kwargs)
    _sessions[call_sid] = updated
    return updated


def destroy(call_sid: str) -> None:
    _sessions.pop(call_sid, None)

import uuid

def get_correlation_id() -> str:
    return str(uuid.uuid4())

def get_current_user():
    return {"id": 1, "email": "admin@neft.local"}

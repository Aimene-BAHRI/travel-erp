import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import AuditEvent

SENSITIVE_KEYS = {"password", "token", "access", "refresh", "secret", "passport_number"}


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


def _json_safe(value):
    return json.loads(json.dumps(_redact(value), cls=DjangoJSONEncoder))


def record_event(
    *,
    actor,
    action,
    target_type,
    target_id="",
    before=None,
    after=None,
    metadata=None,
    request=None,
):
    return AuditEvent.objects.create(
        agency=getattr(actor, "agency", None),
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        before=_json_safe(before or {}),
        after=_json_safe(after or {}),
        metadata=_json_safe(metadata or {}),
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestMeta:
    ip: str | None
    user_agent: str | None

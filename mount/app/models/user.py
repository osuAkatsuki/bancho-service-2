from app.models import BaseModel


class User(BaseModel):
    id: int
    username: str
    username_safe: str
    password_md5: str
    salt: str
    email: str
    register_datetime: int
    achievements_version: int
    latest_activity: int
    silence_end: int
    silence_reason: str
    password_version: int
    privileges: int
    donor_expire: int
    frozen: int
    flags: int
    notes: str | None
    aqn: bool
    ban_datetime: int
    switch_notifs: bool
    previous_overwrite: int
    whitelist: int
    clan_id: int
    clan_privileges: int
    userpage_allowed: bool
    converted: int
    freeze_reason: str | None

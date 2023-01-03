from app.models import BaseModel


class Token(BaseModel):
    token_id: str
    user_id: int
    username: str
    privileges: int
    whitelist: int
    kicked: bool
    login_time: int
    ping_time: int
    utc_offset: int
    tournament: bool
    block_non_friends_dm: bool
    spectating_token_id: str | None
    spectating_user_id: int | None
    latitude: float
    longitude: float
    ip: str
    country: int
    away_message: str | None
    match_id: int | None
    last_np_beatmap_id: int | None
    last_np_mods: int | None
    last_np_accuracy: float | None
    silence_end_time: int
    protocol_version: int
    spam_rate: int
    action_id: int
    action_text: str
    action_md5: str
    action_beatmap_id: int
    action_mods: int
    mode: int
    relax: bool
    autopilot: bool
    ranked_score: int
    accuracy: float
    playcount: int
    total_score: int
    global_rank: int
    pp: int

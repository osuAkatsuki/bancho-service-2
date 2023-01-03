from app.models import BaseModel


class Stats(BaseModel):
    ranked_score: int
    accuracy: float
    playcount: int
    total_score: int
    pp: int
    global_rank: int

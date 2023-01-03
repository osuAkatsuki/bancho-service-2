from app.common.context import Context
from app.models.stats import Stats
from app.repositories.stats import StatsRepository


async def fetch_one(
    ctx: Context,
    user_id: int,
    mode: int,
    relax_int: int,
) -> Stats | None:
    repo = StatsRepository(ctx)

    stats = await repo.fetch_one(user_id, mode, relax_int)
    if stats is None:
        return None

    return Stats.parse_obj(stats)

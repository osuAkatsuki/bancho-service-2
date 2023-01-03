from app.common.context import Context
from typing import Any


async def get_global_rank(ctx: Context, user_id: int, mode: int, relax_int: int) -> int:
    board = {
        0: "leaderboard",
        1: "relaxboard",
        2: "autoboard",
    }[mode]

    mode_str = {
        0: "std",
        1: "taiko",
        2: "ctb",
        3: "mania",
    }[mode]

    position = await ctx.redis.zrevrank(f"ripple:{board}:{mode_str}", user_id)
    if position is None:
        return 0

    return int(position) + 1


class StatsRepository:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

    async def fetch_one(
        self,
        user_id: int,
        mode: int,
        relax_int: int,
    ) -> dict[str, Any] | None:
        table = {
            0: "users_stats",
            1: "rx_stats",
            2: "ap_stats",
        }[relax_int]

        mode_str = {
            0: "std",
            1: "taiko",
            2: "ctb",
            3: "mania",
        }[mode]

        query = f"""\
            SELECT
                ranked_score_{mode_str} AS ranked_score,
                avg_accuracy_{mode_str} AS accuracy,
                playcount_{mode_str} AS playcount,
                total_score_{mode_str} AS total_score,
                pp_{mode_str} AS pp
            FROM {table}
            WHERE
                id = :user_id
        """
        params = {
            "user_id": user_id,
        }

        stats = await self.ctx.database.fetch_one(query, params)
        if stats is not None:
            stats["global_rank"] = await get_global_rank(
                self.ctx,
                user_id,
                mode,
                relax_int,
            )

        return stats

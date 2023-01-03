from app.common.context import Context
from typing import Any

import orjson


class TokensRepository:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

        self.READ_PARAMS = (
            "token_id, user_id, username, privileges, whitelist, kicked, login_time, ping_time, utc_offset, tournament, "
            "block_non_friends_dm, spectating_token_id, spectating_user_id, latitude, longitude, ip, country, away_message, "
            "match_id, last_np_beatmap_id, last_np_mods, last_np_accuracy, silence_end_time, protocol_version, spam_rate, "
            "action_id, action_text, action_md5, action_beatmap_id, action_mods, mode, relax, autopilot, ranked_score, accuracy, "
            "playcount, total_score, global_rank, pp"
        )

    async def fetch_one(
        self,
        token_id: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
    ) -> dict[str, Any] | None:
        query = f"""\
            SELECT {self.READ_PARAMS}
              FROM tokens
            WHERE
              token_id = COALESCE(:token_id, token_id)
              AND user_id = COALESCE(:user_id, user_id)
              AND username = COALESCE(:username, username)
        """
        params = {
            "token_id": token_id,
            "user_id": user_id,
            "username": username,
        }

        token = await self.ctx.database.fetch_one(query, params)
        return token

    async def fetch_all(
        self,
        token_id: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
    ) -> list[dict[str, Any]]:
        query = f"""\
            SELECT {self.READ_PARAMS}
              FROM tokens 
            WHERE
              token_id = COALESCE(:token_id, token_id)
              AND user_id = COALESCE(:user_id, user_id)
              AND username = COALESCE(:username, username)
        """
        params = {
            "token_id": token_id,
            "user_id": user_id,
            "username": username,
        }

        tokens = await self.ctx.database.fetch_all(query, params)
        return tokens

    async def create_one(
        self,
        token_id: str,
        user_id: int,
        username: str,
        privileges: int,
        whitelist: int,
        kicked: bool,
        login_time: int,
        ping_time: int,
        utc_offset: int,
        tournament: bool,
        block_non_friends_dm: bool,
        spectating_token_id: str | None,
        spectating_user_id: int | None,
        latitude: float,
        longitude: float,
        ip: str,
        country: int,
        away_message: str | None,
        match_id: int | None,
        last_np_beatmap_id: int | None,
        last_np_mods: int | None,
        last_np_accuracy: float | None,
        silence_end_time: int,
        protocol_version: int,
        spam_rate: int,
        action_id: int,
        action_text: str,
        action_md5: str,
        action_beatmap_id: int,
        action_mods: int,
        mode: int,
        relax: bool,
        autopilot: bool,
        ranked_score: int,
        accuracy: float,
        playcount: int,
        total_score: int,
        global_rank: int,
        pp: int,
    ) -> None:
        query = f"""\
            INSERT INTO tokens ({self.READ_PARAMS})
            VALUES (:token_id, :user_id, :username, :privileges, :whitelist, :kicked, :login_time, :ping_time, 
            :utc_offset, :tournament, :block_non_friends_dm, :spectating_token_id, :spectating_user_id, 
            :latitude, :longitude, :ip, :country, :away_message, :match_id, :last_np_beatmap_id, 
            :last_np_mods, :last_np_accuracy, :silence_end_time, :protocol_version, :spam_rate, 
            :action_id, :action_text, :action_md5, :action_beatmap_id, :action_mods, :mode, :relax, :autopilot, 
            :ranked_score, :accuracy, :playcount, :total_score, :global_rank, :pp)
        """
        params = {
            "token_id": token_id,
            "user_id": user_id,
            "username": username,
            "privileges": privileges,
            "whitelist": whitelist,
            "kicked": kicked,
            "login_time": login_time,
            "ping_time": ping_time,
            "utc_offset": utc_offset,
            "tournament": tournament,
            "block_non_friends_dm": block_non_friends_dm,
            "spectating_token_id": spectating_token_id,
            "spectating_user_id": spectating_user_id,
            "latitude": latitude,
            "longitude": longitude,
            "ip": ip,
            "country": country,
            "away_message": away_message,
            "match_id": match_id,
            "last_np_beatmap_id": last_np_beatmap_id,
            "last_np_mods": last_np_mods,
            "last_np_accuracy": last_np_accuracy,
            "silence_end_time": silence_end_time,
            "protocol_version": protocol_version,
            "spam_rate": spam_rate,
            "action_id": action_id,
            "action_text": action_text,
            "action_md5": action_md5,
            "action_beatmap_id": action_beatmap_id,
            "action_mods": action_mods,
            "mode": mode,
            "relax": relax,
            "autopilot": autopilot,
            "ranked_score": ranked_score,
            "accuracy": accuracy,
            "playcount": playcount,
            "total_score": total_score,
            "global_rank": global_rank,
            "pp": pp,
        }

        await self.ctx.database.execute(query, params)

    async def partial_update(self, token_id: str, **updates: Any) -> dict[str, Any]:
        query = f"""\
            UPDATE tokens
               SET {', '.join(f'{key} = :{key}' for key in updates)}
             WHERE token_id = :token_id
        """
        params = {"token_id": token_id, **updates}

        await self.ctx.database.execute(query, params)

        token = await self.fetch_one(token_id)
        assert token is not None
        return token

    async def delete_one(self, token_id: str) -> None:
        query = f"""\
            DELETE FROM
              tokens
            WHERE
              token_id = :token_id
        """
        params = {"token_id": token_id}

        await self.ctx.database.execute(query, params)

    async def enqueue(self, token_id: str, data: list[int]) -> None:
        query = f"""\
            INSERT INTO token_buffers (token_id, buffer)
            VALUES (:token_id, :data)
        """
        params = {
            "token_id": token_id,
            "data": orjson.dumps(data).decode(),
        }

        await self.ctx.database.execute(query, params)

    async def dequeue(self, token_id: str) -> list[dict[str, Any]]:
        query = f"""\
            SELECT
              buffer_id,
              buffer
            FROM
              token_buffers
            WHERE
              token_id = :token_id
            ORDER BY
              buffer_id
            ASC
        """
        params = {"token_id": token_id}

        data = await self.ctx.database.fetch_all(query, params)
        for buffer in data:
            query = """\
                DELETE FROM token_buffers
                WHERE buffer_id = :buffer_id
            """
            params = {
                "buffer_id": buffer["buffer_id"],
            }
            await self.ctx.database.execute(query, params)

        return data

from app.common.context import Context

from typing import Any


class UsersRepository:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

        self.READ_PARAMS = (
            "id, username, username_safe, password_md5, salt, email, register_datetime, "
            "achievements_version, latest_activity, silence_end, silence_reason, password_version, "
            "privileges, donor_expire, frozen, flags, notes, aqn, ban_datetime, switch_notifs, previous_overwrite, "
            "whitelist, clan_id, clan_privileges, userpage_allowed, converted, freeze_reason"
        )

    async def fetch_one(
        self,
        id: int | None = None,
        username: str | None = None,
    ) -> dict[str, Any] | None:
        query = f"""\
            SELECT {self.READ_PARAMS}
              FROM users
            WHERE id = COALESCE(:id, id)
              AND username = COALESCE(:username, username)
        """
        params = {
            "id": id,
            "username": username,
        }

        user = await self.ctx.database.fetch_one(query, params)
        return user

    async def partial_update(
        self,
        id: int,
        **updates: Any,
    ) -> dict[str, Any]:
        query = f"""\
            UPDATE users
               SET {', '.join(f'{key} = :{key}' for key in updates)}
             WHERE id = :id
        """
        params = {"id": id, **updates}

        await self.ctx.database.execute(query, params)

        user = await self.fetch_one(id=id)
        assert user is not None
        return user

from app.common.context import Context
from typing import Any


class ChannelsRepository:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

        self.READ_PARAMS = (
            "name, description, public_read, public_write, moderated, instance"
        )

    async def fetch_one(
        self,
        channel_name: str | None = None,
    ) -> dict[str, Any] | None:
        query = f"""\
            SELECT
              {self.READ_PARAMS}
            FROM
              channels
            WHERE
              name = COALESCE(:channel_name, name)
        """
        params = {
            "channel_name": channel_name,
        }

        channel = await self.ctx.database.fetch_one(query, params)
        return channel

    async def fetch_all(self) -> list[dict[str, Any]]:
        query = f"""\
            SELECT {self.READ_PARAMS} FROM channels
        """

        channels = await self.ctx.database.fetch_all(query)
        return channels

    async def create_one(
        self,
        channel_name: str,
        description: str,
        public_read: bool,
        public_write: bool,
        moderated: bool,
        instance: bool,
    ) -> dict[str, Any]:
        query = f"""\
            INSERT INTO channels (name, description, public_read, public_write, moderated, instance)
            VALUES (:channel_name, :description, :public_read, :public_write, :moderated, :instance)
        """
        params = {
            "channel_name": channel_name,
            "description": description,
            "public_read": public_read,
            "public_write": public_write,
            "moderated": moderated,
            "instance": instance,
        }

        await self.ctx.database.execute(query, params)

        channel = await self.fetch_one(channel_name=channel_name)
        assert channel is not None

        return channel

    async def partial_update(
        self,
        channel_name: str,
        **updates: Any,
    ) -> dict[str, Any]:
        query = f"""\
            UPDATE channels
               SET {', '.join(f'{key} = :{key}' for key in updates)}
             WHERE name = :channel_name
        """
        params = {
            "channel_name": channel_name,
        }

        await self.ctx.database.execute(query, params)

        channel = await self.fetch_one(channel_name)
        assert channel is not None
        return channel

    async def delete_one(self, channel_name: str) -> None:
        query = """\
            DELETE FROM
              channels
            WHERE
              channel_name = :channel_name
        """
        params = {
            "channel_name": channel_name,
        }

        await self.ctx.database.execute(query, params)

    async def fetch_clients(
        self,
        token_id: str | None = None,
        channel_name: str | None = None,
    ) -> list[dict[str, Any]]:
        query = f"""\
            SELECT
              token_id, channel_name
            FROM
              channel_tokens
            WHERE
              channel_name = COALESCE(:channel_name, channel_name)
              AND token_id = COALESCE(:token_id, token_id)
        """
        params = {
            "channel_name": channel_name,
            "token_id": token_id,
        }

        clients = await self.ctx.database.fetch_all(query, params)
        return clients

    async def add_client(
        self,
        channel_name: str,
        token_id: str,
    ) -> None:
        query = f"""\
            INSERT INTO channel_tokens (channel_name, token_id)
            VALUES (:channel_name, :token_id)
        """
        params = {"channel_name": channel_name, "token_id": token_id}

        await self.ctx.database.execute(query, params)

    async def remove_client(
        self,
        channel_name: str,
        token_id: str,
    ) -> None:
        query = """\
            DELETE FROM 
              channel_tokens
            WHERE
              channel_name = :channel_name 
              AND token_id = :token_id
        """
        params = {
            "channel_name": channel_name,
            "token_id": token_id,
        }

        await self.ctx.database.execute(query, params)

from app.common.context import Context
from typing import Any


class StreamsRepository:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

        self.READ_PARAMS = "name"

    async def fetch_one(
        self,
        stream_name: str,
    ) -> dict[str, Any] | None:
        query = f"""\
            SELECT
              {self.READ_PARAMS}
            FROM
              streams
            WHERE
              name = COALESCE(:stream_name, name)
        """
        params = {
            "stream_name": stream_name,
        }

        stream = await self.ctx.database.fetch_one(query, params)
        return stream

    async def fetch_all(self) -> list[dict[str, Any]]:
        query = f"""\
            SELECT {self.READ_PARAMS} FROM streams
        """

        streams = await self.ctx.database.fetch_all(query)
        return streams

    async def create_one(self, stream_name: str) -> dict[str, Any]:
        query = f"""\
            INSERT INTO streams (name)
            VALUES (:stream_name)
        """
        params = {
            "stream_name": stream_name,
        }

        await self.ctx.database.execute(query, params)

        stream = await self.fetch_one(stream_name=stream_name)
        assert stream is not None

        return stream

    async def partial_update(
        self,
        stream_name: str,
        **updates: Any,
    ) -> dict[str, Any]:
        query = f"""\
            UPDATE streams
               SET {', '.join(f'{key} = :{key}' for key in updates)}
             WHERE name = :stream_name
        """
        params = {
            "stream_name": stream_name,
        }

        await self.ctx.database.execute(query, params)

        stream = await self.fetch_one(stream_name)
        assert stream is not None
        return stream

    async def delete_one(self, stream_name: str) -> None:
        query = """\
            DELETE FROM
              streams
            WHERE
              stream_name = :stream_name
        """
        params = {
            "stream_name": stream_name,
        }

        await self.ctx.database.execute(query, params)

    async def fetch_clients(
        self,
        stream_name: str,
    ) -> list[dict[str, Any]]:
        query = f"""\
            SELECT
              token_id
            FROM
              stream_tokens
            WHERE
              stream_name = COALESCE(:stream_name, stream_name)
        """
        params = {
            "stream_name": stream_name,
        }

        clients = await self.ctx.database.fetch_all(query, params)
        return clients

    async def add_client(
        self,
        stream_name: str,
        token_id: str,
    ) -> None:
        query = f"""\
            INSERT INTO stream_tokens (stream_name, token_id)
            VALUES (:stream_name, :token_id)
        """
        params = {"stream_name": stream_name, "token_id": token_id}

        await self.ctx.database.execute(query, params)

    async def remove_client(
        self,
        stream_name: str,
        token_id: str,
    ) -> None:
        query = """\
            DELETE FROM 
              stream_tokens
            WHERE
              stream_name = :stream_name 
              AND token_id = :token_id
        """
        params = {
            "stream_name": stream_name,
            "token_id": token_id,
        }

        await self.ctx.database.execute(query, params)

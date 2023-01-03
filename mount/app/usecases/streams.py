from app.repositories.streams import StreamsRepository
from app.usecases import tokens as tokens_usecases
from app.common.context import Context
from app.models.stream import Stream
from typing import Any


async def fetch_one(
    ctx: Context,
    stream_name: str,
) -> Stream | None:
    repo = StreamsRepository(ctx)

    stream = await repo.fetch_one(stream_name)
    if stream is None:
        return None

    return Stream.parse_obj(stream)


async def fetch_all(ctx: Context) -> list[Stream]:
    repo = StreamsRepository(ctx)

    streams = await repo.fetch_all()
    return [Stream.parse_obj(stream) for stream in streams]


async def fetch_clients(
    ctx: Context,
    stream_channel: str,
) -> list[str]:
    repo = StreamsRepository(ctx)

    clients = await repo.fetch_clients(stream_channel)
    return [client["token_id"] for client in clients]


async def create_one(
    ctx: Context,
    stream_name: str,
) -> Stream:
    repo = StreamsRepository(ctx)

    stream = await repo.create_one(stream_name)
    return Stream.parse_obj(stream)


async def delete_one(
    ctx: Context,
    stream_name: str,
) -> None:
    stream = await fetch_one(ctx, stream_name)
    assert stream is not None

    clients = await fetch_clients(ctx, stream_name)
    for client in clients:
        await tokens_usecases.leave_stream(ctx, client, stream_name)

    repo = StreamsRepository(ctx)
    await repo.delete_one(stream_name)


async def partial_update(
    ctx: Context,
    stream_name: str,
    **updates: Any,
) -> Stream:
    repo = StreamsRepository(ctx)

    stream = await repo.partial_update(stream_name, **updates)
    return Stream.parse_obj(stream)


async def add_client(
    ctx: Context,
    stream_name: str,
    token_id: str,
) -> None:
    repo = StreamsRepository(ctx)
    await repo.add_client(stream_name, token_id)


async def remove_client(
    ctx: Context,
    stream_name: str,
    token_id: str,
) -> None:
    repo = StreamsRepository(ctx)
    await repo.remove_client(stream_name, token_id)


async def broadcast(
    ctx: Context,
    stream_name: str,
    data: bytes,
    ignore_list: list[str] | None = None,
) -> None:
    stream = await fetch_one(ctx, stream_name)
    assert stream is not None

    clients = await fetch_clients(ctx, stream_name)
    for client in clients:
        if ignore_list is not None and client in ignore_list:
            continue

        await tokens_usecases.enqueue(ctx, client, data)


async def selective_broadcast(
    ctx: Context,
    stream_name: str,
    data: bytes,
    clients: list[str],
) -> None:
    stream = await fetch_one(ctx, stream_name)
    assert stream is not None

    for client in clients:
        await tokens_usecases.enqueue(ctx, client, data)

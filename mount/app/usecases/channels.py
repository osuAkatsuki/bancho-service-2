from app.repositories.channels import ChannelsRepository
from app.usecases import tokens as tokens_usecases
from app.usecases import streams as streams_usecases
from app.common.context import Context
from app.models.channel import Channel
from app.common import logger
from typing import Any


async def fetch_one(
    ctx: Context,
    channel_name: str,
) -> Channel | None:
    repo = ChannelsRepository(ctx)

    channel = await repo.fetch_one(channel_name)
    if channel is None:
        return None

    return Channel.parse_obj(channel)


async def fetch_all(ctx: Context) -> list[Channel]:
    repo = ChannelsRepository(ctx)

    channels = await repo.fetch_all()
    return [Channel.parse_obj(channel) for channel in channels]


async def fetch_clients(
    ctx: Context,
    token_id: str | None = None,
    channel_name: str | None = None,
) -> list[dict[str, Any]]:
    repo = ChannelsRepository(ctx)

    clients = await repo.fetch_clients(token_id=token_id, channel_name=channel_name)
    return clients


async def create_one(
    ctx: Context,
    channel_name: str,
    description: str,
    public_read: bool,
    public_write: bool,
    moderated: bool,
    instance: bool,
) -> Channel:
    await streams_usecases.create_one(ctx, f"chat/{channel_name}")

    repo = ChannelsRepository(ctx)

    raw_channel = await repo.create_one(
        channel_name,
        description,
        public_read,
        public_write,
        moderated,
        instance,
    )
    channel = Channel.parse_obj(raw_channel)

    bot = await tokens_usecases.fetch_one(ctx, user_id=999)
    assert bot is not None

    await tokens_usecases.join_channel(ctx, bot.token_id, channel.name)

    logger.info(f"Created channel {channel_name}.")
    return channel


async def delete_one(
    ctx: Context,
    channel_name: str,
) -> None:
    clients = await streams_usecases.fetch_clients(ctx, f"chat/{channel_name}")
    for client in clients:
        token = await tokens_usecases.fetch_one(ctx, token_id=client)
        if token is None:
            continue

        await tokens_usecases.leave_channel(
            ctx,
            token.token_id,
            channel_name,
            kick=True,
        )

    await streams_usecases.delete_one(ctx, f"chat/{channel_name}")

    repo = ChannelsRepository(ctx)
    await repo.delete_one(channel_name)

    logger.info(f"Removed channel {channel_name}")


async def partial_update(
    ctx: Context,
    channel_name: str,
    **updates: Any,
) -> Channel:
    repo = ChannelsRepository(ctx)

    channel = await repo.partial_update(channel_name, **updates)
    return Channel.parse_obj(channel)


async def add_client(
    ctx: Context,
    channel_name: str,
    token_id: str,
) -> None:
    repo = ChannelsRepository(ctx)
    await repo.add_client(channel_name, token_id)


async def remove_client(
    ctx: Context,
    channel_name: str,
    token_id: str,
) -> None:
    repo = ChannelsRepository(ctx)
    await repo.remove_client(channel_name, token_id)


def get_client_name(channel_name: str) -> str:
    if channel_name.startswith("#spect_"):
        return "#spectator"
    elif channel_name.startswith("#multi_"):
        return "#multiplayer"

    return channel_name

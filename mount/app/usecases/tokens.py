from app.models.token import Token
from app.models.mode import Mode
from app.models.action import Action
from app.models.privileges import Privileges
from app.common.context import Context
from app.repositories.tokens import TokensRepository
from app.usecases import streams as streams_usecases
from app.usecases import users as users_usecases
from app.usecases import stats as stats_usecases
from app.usecases import channels as channels_usecases
from app.common import serial
from uuid import uuid4

import time
import orjson


async def fetch_one(
    ctx: Context,
    token_id: str | None = None,
    user_id: int | None = None,
    username: str | None = None,
) -> Token | None:
    repo = TokensRepository(ctx)

    token = await repo.fetch_one(token_id, user_id, username)
    if token is None:
        return None

    return Token.parse_obj(token)


async def fetch_all(
    ctx: Context,
    token_id: str | None = None,
    user_id: int | None = None,
    username: str | None = None,
) -> list[Token]:
    repo = TokensRepository(ctx)

    tokens = await repo.fetch_all(token_id, user_id, username)
    return [Token.parse_obj(token) for token in tokens]


async def create_one(
    ctx: Context,
    user_id: int,
    username: str,
    privileges: int,
    whitelist: int,
    silence_end_time: int,
    ip: str,
    utc_offset: int,
    tournament: bool,
    block_non_friends_dm: bool,
) -> Token:
    now = int(time.time())

    token_params = {
        "token_id": str(uuid4()),
        "user_id": user_id,
        "username": username,
        "privileges": privileges,
        "whitelist": whitelist,
        "kicked": False,
        "login_time": now,
        "ping_time": now,
        "utc_offset": utc_offset,
        "tournament": tournament,
        "block_non_friends_dm": block_non_friends_dm,
        "spectating_token_id": None,
        "spectating_user_id": None,
        "latitude": 0.0,
        "longitude": 0.0,
        "ip": ip,
        "country": 0,
        "away_message": None,
        "match_id": None,
        "last_np_beatmap_id": None,
        "last_np_mods": None,
        "last_np_accuracy": None,
        "silence_end_time": silence_end_time,
        "protocol_version": 0,
        "spam_rate": 0,
        "action_id": Action.IDLE,
        "action_text": "",
        "action_md5": "",
        "action_mods": 0,
        "action_beatmap_id": 0,
        "mode": Mode.STD,
        "relax": False,
        "autopilot": False,
        "ranked_score": 0,
        "accuracy": 0.0,
        "playcount": 0,
        "total_score": 0,
        "global_rank": 0,
        "pp": 0,
    }

    token = Token.parse_obj(token_params)
    repo = TokensRepository(ctx)
    await repo.create_one(**token_params)

    token = await update_cached_stats(ctx, token.token_id)
    await join_stream(ctx, token.token_id, stream_name="main")

    return token


async def partial_update(
    ctx: Context,
    token_id: str,
    **kwargs,
) -> Token:
    repo = TokensRepository(ctx)
    new_token = await repo.partial_update(token_id, **kwargs)

    return Token.parse_obj(new_token)


async def delete_one(
    ctx: Context,
    token_id: str,
) -> None:
    repo = TokensRepository(ctx)
    await repo.delete_one(token_id)


async def update_cached_stats(ctx: Context, token_id: str) -> Token:
    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    relax_int = 0
    if token.relax:
        relax_int = 1
    elif token.autopilot:
        relax_int = 2

    stats = await stats_usecases.fetch_one(ctx, token.user_id, token.mode, relax_int)
    assert stats is not None

    new_token = await partial_update(
        ctx,
        token_id,
        ranked_score=stats.ranked_score,
        accuracy=stats.accuracy / 100,
        playcount=stats.playcount,
        total_score=stats.total_score,
        pp=stats.pp,
        global_rank=stats.global_rank,
    )
    return new_token


async def enqueue(
    ctx: Context,
    token_id: str,
    data: bytes,
) -> None:
    repo = TokensRepository(ctx)

    json_data = list(data)
    await repo.enqueue(token_id, json_data)


async def dequeue(
    ctx: Context,
    token_id: str,
) -> bytes:
    repo = TokensRepository(ctx)

    buffers = await repo.dequeue(token_id)
    return b"".join(bytes(orjson.loads(buffer["buffer"])) for buffer in buffers)


async def join_stream(
    ctx: Context,
    token_id: str,
    stream_name: str,
) -> None:
    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    stream = await streams_usecases.fetch_one(
        ctx,
        stream_name,
    )
    if stream is None:
        assert stream_name is not None
        stream = await streams_usecases.create_one(ctx, stream_name)

    await streams_usecases.add_client(ctx, stream_name, token_id)


async def leave_stream(
    ctx: Context,
    token_id: str,
    stream_name: str,
) -> None:
    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    stream = await streams_usecases.fetch_one(
        ctx,
        stream_name,
    )
    assert stream is not None

    await streams_usecases.remove_client(ctx, stream_name, token_id)


async def enqueue_message(
    ctx: Context,
    token_id: str,
    message: str,
    sender_token_id: str,
) -> None:
    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    sender = await fetch_one(ctx, token_id=sender_token_id)
    if sender is None:
        return

    packet = serial.write_send_message_packet(
        sender.username,
        message,
        token.username,
        sender.user_id,
    )
    await enqueue(ctx, token_id, packet)


async def enqueue_bot_message(
    ctx: Context,
    token_id: str,
    message: str,
) -> None:
    bot = await fetch_one(ctx, user_id=999)
    assert bot is not None

    await enqueue_message(ctx, token_id, message, bot.token_id)


RESTRICTED_MSG = "Your account is currently in restricted mode. Please visit Akatsuki's website for more information."
UNRESTRICTED_MSG = "Your account has been unrestricted! Please log in again."


async def check_restricted(
    ctx: Context,
    token_id: str,
    user_id: int,
    current_privileges: int,
) -> None:
    old_restricted = current_privileges & Privileges.USER_PUBLIC == 0

    user = await users_usecases.fetch_one(ctx, id=user_id)
    assert user is not None

    restricted = users_usecases.is_restricted(user.privileges)
    if not restricted and not old_restricted:
        return

    message = RESTRICTED_MSG if restricted else UNRESTRICTED_MSG
    await enqueue_bot_message(ctx, token_id, message)


async def enqueue_notification(
    ctx: Context,
    token_id: str,
    message: str,
) -> None:
    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    packet = serial.write_notification_packet(message)
    await enqueue(ctx, token_id, packet)


def get_remaining_silence_seconds(silence_end_time: int) -> int:
    return max(0, silence_end_time - int(time.time()))


async def join_channel(
    ctx: Context,
    token_id: str,
    channel_name: str,
) -> None:
    # private messages
    if not channel_name.startswith("#"):
        return

    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    channel = await channels_usecases.fetch_one(ctx, channel_name)
    assert channel is not None

    joined_channels = [
        client["channel_name"]
        for client in await channels_usecases.fetch_clients(ctx, token_id=token_id)
    ]
    if channel_name in joined_channels:
        return

    if (
        (channel_name == "#premium" and not token.privileges & Privileges.USER_PREMIUM)
        or (
            channel_name == "#supporter"
            and not token.privileges & Privileges.USER_DONOR
        )
        or (not channel.public_read and not users_usecases.is_staff(token.privileges))
    ) and token.user_id != 999:
        return

    await join_stream(ctx, token_id, f"chat/{channel_name}")

    client_name = channels_usecases.get_client_name(channel_name)
    await enqueue(
        ctx,
        token_id,
        serial.write_channel_join_success_packet(client_name),
    )


async def leave_channel(
    ctx: Context,
    token_id: str,
    channel_name: str,
    kick: bool = False,
) -> None:
    # private messages
    if not channel_name.startswith("#"):
        return

    token = await fetch_one(ctx, token_id=token_id)
    assert token is not None

    client_channel = channel_name
    if channel_name == "#spectator":
        if token.spectating_user_id is None:
            user_id = token.user_id
        else:
            user_id = token.spectating_user_id

        channel_name = f"#spect_{user_id}"
    elif channel_name == "#multiplayer":
        channel_name = f"#multi_{token.match_id}"
    elif channel_name.startswith("#spect_"):
        client_channel = "#spectator"
    elif channel_name.startswith("#multi_"):
        client_channel = "#multiplayer"

    channel = await channels_usecases.fetch_one(ctx, channel_name)
    assert channel is not None

    channel_clients = await channels_usecases.fetch_clients(
        ctx,
        channel_name=channel_name,
    )
    if token_id not in channel_clients:
        return

    stream = await streams_usecases.fetch_one(ctx, f"chat/{channel_name}")
    assert stream is not None

    await channels_usecases.remove_client(ctx, channel_name, token_id)

    stream_clients = await streams_usecases.fetch_clients(ctx, f"chat/{channel_name}")
    if token_id not in stream_clients:
        new_stream_count = len(stream_clients)
    else:
        new_stream_count = len(stream_clients) - 1

    if channel.instance and new_stream_count == 0:
        await channels_usecases.delete_one(ctx, channel_name)
    else:
        await streams_usecases.remove_client(ctx, f"chat/{channel_name}", token_id)

    if kick:
        await enqueue(
            ctx,
            token_id,
            serial.write_channel_kick_packet(client_channel),
        )

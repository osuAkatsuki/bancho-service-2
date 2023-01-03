from fastapi import APIRouter
from fastapi import Request
from fastapi import Response
from fastapi import Depends
from datetime import datetime
from datetime import timedelta

from app.common.context import Context
from app.usecases import login as login_usecases
from app.usecases import users as users_usecases
from app.usecases import tokens as tokens_usecases
from app.usecases import cryptography as cryptography_usecases
from app.usecases import geolocation as geolocation_usecases
from app.usecases import logging as logging_usecases
from app.usecases import channels as channels_usecases
from app.usecases import streams as streams_usecases
from app.common import serial
from app.common import logger
from app.common import settings
from app.models.privileges import Privileges

import time
import re

router = APIRouter()

CLIENT_REGEX = re.compile(
    r"^b(?P<ver>\d{8})(?:\.(?P<subver>\d))?"
    r"(?P<stream>beta|cuttingedge|dev|tourney)?$",
)


def success_response(content: bytes, token: str) -> Response:
    return Response(content=content, headers={"cho-token": token}, status_code=200)


def failure_response(content: bytes) -> Response:
    return Response(content=content, headers={"cho-token": "no"}, status_code=200)


async def handle_packet_request(request: Request, ctx: Context) -> Response:
    token = await tokens_usecases.fetch_one(ctx, token_id=request.headers["osu-token"])
    if token is None:
        return success_response(b"", request.headers["osu-token"])

    packet_data = await tokens_usecases.dequeue(ctx, token.token_id)
    return success_response(packet_data, token.token_id)


@router.post("/")
async def bancho_endpoint(request: Request, ctx: Context = Depends()):
    request_body = await request.body()

    if "osu-token" in request.headers:
        return await handle_packet_request(request, ctx)

    login_data = login_usecases.parse_login_data(request_body)
    user = await users_usecases.fetch_one(ctx, username=login_data.username)
    if user is None:
        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "Akatsuki: You have entered an invalid username or password. Please check your credentials and try again!"
            )
        )

    # login attempt as bot?
    if user.id == 999:
        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "Akatsuki: Something went wrong during your login attempt... Please try again!"
            )
        )

    correct_password = await cryptography_usecases.verify_bcrypt_password(
        ctx,
        password_md5=login_data.password_md5,
        bcrypt_hash=user.password_md5,
    )
    if not correct_password:
        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "Akatsuki: You have entered an invalid username or password. Please check your credentials and try again!"
            )
        )

    pending_verification = user.privileges & Privileges.USER_PENDING_VERIFICATION != 0
    if not pending_verification:
        # user is banned
        if not user.privileges & (Privileges.USER_PUBLIC | Privileges.USER_NORMAL):
            return failure_response(
                serial.write_account_id_packet(-1)
                + serial.write_notification_packet(
                    (
                        "You are banned. The earliest we accept appeals is 2 months after your most recent offense, "
                        "and we really only care for the truth."
                    )
                )
            )

        # user is locked
        if (
            user.privileges & Privileges.USER_PUBLIC
            and not user.privileges & Privileges.USER_NORMAL
        ):
            return failure_response(
                serial.write_account_id_packet(-1)
                + serial.write_notification_packet(
                    (
                        "Your account is locked. You can't log in, but your "
                        "profile and scores are still visible from the website. "
                        "The earliest we accept appeals is 2 months after your "
                        "most recent offense, and really only care for the truth."
                    )
                )
            )

    osu_version_regex = CLIENT_REGEX.match(login_data.osu_version)
    if osu_version_regex is None:
        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "Akatsuki: Something went wrong during your login attempt... Please try again!"
            )
        )

    client_version_date = datetime(
        year=int(osu_version_regex["ver"][:4]),
        month=int(osu_version_regex["ver"][4:6]),
        day=int(osu_version_regex["ver"][6:8]),
    )
    if client_version_date < (datetime.now() - timedelta(days=365)):
        logger.warning(
            "Denied login from outdated client",
            username=user.username,
            osu_version=login_data.osu_version,
        )

        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "\n".join(
                    [
                        "Hey!",
                        "The osu! client you're trying to use is out of date.",
                        "Custom/out of date osu! clients are not allowed on Akatsuki.",
                        "Please relogin using the current osu! client - no fallback, sorry!",
                    ]
                )
            )
        )

    ip = geolocation_usecases.retrieve_ip_from_headers(request.headers) or "some_ip"
    if ip is None:
        logger.warning("Denied login from unknown IP", username=user.username)
        return failure_response(
            serial.write_account_id_packet(-1)
            + serial.write_notification_packet(
                "Akatsuki: Something went wrong during your login attempt... Please try again!"
            )
        )

    # TODO: hardware logging
    first_login = pending_verification

    await users_usecases.log_ip(ctx, user.id, ip)

    using_tournament_client = osu_version_regex["stream"] == "tourney"
    async with await ctx.lock_manager.lock("akatsuki:locks:tokens"):
        if not using_tournament_client:
            # check if user is already logged in somewhere else
            # if so, send failure
            connected_clients = await tokens_usecases.fetch_all(ctx, user_id=user.id)
            if connected_clients:
                return failure_response(
                    serial.write_account_id_packet(-1)
                    + serial.write_notification_packet(
                        "Akatsuki: You are already logged in somewhere else!"
                    )
                )

        token = await tokens_usecases.create_one(
            ctx,
            user.id,
            user.username,
            user.privileges,
            user.whitelist,
            user.silence_end,
            ip,
            login_data.utc_offset,
            using_tournament_client,
            login_data.pm_private,
        )

    logger.info("Successful login", username=user.username, ip=ip)

    await tokens_usecases.check_restricted(
        ctx,
        token.token_id,
        token.user_id,
        token.privileges,
    )

    response_data = bytearray()

    current_time = int(time.time())

    if user.frozen:
        if user.frozen == 1:
            user.frozen = await users_usecases.begin_freeze_timer(ctx, user.id)

        freeze_str = (
            f" as a result of:\n\n{user.freeze_reason}\n" if user.freeze_reason else ""
        )

        if user.frozen > current_time:
            # warn them, time is not over yet

            message = "\n".join(
                [
                    f"Your account has been frozen by an administrator{freeze_str}",
                    "This is not a restriction, but will lead to one if ignored.",
                    "You are required to submit a liveplay using the (specified criteria)[https://pastebin.com/BwcXp6Cr]",
                    "Please remember we are not stupid - we have done plenty of these before and have heard every excuse in the book; if you are breaking rules, your best bet would be to admit to a staff member, lying will only end up digging your grave deeper.",
                    "-------------",
                    "If you have any questions or are ready to liveplay, please contact an (Akatsuki Administrator)[https://akatsuki.pw/team] {ingame, (Discord)[https://akatsuki.pw/discord], etc.}",
                    f"Time until account restriction: {timedelta(seconds=user.frozen - current_time)}.",
                ],
            )

            bot = await users_usecases.fetch_one(ctx, id=999)
            assert bot is not None

            response_data += serial.write_send_message_packet(
                bot.username,
                message,
                token.username,
                bot.id,
            )
        else:
            # timer is up, restrict !!!!

            user.privileges = token.privileges = await users_usecases.restrict(
                ctx,
                user.id,
                user.privileges,
            )

            await users_usecases.unfreeze(ctx, user.id, log=False)
            user.frozen = 0

            notification = "\n".join(
                [
                    "Your account has been automatically restricted due to an account freeze being left unhandled for over 7 days.",
                    "You are still welcome to liveplay, although your account will remain in restricted mode unless this is handled.",
                ]
            )
            response_data += serial.write_notification_packet(notification)

            await logging_usecases.rap(
                ctx,
                user.id,
                "has been automatically restricted due to a pending freeze.",
            )

            await logging_usecases.anticheat(
                f"[{user.username}](https://akatsuki.pw/u/{user.id}) has been automatically restricted due to a pending freeze.",
                "ac_general",
            )

    if user.privileges & Privileges.USER_DONOR:
        has_premium = user.privileges & Privileges.USER_PREMIUM
        role_name = "premium" if has_premium else "supporter"

        if current_time >= user.donor_expire:
            user.privileges = (
                token.privileges
            ) = await users_usecases.revoke_supporter_privileges(
                ctx,
                user.id,
                user.privileges,
            )

            response_data += serial.write_notification_packet(
                "\n".join(
                    [
                        f"Your {role_name} tag has expired.",
                        "Whether you continue to support us or not, we'd like to thank you "
                        "to the moon and back for your support so far - it really means everything to us.",
                        "- cmyui, and the Akatsuki Team",
                    ],
                ),
            )
        elif user.donor_expire - current_time <= 86_400 * 7:
            # <= 7 days left, notify them
            expires_in = timedelta(seconds=user.donor_expire - current_time)

            response_data += serial.write_notification_packet(
                f"Your {role_name} tag will expire in {str(expires_in):0>8}",
            )

    silence_seconds = tokens_usecases.get_remaining_silence_seconds(
        token.silence_end_time
    )
    user_restricted = users_usecases.is_restricted(token.privileges)
    user_gmt = users_usecases.is_staff(token.privileges)
    user_tournament = users_usecases.is_tournament_staff(token.privileges)

    if token.privileges & Privileges.USER_DONOR:
        # if donor, use their website flag
        country = await users_usecases.fetch_country(ctx, user.id)
        longitude = 0.0
        latitude = 0.0
    else:
        geolocation = geolocation_usecases.fetch_geolocation_from_ip(ctx, ip)

        country = geolocation["country_acronym"]
        longitude = geolocation["longitude"]
        latitude = geolocation["latitude"]

    token.country = users_usecases.fetch_country_id(country)
    token.longitude = longitude
    token.latitude = latitude

    # TODO: restart check?

    if settings.LOGIN_NOTIFICATION:
        response_data += serial.write_notification_packet(settings.LOGIN_NOTIFICATION)

    if settings.MAINTENANCE_MODE:
        if not user_gmt:
            await tokens_usecases.delete_one(ctx, token.token_id)
            return failure_response(
                response_data
                + serial.write_account_id_packet(-1)
                + serial.write_notification_packet(
                    "Akatsuki is currently in maintenance mode. Please try to login again later."
                )
            )
        else:
            response_data += serial.write_notification_packet(
                "Akatsuki is currently in maintenance mode. Only admins have full access to the server.\n"
                "Type '!system maintenance off' in chat to disable maintenance mode."
            )

    response_data += serial.write_protocol_version_packet(19)
    response_data += serial.write_account_id_packet(user.id)
    response_data += serial.write_silence_end_packet(silence_seconds)

    client_privileges = 1
    if not user_restricted:
        # "supporter"
        client_privileges |= 4

    if user_gmt:
        # "BAT"
        client_privileges |= 2

    if user_tournament:
        client_privileges |= 32

    response_data += serial.write_privileges_packet(client_privileges)
    response_data += serial.write_user_presence_packet(
        user.id,
        user.username,
        token.utc_offset,
        token.country,
        client_privileges,
        token.mode,
        token.latitude,
        token.longitude,
        token.global_rank,
    )
    response_data += serial.write_user_stats_packet(
        user.id,
        token.action_id,
        token.action_text,
        token.action_md5,
        token.action_mods,
        token.mode,
        token.action_beatmap_id,
        token.ranked_score,
        token.accuracy,
        token.playcount,
        token.total_score,
        token.global_rank,
        token.pp,
    )

    await tokens_usecases.join_channel(ctx, token.token_id, channel_name="#osu")
    await tokens_usecases.join_channel(ctx, token.token_id, channel_name="#announce")

    # join default channels
    for channel in await channels_usecases.fetch_all(ctx):
        if channel.public_read and not channel.instance:
            client_count = len(
                await streams_usecases.fetch_clients(ctx, f"chat/{channel.name}")
            )
            response_data += serial.write_channel_info_packet(
                channel.name, channel.description, client_count
            )

    response_data += serial.write_channel_info_end_packet()

    friends = await users_usecases.fetch_friends(ctx, user.id)
    response_data += serial.write_friends_list_packet(friends)

    if settings.MAIN_MENU_ICON_URL and settings.MAIN_MENU_ON_CLICK_URL:
        response_data += serial.write_main_menu_icon_packet(
            settings.MAIN_MENU_ICON_URL,
            settings.MAIN_MENU_ON_CLICK_URL,
        )

    async with await ctx.lock_manager.lock("akatsuki:locks:tokens"):
        for user_token in await tokens_usecases.fetch_all(ctx):
            if users_usecases.is_restricted(user_token.privileges):
                continue

            client_privileges = 1 | 4

            user_token_gmt = users_usecases.is_staff(user_token.privileges)
            user_token_tournament = users_usecases.is_tournament_staff(
                user_token.privileges
            )

            if user_token_gmt:
                # "BAT"
                client_privileges |= 2

            if user_token_tournament:
                client_privileges |= 32

            response_data += serial.write_user_presence_packet(
                user_token.user_id,
                user_token.username,
                user_token.utc_offset,
                user_token.country,
                client_privileges,
                user_token.mode,
                user_token.latitude,
                user_token.longitude,
                user_token.global_rank,
            )

    if not user_restricted:
        await streams_usecases.broadcast(
            ctx,
            "main",
            serial.write_user_presence_packet(
                user.id,
                user.username,
                token.utc_offset,
                token.country,
                client_privileges,
                token.mode,
                token.latitude,
                token.longitude,
                token.global_rank,
            ),
        )

    return success_response(bytes(response_data), token.token_id)

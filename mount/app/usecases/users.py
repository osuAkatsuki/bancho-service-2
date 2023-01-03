from app.repositories.users import UsersRepository
from app.common.context import Context
from app.models.user import User
from app.models.privileges import Privileges
from app.usecases import logging as logging_usecases
from typing import Any

import time


async def fetch_one(
    ctx: Context,
    id: int | None = None,
    username: str | None = None,
) -> User | None:
    repo = UsersRepository(ctx)

    user = await repo.fetch_one(id, username)
    if user is None:
        return None

    return User.parse_obj(user)


async def partial_update(ctx: Context, id: int, **updates: Any) -> User:
    repo = UsersRepository(ctx)
    new_user = await repo.partial_update(id, **updates)

    return User.parse_obj(new_user)


async def log_ip(ctx: Context, user_id: int, ip: str) -> None:
    query = """\
        INSERT INTO ip_user (userid, ip, occurencies)
        VALUES (:user_id, :ip, 1)
        ON DUPLICATE KEY UPDATE
            occurencies = occurencies + 1
    """
    params = {
        "user_id": user_id,
        "ip": ip,
    }

    await ctx.database.execute(query, params)


def is_restricted(privileges: int) -> bool:
    return privileges & Privileges.USER_PUBLIC == 0


def is_staff(privileges: int) -> bool:
    return privileges & Privileges.ADMIN_CHAT_MOD != 0


def is_tournament_staff(privileges: int) -> bool:
    return privileges & Privileges.USER_TOURNAMENT_STAFF != 0


async def begin_freeze_timer(ctx: Context, user_id: int) -> int:
    restriction_time = int(time.time() + (86_400 * 7))

    await partial_update(ctx, user_id, frozen=restriction_time)
    return restriction_time


async def fetch_country(ctx: Context, user_id: int) -> str:
    stats_row = await ctx.database.fetch_one(
        "SELECT country FROM users_stats WHERE id = :user_id", {"user_id": user_id}
    )
    assert stats_row is not None

    return stats_row["country"]


async def remove_from_leaderboard(ctx: Context, user_id: int) -> None:
    user = await fetch_one(ctx, id=user_id)
    assert user is not None

    country = (await fetch_country(ctx, user_id)).lower()
    for board in ("leaderboard", "relaxboard", "autoboard"):
        for mode in ("std", "taiko", "ctb", "mania"):
            await ctx.redis.zrem(f"ripple:{board}:{mode}", str(user.id))

            if country and country != "xx":
                await ctx.redis.zrem(f"ripple:{board}:{mode}:{country}", str(user.id))


async def restrict(ctx: Context, user_id: int, current_privileges: int) -> int:
    # already restricted
    if current_privileges & Privileges.USER_PUBLIC == 0:
        return current_privileges

    user = await partial_update(
        ctx,
        user_id,
        privileges=current_privileges & ~Privileges.USER_PUBLIC,
    )

    await ctx.redis.publish("peppy:ban", user_id)
    await remove_from_leaderboard(ctx, user_id)

    return user.privileges


async def append_notes(
    ctx: Context,
    user_id: int,
    note: str,
    track_date: bool = True,
    add_newline: bool = True,
) -> str:
    if track_date:
        note = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] {note}"

    if add_newline:
        note = f"\n{note}"

    user = await fetch_one(ctx, id=user_id)
    assert user is not None

    user = await partial_update(
        ctx,
        user_id,
        notes=(user.notes or "") + note,
    )
    assert user.notes is not None

    return user.notes


async def unfreeze(
    ctx: Context,
    user_id: int,
    author_id: int = 999,
    log: bool = True,
) -> None:
    await partial_update(ctx, user_id, frozen=0, freeze_reason="")

    if not log:
        return

    author = await fetch_one(ctx, id=author_id)
    assert author is not None

    user = await fetch_one(ctx, id=user_id)
    assert user is not None

    await append_notes(
        ctx,
        user_id,
        f"{author.username} ({author_id}) unfroze this user.",
    )

    await logging_usecases.rap(
        ctx,
        author.id,
        f"unfroze {user.username} ({user.id}).",
    )

    await logging_usecases.anticheat(
        f"{author.username} has unfrozen [{user.username}](https://akatsuki.pw/u/{user.id})",
        "ac_general",
    )


async def revoke_supporter_privileges(
    ctx: Context,
    user_id: int,
    current_privileges: int,
) -> int:
    has_premium = current_privileges & Privileges.USER_PREMIUM
    role_name = "premium" if has_premium else "supporter"

    user = await partial_update(
        ctx,
        user_id,
        privileges=current_privileges - Privileges.USER_DONOR
        | (Privileges.USER_PREMIUM if has_premium else 0),
    )

    # 36 = supporter, 59 = premium
    query = """\
        DELETE FROM user_badges
        WHERE
          badge IN (36, 59)
          AND user = :user_id
    """
    params = {
        "user_id": user.id,
    }
    await ctx.database.execute(query, params)

    query = """\
        UPDATE users_stats
        SET
          can_custom_badge = 0,
          show_custom_badge = 0
        WHERE
          id = :user_id
    """
    params = {
        "user_id": user.id,
    }
    await ctx.database.execute(query, params)

    await logging_usecases.anticheat(
        f"[{user.username}](https://akatsuki.pw/u/{user.id})'s {role_name} subscription has expired.",
        "ac_confidental",
    )
    await logging_usecases.rap(ctx, user.id, f"{role_name} subscription expired.")

    return user.privileges


async def fetch_friends(ctx: Context, user_id: int) -> list[int]:
    query = """\
        SELECT
          user2
        FROM
          users_relationships
        WHERE
          user1 = :user_id
    """
    params = {
        "user_id": user_id,
    }

    rows = await ctx.database.fetch_all(query, params)
    return [row["user2"] for row in rows]


# fmt: off
country_codes = {
    "oc": 1,   "eu": 2,   "ad": 3,   "ae": 4,   "af": 5,   "ag": 6,   "ai": 7,   "al": 8,
    "am": 9,   "an": 10,  "ao": 11,  "aq": 12,  "ar": 13,  "as": 14,  "at": 15,  "au": 16,
    "aw": 17,  "az": 18,  "ba": 19,  "bb": 20,  "bd": 21,  "be": 22,  "bf": 23,  "bg": 24,
    "bh": 25,  "bi": 26,  "bj": 27,  "bm": 28,  "bn": 29,  "bo": 30,  "br": 31,  "bs": 32,
    "bt": 33,  "bv": 34,  "bw": 35,  "by": 36,  "bz": 37,  "ca": 38,  "cc": 39,  "cd": 40,
    "cf": 41,  "cg": 42,  "ch": 43,  "ci": 44,  "ck": 45,  "cl": 46,  "cm": 47,  "cn": 48,
    "co": 49,  "cr": 50,  "cu": 51,  "cv": 52,  "cx": 53,  "cy": 54,  "cz": 55,  "de": 56,
    "dj": 57,  "dk": 58,  "dm": 59,  "do": 60,  "dz": 61,  "ec": 62,  "ee": 63,  "eg": 64,
    "eh": 65,  "er": 66,  "es": 67,  "et": 68,  "fi": 69,  "fj": 70,  "fk": 71,  "fm": 72,
    "fo": 73,  "fr": 74,  "fx": 75,  "ga": 76,  "gb": 77,  "gd": 78,  "ge": 79,  "gf": 80,
    "gh": 81,  "gi": 82,  "gl": 83,  "gm": 84,  "gn": 85,  "gp": 86,  "gq": 87,  "gr": 88,
    "gs": 89,  "gt": 90,  "gu": 91,  "gw": 92,  "gy": 93,  "hk": 94,  "hm": 95,  "hn": 96,
    "hr": 97,  "ht": 98,  "hu": 99,  "id": 100, "ie": 101, "il": 102, "in": 103, "io": 104,
    "iq": 105, "ir": 106, "is": 107, "it": 108, "jm": 109, "jo": 110, "jp": 111, "ke": 112,
    "kg": 113, "kh": 114, "ki": 115, "km": 116, "kn": 117, "kp": 118, "kr": 119, "kw": 120,
    "ky": 121, "kz": 122, "la": 123, "lb": 124, "lc": 125, "li": 126, "lk": 127, "lr": 128,
    "ls": 129, "lt": 130, "lu": 131, "lv": 132, "ly": 133, "ma": 134, "mc": 135, "md": 136,
    "mg": 137, "mh": 138, "mk": 139, "ml": 140, "mm": 141, "mn": 142, "mo": 143, "mp": 144,
    "mq": 145, "mr": 146, "ms": 147, "mt": 148, "mu": 149, "mv": 150, "mw": 151, "mx": 152,
    "my": 153, "mz": 154, "na": 155, "nc": 156, "ne": 157, "nf": 158, "ng": 159, "ni": 160,
    "nl": 161, "no": 162, "np": 163, "nr": 164, "nu": 165, "nz": 166, "om": 167, "pa": 168,
    "pe": 169, "pf": 170, "pg": 171, "ph": 172, "pk": 173, "pl": 174, "pm": 175, "pn": 176,
    "pr": 177, "ps": 178, "pt": 179, "pw": 180, "py": 181, "qa": 182, "re": 183, "ro": 184,
    "ru": 185, "rw": 186, "sa": 187, "sb": 188, "sc": 189, "sd": 190, "se": 191, "sg": 192,
    "sh": 193, "si": 194, "sj": 195, "sk": 196, "sl": 197, "sm": 198, "sn": 199, "so": 200,
    "sr": 201, "st": 202, "sv": 203, "sy": 204, "sz": 205, "tc": 206, "td": 207, "tf": 208,
    "tg": 209, "th": 210, "tj": 211, "tk": 212, "tm": 213, "tn": 214, "to": 215, "tl": 216,
    "tr": 217, "tt": 218, "tv": 219, "tw": 220, "tz": 221, "ua": 222, "ug": 223, "um": 224,
    "us": 225, "uy": 226, "uz": 227, "va": 228, "vc": 229, "ve": 230, "vg": 231, "vi": 232,
    "vn": 233, "vu": 234, "wf": 235, "ws": 236, "ye": 237, "yt": 238, "rs": 239, "za": 240,
    "zm": 241, "me": 242, "zw": 243, "xx": 244, "a2": 245, "o1": 246, "ax": 247, "gg": 248,
    "im": 249, "je": 250, "bl": 251, "mf": 252,
}
# fmt: on


def fetch_country_id(country_code: str) -> int:
    return country_codes.get(country_code.lower(), 0)

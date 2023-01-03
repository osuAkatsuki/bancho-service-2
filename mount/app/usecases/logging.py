from app.common import logger
from app.common import settings
from app.models.discord import Webhook
from app.models.discord import Embed
from app.common.context import Context

MAX_DISCORD_WEBHOOK_RETRIES = 5


async def send_discord_webhook(message: str, webhook_url: str) -> None:
    if not webhook_url:
        return

    webhook = Webhook(url=webhook_url)

    embed = Embed(color=0x542CB8)
    embed.add_field(name="** **", value=message)
    embed.set_footer(text=f"Akatsuki Anticheat")
    embed.set_thumbnail(url="https://akatsuki.pw/static/logos/logo.png")
    webhook.add_embed(embed)

    for _ in range(MAX_DISCORD_WEBHOOK_RETRIES):
        try:
            await webhook.post()
            break
        except Exception:
            continue


async def anticheat(message: str, discord_channel: str | None = None) -> None:
    logger.warning(f"ANTICHEAT: {message}")

    if discord_channel:
        if discord_channel == "ac_general":
            channel = settings.DISCORD_GENERAL_ANTICHEAT_WEBHOOK
        elif discord_channel == "ac_confidental":
            channel = settings.DISCORD_CONFIDENTIAL_ANTICHEAT_WEBHOOK
        else:
            raise ValueError(f"Invalid anticheat channel: {discord_channel}")

        await send_discord_webhook(message, channel)


async def rap(
    ctx: Context,
    user_id: int,
    message: str,
    discord_channel: str | None = None,
    admin: str = "Aika",
) -> None:
    query = """\
        INSERT INTO rap_logs (id, userid, text, datetime, through)
        VALUES (NULL, :user_id, :message, UNIX_TIMESTAMP(), :admin)
    """
    params = {
        "user_id": user_id,
        "message": message,
        "admin": admin,
    }

    await ctx.database.execute(query, params)

    if discord_channel:
        await send_discord_webhook(message, discord_channel)

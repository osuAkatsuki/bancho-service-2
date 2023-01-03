from app.models.redis_cache import RedisCache
from app.common import logger
from app.common import settings

from fastapi import FastAPI
from asyncql import Database
from app.common.aioredlock import Aioredlock
from app.usecases import users as users_usecases
from app.usecases import tokens as tokens_usecases
from app.usecases import channels as channels_usecases
from app.common.context import Context
from geoip2.database import Reader

import aioredis


def mysql_dsn(username: str, password: str, host: str, port: int, database: str) -> str:
    return f"mysql://{username}:{password}@{host}:{port}/{database}"


def init_db(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_database() -> None:
        logger.info("Connecting to database")

        database = Database(
            mysql_dsn(
                username=settings.DB_USER,
                password=settings.DB_PASS,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                database=settings.DB_NAME,
            )
        )
        await database.connect()

        app.state.database = database
        logger.info("Connected to database")

    @app.on_event("shutdown")
    async def shutdown_database() -> None:
        logger.info("Disconnecting from database")

        await app.state.database.disconnect()
        del app.state.database

        logger.info("Disconnected from database")


class ContextProxy(Context):
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    @property
    def database(self) -> Database:
        return self.app.state.database

    @property
    def redis(self) -> aioredis.Redis:
        return self.app.state.redis

    @property
    def bcrypt_cache(self) -> RedisCache[str]:
        return self.app.state.bcrypt_cache

    @property
    def lock_manager(self) -> Aioredlock:
        return self.app.state.lock_manager

    @property
    def geolocation_reader(self) -> Reader:
        return self.app.state.geolocation_reader


async def instantiate_channels(app: FastAPI) -> None:
    ctx = ContextProxy(app)

    bancho_channels = await ctx.database.fetch_all("SELECT * FROM bancho_channels")
    for bancho_channel in bancho_channels:
        channel = await channels_usecases.fetch_one(
            ctx,
            channel_name=bancho_channel["name"],
        )
        if channel is not None:
            continue

        await channels_usecases.create_one(
            ctx,
            bancho_channel["name"],
            bancho_channel["description"],
            bancho_channel["public_read"],
            bancho_channel["public_write"],
            False,  # moderated
            bancho_channel["temp"],
        )


async def connect_aika(app: FastAPI) -> None:
    ctx = ContextProxy(app)

    aika = await tokens_usecases.fetch_one(ctx, user_id=999)
    if aika is not None:
        return

    bot_user = await users_usecases.fetch_one(ctx, id=999)
    assert bot_user is not None

    await tokens_usecases.create_one(
        ctx,
        user_id=bot_user.id,
        username=bot_user.username,
        privileges=bot_user.privileges,
        whitelist=bot_user.whitelist,
        silence_end_time=bot_user.silence_end,
        ip="",
        utc_offset=24,
        tournament=False,
        block_non_friends_dm=False,
    )


def init_redis(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_redis() -> None:
        logger.info("Connecting to redis")

        redis = aioredis.StrictRedis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
        )
        await redis.initialize()

        app.state.redis = redis
        logger.info("Connected to redis")

        await connect_aika(app)
        await instantiate_channels(app)

    @app.on_event("shutdown")
    async def shutdown_redis() -> None:
        logger.info("Disconnecting from redis")

        await app.state.redis.close()
        del app.state.redis

        logger.info("Disconnected from redis")


def init_bcrypt_cache(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_bcrypt_cache() -> None:
        logger.info("Initializing bcrypt cache")

        bcrypt_cache: RedisCache[str] = RedisCache(
            app.state.redis, "akatsuki:cache:bcrypt"
        )
        app.state.bcrypt_cache = bcrypt_cache

        logger.info("Initialized bcrypt cache")

    @app.on_event("shutdown")
    async def shutdown_bcrypt_cache() -> None:
        logger.info("Destroying bcrypt cache")

        del app.state.bcrypt_cache

        logger.info("Destroyed bcrypt cache")


def init_lock_manager(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_lock_manager() -> None:
        logger.info("Initializing lock manager")

        lock_manager = Aioredlock([app.state.redis])  # type: ignore
        app.state.lock_manager = lock_manager

        logger.info("Initialized lock manager")

    @app.on_event("shutdown")
    async def shutdown_lock_manager() -> None:
        logger.info("Destroying lock manager")

        del app.state.lock_manager

        logger.info("Destroyed lock manager")


def init_geolocation_reader(app: FastAPI) -> None:
    @app.on_event("startup")
    async def startup_geolocation_reader() -> None:
        logger.info("Initializing geolocation reader")

        geolocation_reader = Reader(settings.GEOLOCATION_DB_PATH)
        app.state.geolocation_reader = geolocation_reader

        logger.info("Initialized geolocation reader")


def init_routes(app: FastAPI) -> None:
    from . import bancho

    app.include_router(bancho.router)


def init_api() -> FastAPI:
    app = FastAPI()

    init_db(app)
    init_redis(app)
    init_bcrypt_cache(app)
    init_lock_manager(app)
    init_geolocation_reader(app)
    init_routes(app)

    return app

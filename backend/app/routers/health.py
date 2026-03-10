import redis.asyncio as aioredis
from fastapi import APIRouter
from neo4j import AsyncGraphDatabase
from sqlalchemy import text

from app.config import settings
from app.db.database import async_session_factory
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


async def _check_database() -> str:
    """Check PostgreSQL connectivity."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        return f"error: {e}"


async def _check_redis() -> str:
    """Check Redis connectivity."""
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        return "connected"
    except Exception as e:
        return f"error: {e}"


async def _check_neo4j() -> str:
    """Check Neo4j connectivity."""
    try:
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        return "connected"
    except Exception as e:
        return f"error: {e}"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health of all services."""
    db_status = await _check_database()
    redis_status = await _check_redis()
    neo4j_status = await _check_neo4j()

    all_healthy = all(
        s == "connected" for s in [db_status, redis_status, neo4j_status]
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        environment=settings.ENVIRONMENT,
        database=db_status,
        redis=redis_status,
        neo4j=neo4j_status,
    )

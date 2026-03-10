from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    redis: str
    neo4j: str


class ServiceStatus(BaseModel):
    status: str
    detail: str | None = None

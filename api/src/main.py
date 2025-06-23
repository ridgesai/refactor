from fastapi import FastAPI

from src.endpoints.upload import router as upload_router
from src.endpoints.retrieval import router as retrieval_router
from src.endpoints.agents import router as agents_router

app = FastAPI()

# Include ingestion routes
app.include_router(
    upload_router,
    prefix="/upload",
)

app.include_router(
    retrieval_router,
    prefix="/retrieval",
)

app.include_router(
    agents_router,
    prefix="/agents",
)

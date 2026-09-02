"""FastAPI application entrypoint.

This service is both tiers of the proposal's middle: it is the inference
microservice *and* the record-management API. The proposal (Section 3.7) put a
.NET 8 Web API between the Angular client and a FastAPI inference service;
collapsing them removes a network hop and a language boundary while keeping the
inference code isolated behind `app.ml.Predictor`, which is what the
architectural argument in Section 2.6 (Sculley et al., 2015) actually turns on.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.ml import get_predictor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    predictor = get_predictor()
    if not predictor.is_real:
        logger.warning(
            "Running with the %s backend - predictions are placeholders, not evidence.",
            predictor.name,
        )
    else:
        logger.info("Inference backend ready: %s (%s)", predictor.name, predictor.model_name)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Automated pre- and post-rental passenger car damage inspection.\n\n"
        "Deep-learning damage classification, inspection record management, "
        "pre/post comparison and evidentiary PDF reporting."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }

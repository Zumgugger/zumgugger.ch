"""Health check endpoint."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, check_db_connection, get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Health check endpoint.
    
    Returns:
        JSON with status and database connection info.
        
    Responses:
        200: Service is healthy and database is connected
        503: Service is unhealthy (database connection failed)
    """
    db_connected = check_db_connection()
    
    if db_connected:
        return {
            "status": "ok",
            "db": "connected",
        }
    else:
        # Return 503 Service Unavailable if DB is down
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "db": "disconnected",
            }
        )

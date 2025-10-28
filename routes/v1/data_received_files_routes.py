"""
Purpose: FastAPI router for Data Received Files endpoints.
Provides dedicated API for file-level operations.

Separate router for API clarity, uses DataReceivedFilesService.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body
from typing import Optional, List
from datetime import datetime
import traceback

from models.data_received_files_models import (
    DataReceivedFileResponseSchema,
    FileWithPipelineDetailsSchema,
)
from services.data_received_files_service import (
    DataReceivedFilesService,
    FileNotFoundError,
    DatabaseOperationError,
)
from utils.validators import PyObjectId
from constants.value_sets import MatchingStatus


router = APIRouter(
    prefix="/api/v1/files",
    tags=["Data Received Files"],
)

service = DataReceivedFilesService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """Get current authenticated user ID."""
    return PyObjectId("6710000000000000000000a2")


# ========== GET FILE BY ID ==========
@router.get(
    "/{file_id}",
    response_model=DataReceivedFileResponseSchema,
    summary="Get File by ID"
)
async def get_file(file_id: PyObjectId = Path(...)):
    """Get individual file details."""
    try:
        result = service.get_by_id(file_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.FILE.NOT_FOUND", "message": "File not found"}
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.GET.UNEXPECTED", "message": str(e)}
        )


# ========== GET FILES BY BATCH ==========
@router.get(
    "/batch/{data_received_id}",
    response_model=List[DataReceivedFileResponseSchema],
    summary="Get Files by Batch ID"
)
async def get_files_by_batch(data_received_id: PyObjectId = Path(...)):
    """Get all files for a data_received batch."""
    try:
        return service.get_by_data_received_id(data_received_id)
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.GET_BY_BATCH.UNEXPECTED", "message": str(e)}
        )


# ========== MANUAL MAP FILE ==========
@router.post(
    "/{file_id}/map",
    response_model=DataReceivedFileResponseSchema,
    summary="Manually Map File to Pipeline"
)
async def manual_map_file(
    file_id: PyObjectId = Path(...),
    pipeline_id: PyObjectId = Body(..., embed=True),
    request: Request = ...
):
    """Manually map file to pipeline."""
    try:
        mapped_by = get_current_user_id()
        mapped_ip = get_client_ip(request)
        
        result = service.manual_map_file(file_id, pipeline_id, mapped_by, mapped_ip)
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.error_code, "message": e.message}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ERR.FILE.MAP.INVALID", "message": str(e)}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.MAP.UNEXPECTED", "message": str(e)}
        )


# ========== SEARCH PIPELINES ==========
@router.get(
    "/search-pipelines",
    response_model=list,
    summary="Search Pipelines for Manual Mapping"
)
async def search_pipelines_for_mapping(
    operator_id: Optional[PyObjectId] = Query(None, alias="operatorId"),
    key_field_value: Optional[str] = Query(None, alias="keyFieldValue"),
    service_id: Optional[PyObjectId] = Query(None, alias="serviceId"),
    fir_no: Optional[int] = Query(None, alias="firNo")
):
    """Search available pipelines for manual file mapping."""
    try:
        return service.search_pipelines_for_mapping(
            operator_id=operator_id,
            key_field_value=key_field_value,
            service_id=service_id,
            fir_no=fir_no
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.SEARCH.UNEXPECTED", "message": str(e)}
        )


# ========== GET BY STATUS ==========
@router.get(
    "/status/{status}",
    response_model=List[DataReceivedFileResponseSchema],
    summary="Get Files by Status"
)
async def get_files_by_status(
    status: MatchingStatus = Path(...),
    data_received_id: Optional[PyObjectId] = Query(None, alias="dataReceivedId"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get files filtered by matching status."""
    try:
        return service.get_by_status(status, data_received_id, limit)
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.GET_STATUS.UNEXPECTED", "message": str(e)}
        )


# ========== RETRY AUTO-MATCH ==========
@router.post(
    "/{file_id}/retry-match",
    response_model=DataReceivedFileResponseSchema,
    summary="Retry Auto-Matching"
)
async def retry_auto_match(
    file_id: PyObjectId = Path(...),
    operator_id: PyObjectId = Body(..., embed=True),
    request: Request = ...
):
    """Retry auto-matching for unmatched file."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.retry_auto_match(file_id, operator_id, updated_by, updated_ip)
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.error_code, "message": e.message}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ERR.FILE.RETRY.INVALID", "message": str(e)}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.RETRY.UNEXPECTED", "message": str(e)}
        )


# ========== UNMAP FILE ==========
@router.post(
    "/{file_id}/unmap",
    response_model=DataReceivedFileResponseSchema,
    summary="Unmap File from Pipeline"
)
async def unmap_file(
    file_id: PyObjectId = Path(...),
    request: Request = ...
):
    """Unmap file from its current pipeline."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.unmap_file(file_id, updated_by, updated_ip)
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.error_code, "message": e.message}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ERR.FILE.UNMAP.INVALID", "message": str(e)}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILE.UNMAP.UNEXPECTED", "message": str(e)}
        )

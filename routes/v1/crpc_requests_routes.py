"""
Purpose: FastAPI router for CrPC Requests endpoints.
Provides RESTful API for main CrPC request operations.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body
from typing import Optional
from datetime import date
import traceback

from models.crpc_requests_models import (
    CrpcRequestCreateSchema,
    CrpcRequestUpdateSchema,
    CrpcRequestResponseSchema,
    CrpcRequestListResponseSchema,
    CrpcRequestSearchSchema,
    CrpcRequestWithPipelinesSchema,
    CloseRequestSchema,
)
from services.crpc_requests_service import (
    CrpcRequestService,
    RequestNotFoundError,
    PipelineGenerationError,
    InvalidServiceListError,
    UnauthorizedClosureError,
    DatabaseOperationError,
)
from utils.validators import PyObjectId
from constants.value_sets import CrpcRequestStatus


router = APIRouter(
    prefix="/api/v1/crpc-requests",
    tags=["CrPC Requests"],
)

service = CrpcRequestService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """Get current authenticated user ID. TODO: JWT authentication"""
    return PyObjectId("6710000000000000000000a5")


def get_current_user_role() -> str:
    """Get current user's role. TODO: JWT token extraction"""
    return "SHO"


# ========== CREATE Endpoint ==========
@router.post(
    "",
    response_model=CrpcRequestResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create CrPC Request",
    description="Create a new CrPC request with automatic pipeline and approval chain generation"
)
async def create_request(
    data: CrpcRequestCreateSchema,
    request: Request
):
    """Create CrPC request with pre-validation."""
    try:
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        result = service.create_request(data, created_by, created_ip)
        return result
        
    except InvalidServiceListError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "serviceList",
                "suggestion": "Verify all service IDs exist in service_master collection"
            }
        )
    except PipelineGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": e.message,
                "note": "Request was rolled back",
                "suggestion": "Check operator mappings in operator_service_list"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.CRPC_REQUEST.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Database operation failed",
                "details": e.message
            }
        )
    except Exception as e:
        print(f"Unexpected error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.CRPC_REQUEST.CREATE.UNEXPECTED",
                "message": "Unexpected error occurred",
                "details": str(e)
            }
        )


# ========== READ Endpoint ==========
@router.get(
    "/{request_id}",
    response_model=CrpcRequestResponseSchema,
    summary="Get CrPC Request by ID"
)
async def get_request(request_id: PyObjectId = Path(...)):
    """Get CrPC request by ID."""
    try:
        result = service.get_request_by_id(request_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.CRPC_REQUEST.NOT_FOUND",
                    "message": f"Request {request_id} not found"
                }
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.READ.UNEXPECTED", "message": str(e)}
        )


# ========== GET WITH PIPELINES ==========
@router.get(
    "/{request_id}/details",
    response_model=CrpcRequestWithPipelinesSchema,
    summary="Get Request with Pipelines"
)
async def get_request_with_pipelines(request_id: PyObjectId = Path(...)):
    """Get complete request with pipeline details."""
    try:
        result = service.get_request_with_pipelines(request_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.CRPC_REQUEST.NOT_FOUND", "message": "Not found"}
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.GET_DETAILS.UNEXPECTED", "message": str(e)}
        )


# ========== UPDATE Endpoint ==========
@router.put(
    "/{request_id}",
    response_model=CrpcRequestResponseSchema,
    summary="Update CrPC Request"
)
async def update_request(
    request_id: PyObjectId = Path(...),
    data: CrpcRequestUpdateSchema = ...,
    request: Request = ...
):
    """Update CrPC request (limited fields)."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.update_request(request_id, data, updated_by, updated_ip)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.CRPC_REQUEST.NOT_FOUND", "message": "Not found"}
            )
        return result
    except RequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": e.error_code, "message": e.message})
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.UPDATE.UNEXPECTED", "message": str(e)}
        )


# ========== CLOSE Request ==========
@router.post(
    "/{request_id}/close",
    response_model=CrpcRequestResponseSchema,
    summary="Close CrPC Request (SHO only)"
)
async def close_request(
    request_id: PyObjectId = Path(...),
    closure_data: CloseRequestSchema = Body(...),
    request: Request = ...
):
    """Close request (SHO only)."""
    try:
        user_role = get_current_user_role()
        closed_by = get_current_user_id()
        closed_ip = get_client_ip(request)
        
        result = service.close_request(request_id, closure_data, user_role, closed_by, closed_ip)
        return result
    except UnauthorizedClosureError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": e.error_code, "message": e.message})
    except RequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": e.error_code, "message": e.message})
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.CLOSE.UNEXPECTED", "message": str(e)}
        )


# ========== SEARCH Endpoint ==========
@router.get(
    "",
    response_model=CrpcRequestListResponseSchema,
    summary="Search CrPC Requests"
)
async def search_requests(
    unit_id: Optional[PyObjectId] = Query(None, alias="unitId"),
    requested_by: Optional[PyObjectId] = Query(None, alias="requestedBy"),
    fir_no: Optional[int] = Query(None, alias="firNo"),
    crpc_request_status: Optional[CrpcRequestStatus] = Query(None, alias="CrPCRequestStatus"),
    request_date_from: Optional[date] = Query(None, alias="requestDateFrom"),
    request_date_to: Optional[date] = Query(None, alias="requestDateTo"),
    ack_no: Optional[str] = Query(None, alias="ackNo"),
    include_inactive: bool = Query(False, alias="includeInactive"),
    sort_by: str = Query("createdAt", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize")
):
    """Search and filter CrPC requests."""
    try:
        search_params = CrpcRequestSearchSchema(
            unitId=unit_id,
            requestedBy=requested_by,
            firNo=fir_no,
            CrPCRequestStatus=crpc_request_status,
            requestDateFrom=request_date_from,
            requestDateTo=request_date_to,
            ackNo=ack_no,
            includeInactive=include_inactive,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_requests(search_params)
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "data": results,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ERR.CRPC_REQUEST.SEARCH.VALIDATION", "message": str(e)}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.SEARCH.UNEXPECTED", "message": str(e)}
        )


# ========== GET BY FIR ==========
@router.get(
    "/fir/{fir_no}",
    response_model=list[CrpcRequestResponseSchema],
    summary="Get Requests by FIR"
)
async def get_by_fir_number(fir_no: int = Path(...)):
    """Get all requests for a FIR."""
    try:
        return service.get_by_fir_number(fir_no)
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.GET_BY_FIR.UNEXPECTED", "message": str(e)}
        )


# ========== GET BY UNIT ==========
@router.get(
    "/unit/{unit_id}",
    response_model=list[CrpcRequestResponseSchema],
    summary="Get Requests by Unit"
)
async def get_by_unit(unit_id: PyObjectId = Path(...)):
    """Get all requests for a unit."""
    try:
        return service.get_by_unit(unit_id)
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CRPC_REQUEST.GET_BY_UNIT.UNEXPECTED", "message": str(e)}
        )

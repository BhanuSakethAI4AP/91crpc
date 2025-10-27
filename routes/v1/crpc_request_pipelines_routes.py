"""
Purpose: FastAPI router for CrPC Request Pipelines endpoints.
Provides RESTful API for pipeline operations.

Handles individual service line items tracking.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body
from typing import Optional, List
import traceback

from models.crpc_request_pipelines_models import (
    CrpcRequestPipelineCreateSchema,
    CrpcRequestPipelineUpdateSchema,
    CrpcRequestPipelineResponseSchema,
    CrpcRequestPipelineListResponseSchema,
    CrpcRequestPipelineSearchSchema,
    PipelineStatusUpdateSchema,
    CrpcRequestPipelineWithDetailsSchema,
)
from services.crpc_request_pipelines_service import (
    CrpcRequestPipelineService,
    PipelineNotFoundError,
    InvalidOperatorError,
    InvalidServiceError,
    DuplicatePipelineError,
    DatabaseOperationError,
    CrpcRequestPipelineError,
)
from utils.validators import PyObjectId
from constants.value_sets import LineItemRequestStatus


router = APIRouter(
    prefix="/api/v1/crpc-pipelines",
    tags=["CrPC Request Pipelines"],
)

service = CrpcRequestPipelineService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """
    Get current authenticated user ID.
    TODO: Replace with actual JWT authentication
    """
    return PyObjectId("6710000000000000000000a2")


# ========== CREATE Endpoint ==========
@router.post(
    "",
    response_model=CrpcRequestPipelineResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Pipeline",
    description="Create a new pipeline (auto-created with CrPC request)"
)
async def create_pipeline(
    data: CrpcRequestPipelineCreateSchema,
    request: Request
):
    """
    Create pipeline.
    
    Note: Typically auto-created when CrPC request is created.
    This endpoint is for manual creation if needed.
    """
    try:
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        result = service.create_pipeline(data, created_by, created_ip)
        return result
        
    except InvalidServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "serviceId"
            }
        )
    except InvalidOperatorError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "operatorId"
            }
        )
    except DuplicatePipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.PIPELINE.CREATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in create_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create pipeline"
            }
        )
    except Exception as e:
        print(f"Unexpected error in create_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint ==========
@router.get(
    "/{pipeline_id}",
    response_model=CrpcRequestPipelineResponseSchema,
    summary="Get Pipeline by ID",
    description="Retrieve a pipeline by its ID"
)
async def get_pipeline(
    pipeline_id: PyObjectId = Path(..., description="Pipeline ID")
):
    """Get pipeline by ID."""
    try:
        result = service.get_pipeline_by_id(pipeline_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.PIPELINE.NOT_FOUND",
                    "message": f"Pipeline with ID {pipeline_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        print(f"Database error in get_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve pipeline"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET BY REQUEST ID ==========
@router.get(
    "/request/{request_id}",
    response_model=list[CrpcRequestPipelineResponseSchema],
    summary="Get Pipelines by Request ID",
    description="Get all pipelines for a CrPC request"
)
async def get_by_request_id(
    request_id: PyObjectId = Path(..., description="CrPC Request ID")
):
    """Get all pipelines for a CrPC request."""
    try:
        results = service.get_by_request_id(request_id)
        return results
        
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve pipelines"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_by_request_id: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.GET_BY_REQUEST.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET WITH DETAILS ==========
@router.get(
    "/request/{request_id}/details",
    response_model=list[CrpcRequestPipelineWithDetailsSchema],
    summary="Get Pipelines with Details",
    description="Get pipelines with service/operator names"
)
async def get_pipelines_with_details(
    request_id: PyObjectId = Path(..., description="CrPC Request ID")
):
    """Get pipelines with joined details."""
    try:
        results = service.get_pipelines_with_details(request_id)
        return results
        
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve pipeline details"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_pipelines_with_details: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.GET_DETAILS.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint ==========
@router.put(
    "/{pipeline_id}",
    response_model=CrpcRequestPipelineResponseSchema,
    summary="Update Pipeline",
    description="Update a pipeline"
)
async def update_pipeline(
    pipeline_id: PyObjectId = Path(..., description="Pipeline ID"),
    data: CrpcRequestPipelineUpdateSchema = ...,
    request: Request = ...
):
    """Update pipeline."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.update_pipeline(pipeline_id, data, updated_by, updated_ip)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.PIPELINE.NOT_FOUND",
                    "message": f"Pipeline with ID {pipeline_id} not found"
                }
            )
        
        return result
        
    except PipelineNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except InvalidOperatorError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.PIPELINE.UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in update_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update pipeline"
            }
        )
    except Exception as e:
        print(f"Unexpected error in update_pipeline: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE STATUS ==========
@router.patch(
    "/{pipeline_id}/status",
    response_model=CrpcRequestPipelineResponseSchema,
    summary="Update Pipeline Status",
    description="Update pipeline status"
)
async def update_pipeline_status(
    pipeline_id: PyObjectId = Path(..., description="Pipeline ID"),
    status_data: PipelineStatusUpdateSchema = Body(...),
    request: Request = ...
):
    """Update pipeline status."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.update_status(pipeline_id, status_data, updated_by, updated_ip)
        return result
        
    except PipelineNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.PIPELINE.UPDATE_STATUS.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in update_pipeline_status: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update pipeline status"
            }
        )
    except Exception as e:
        print(f"Unexpected error in update_pipeline_status: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.UPDATE_STATUS.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== BULK UPDATE ==========
@router.post(
    "/bulk-update",
    summary="Bulk Update Pipelines",
    description="Update multiple pipelines at once"
)
async def bulk_update_pipelines(
    pipeline_ids: List[PyObjectId] = Body(..., description="List of pipeline IDs"),
    updates: dict = Body(..., description="Fields to update"),
    request: Request = ...
):
    """Bulk update pipelines."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.bulk_update(pipeline_ids, updates, updated_by, updated_ip)
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.PIPELINE.BULK_UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in bulk_update_pipelines: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to bulk update pipelines"
            }
        )
    except Exception as e:
        print(f"Unexpected error in bulk_update_pipelines: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.BULK_UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint ==========
@router.get(
    "",
    response_model=CrpcRequestPipelineListResponseSchema,
    summary="Search Pipelines",
    description="Search, filter, sort, and paginate pipelines"
)
async def search_pipelines(
    crpc_request_id: Optional[PyObjectId] = Query(None, alias="crpcRequestId"),
    operator_id: Optional[PyObjectId] = Query(None, alias="operatorId"),
    service_id: Optional[PyObjectId] = Query(None, alias="serviceId"),
    line_item_request_status: Optional[LineItemRequestStatus] = Query(None, alias="lineItemRequestStatus"),
    key_field_value: Optional[str] = Query(None, alias="keyFieldValue"),
    include_inactive: bool = Query(False, alias="includeInactive"),
    sort_by: str = Query("createdAt", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize")
):
    """Search and filter pipelines."""
    try:
        search_params = CrpcRequestPipelineSearchSchema(
            crpcRequestId=crpc_request_id,
            operatorId=operator_id,
            serviceId=service_id,
            lineItemRequestStatus=line_item_request_status,
            keyFieldValue=key_field_value,
            includeInactive=include_inactive,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_pipelines(search_params)
        
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
            detail={
                "error": "ERR.PIPELINE.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in search_pipelines: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search pipelines"
            }
        )
    except Exception as e:
        print(f"Unexpected error in search_pipelines: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.PIPELINE.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

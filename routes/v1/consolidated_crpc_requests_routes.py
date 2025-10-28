"""
Purpose: FastAPI router for Consolidated CrPC Requests.
Provides API for consolidation and dispatch management.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
import traceback
import os

from models.consolidated_crpc_requests_models import (
    ConsolidatedCrpcRequestResponseSchema,
    ConsolidatedListResponseSchema,
    ConsolidatedSearchSchema,
    MarkDownloadedSchema,
)
from services.consolidated_crpc_requests_service import (
    ConsolidatedCrpcRequestsService,
    NotFoundError,
    NoPipelinesError,
    DatabaseOperationError,
)
from utils.validators import PyObjectId
from constants.value_sets import DispatchMode, ConsolidatedRequestStatus


router = APIRouter(
    prefix="/api/v1/consolidated",
    tags=["Consolidated Requests"],
)

service = ConsolidatedCrpcRequestsService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """Get current authenticated user ID."""
    return PyObjectId("6710000000000000000000a2")


# ========== GET AVAILABLE CONSOLIDATIONS ==========
@router.get(
    "/available",
    response_model=list,
    summary="Get Available Consolidations",
    description="Get list of service-operator combinations ready for consolidation"
)
async def get_available_consolidations():
    """
    Get consolidatable pipelines grouped by service and operator.
    
    Shows which combinations have approved pipelines ready to consolidate.
    """
    try:
        return service.get_available_consolidations()
        
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.AVAILABLE.UNEXPECTED", "message": str(e)}
        )


# ========== CREATE CONSOLIDATION ==========
@router.post(
    "/create",
    response_model=ConsolidatedCrpcRequestResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Consolidation",
    description="Consolidate approved pipelines for service-operator combination"
)
async def create_consolidation(
    service_id: PyObjectId = Body(..., embed=True, description="Service ID"),
    operator_id: PyObjectId = Body(..., embed=True, description="Operator ID"),
    mode: DispatchMode = Body(..., embed=True, description="Dispatch mode (Email/SMS)"),
    request: Request = ...
):
    """
    Create consolidated request.
    
    Steps:
    1. Find approved pipelines for service-operator
    2. Generate output file (Excel/Word/etc based on config)
    3. Create consolidated record
    4. Update pipeline statuses to 'Consolidated'
    """
    try:
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        result = service.create_consolidation(
            service_id,
            operator_id,
            mode,
            created_by,
            created_ip
        )
        
        return result
        
    except NoPipelinesError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.error_code, "message": e.message}
        )
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CONSOLIDATE.UNEXPECTED", "message": str(e)}
        )


# ========== GET BY ID ==========
@router.get(
    "/{consolidated_id}",
    response_model=ConsolidatedCrpcRequestResponseSchema,
    summary="Get Consolidation by ID",
    description="Retrieve consolidated request details"
)
async def get_consolidation(
    consolidated_id: PyObjectId = Path(..., description="Consolidated Request ID")
):
    """Get consolidated request by ID."""
    try:
        result = service.get_by_id(consolidated_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.CONSOLIDATED.NOT_FOUND",
                    "message": f"Consolidated request {consolidated_id} not found"
                }
            )
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.GET.UNEXPECTED", "message": str(e)}
        )


# ========== DOWNLOAD FILE ==========
@router.get(
    "/{consolidated_id}/download",
    summary="Download Consolidated File",
    description="Download the generated file and mark as downloaded"
)
async def download_file(
    consolidated_id: PyObjectId = Path(..., description="Consolidated Request ID"),
    request: Request = ...
):
    """
    Download consolidated file.
    
    Automatically marks the request as 'Downloaded' on first download.
    """
    try:
        # Get consolidated request
        consolidated = service.get_by_id(consolidated_id)
        if not consolidated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.NOT_FOUND", "message": "Consolidated request not found"}
            )
        
        # Get file path
        letter_files = consolidated.get("letterFilePaths", [])
        if not letter_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.NO_FILE", "message": "No file generated for this consolidation"}
            )
        
        filepath = letter_files[0].get("formatFilePath")
        if not os.path.exists(filepath):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.FILE_NOT_FOUND", "message": "File not found on server"}
            )
        
        # Mark as downloaded (if not already)
        if consolidated.get("consolidatedCrpcRequestStatus") == ConsolidatedRequestStatus.NOT_DOWNLOADED.value:
            downloaded_by = get_current_user_id()
            downloaded_ip = get_client_ip(request)
            service.mark_as_downloaded(consolidated_id, downloaded_by, downloaded_ip)
        
        # Return file
        return FileResponse(
            filepath,
            filename=os.path.basename(filepath),
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.DOWNLOAD.UNEXPECTED", "message": str(e)}
        )


# ========== MARK AS DOWNLOADED ==========
@router.post(
    "/{consolidated_id}/mark-downloaded",
    response_model=ConsolidatedCrpcRequestResponseSchema,
    summary="Mark as Downloaded",
    description="Manually mark consolidation as downloaded"
)
async def mark_downloaded(
    consolidated_id: PyObjectId = Path(..., description="Consolidated Request ID"),
    request: Request = ...
):
    """Mark consolidated request as downloaded."""
    try:
        downloaded_by = get_current_user_id()
        downloaded_ip = get_client_ip(request)
        
        result = service.mark_as_downloaded(consolidated_id, downloaded_by, downloaded_ip)
        return result
        
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.MARK_DOWNLOADED.UNEXPECTED", "message": str(e)}
        )


# ========== SEARCH ==========
@router.get(
    "",
    response_model=ConsolidatedListResponseSchema,
    summary="Search Consolidated Requests",
    description="Search and filter consolidated requests with pagination"
)
async def search_consolidations(
    service_id: Optional[PyObjectId] = Query(None, alias="serviceId", description="Filter by service"),
    operator_id: Optional[PyObjectId] = Query(None, alias="operatorId", description="Filter by operator"),
    status: Optional[ConsolidatedRequestStatus] = Query(None, description="Filter by status"),
    created_date_from: Optional[datetime] = Query(None, alias="createdDateFrom", description="From date"),
    created_date_to: Optional[datetime] = Query(None, alias="createdDateTo", description="To date"),
    include_inactive: bool = Query(False, alias="includeInactive", description="Include inactive"),
    sort_by: str = Query("createdAt", alias="sortBy", description="Sort field"),
    sort_order: str = Query("desc", alias="sortOrder", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize", description="Items per page")
):
    """Search consolidated requests with filters."""
    try:
        search_params = ConsolidatedSearchSchema(
            serviceId=service_id,
            operatorId=operator_id,
            status=status,
            createdDateFrom=created_date_from,
            createdDateTo=created_date_to,
            includeInactive=include_inactive,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search(search_params)
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
            detail={"error": "ERR.SEARCH.VALIDATION", "message": str(e)}
        )
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.SEARCH.UNEXPECTED", "message": str(e)}
        )


# ========== DELETE ==========
@router.delete(
    "/{consolidated_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Consolidation",
    description="Soft delete consolidated request"
)
async def delete_consolidation(
    consolidated_id: PyObjectId = Path(..., description="Consolidated Request ID"),
    request: Request = ...
):
    """Soft delete consolidated request."""
    try:
        deleted_by = get_current_user_id()
        deleted_ip = get_client_ip(request)
        
        success = service.delete_consolidation(consolidated_id, deleted_by, deleted_ip)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ERR.NOT_FOUND", "message": "Consolidated request not found"}
            )
        
        return None
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        print(f"Database error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.DELETE.UNEXPECTED", "message": str(e)}
        )

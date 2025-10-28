"""
Purpose: FastAPI router for Data Received endpoints.
Provides RESTful API for data reception and conflict resolution.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone
import traceback

from models.data_received_models import (
    DataReceivedResponseSchema,
    DataReceivedListResponseSchema,
    DataReceivedSearchSchema,
    ResolveConflictSchema,
    DataReceivedCreateSchema,
    EmailMetaDataSchema,
)
from models.data_received_files_models import (
    DataReceivedFileResponseSchema,
    FileWithPipelineDetailsSchema,
)
from services.data_received_service import (
    DataReceivedService,
    DataReceivedNotFoundError,
    DatabaseOperationError,
)
from services.data_received_files_service import FileNotFoundError
from utils.validators import PyObjectId
from constants.value_sets import ProcessingStatus


router = APIRouter(
    prefix="/api/v1/data-received",
    tags=["Data Received"],
)

service = DataReceivedService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """Get current authenticated user ID. TODO: JWT integration"""
    return PyObjectId("6710000000000000000000a2")


# ========== UPLOAD Endpoint ==========
@router.post(
    "/upload",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Received Data",
    description="Upload data received from operator with auto-matching"
)
async def upload_data_received(
    operator_id: str = Form(..., description="Operator ID"),
    email_from: Optional[str] = Form(None, description="Sender email"),
    email_subject: Optional[str] = Form(None, description="Email subject"),
    email_password: Optional[str] = Form(None, description="ZIP password"),
    files: List[UploadFile] = File(..., description="Files received from operator"),
    request: Request = ...
):
    """
    Upload received data files with auto-matching.
    
    Process:
    1. Upload files to storage
    2. Create data_received record
    3. Auto-match files to pipelines
    4. Return matching results
    """
    try:
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        # TODO: Save files to storage (S3/local)
        # For now, collect file info
        file_infos = []
        for file in files:
            # TODO: Implement actual file storage
            # await save_file_to_storage(file)
            file_info = {
                "fileName": file.filename,
                "fileType": "CDR",  # TODO: Detect from filename or metadata
                "filePath": f"/uploads/data_received/{file.filename}",
                "fileSize": file.size or 0,
                "uploadedAt": datetime.now(timezone.utc)
            }
            file_infos.append(file_info)
        
        # Prepare email metadata
        email_metadata = None
        if email_from:
            email_metadata = EmailMetaDataSchema(
                fromEmail=email_from,
                subject=email_subject or "",
                password=email_password
            )
        
        # Create data received record
        data = DataReceivedCreateSchema(
            receivedAt=datetime.now(timezone.utc),
            operatorId=PyObjectId(operator_id),
            totalFiles=len(file_infos),
            emailMetaData=email_metadata
        )
        
        # Process with auto-matching
        result, matching_results = service.create_data_received(
            data,
            file_infos,
            created_by,
            created_ip
        )
        
        return {
            "dataReceived": result,
            "matchingResults": {
                "autoMatchedCount": len(matching_results["auto_matched"]),
                "conflictCount": len(matching_results["conflicts"]),
                "unmatchedCount": len(matching_results["unmatched"])
            }
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.DATA_RECEIVED.UPLOAD.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in upload_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except Exception as e:
        print(f"Unexpected error in upload_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.DATA_RECEIVED.UPLOAD.UNEXPECTED",
                "message": str(e)
            }
        )


# ========== GET BY ID ==========
@router.get(
    "/{data_received_id}",
    response_model=DataReceivedResponseSchema,
    summary="Get Data Received by ID",
    description="Retrieve data received record with processing status"
)
async def get_data_received(
    data_received_id: PyObjectId = Path(..., description="Data Received ID")
):
    """Get data received record by ID."""
    try:
        result = service.get_by_id(data_received_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.DATA_RECEIVED.NOT_FOUND",
                    "message": f"Data received with ID {data_received_id} not found"
                }
            )
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        print(f"Database error in get_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error in get_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.DATA_RECEIVED.GET.UNEXPECTED", "message": str(e)}
        )


# ========== GET FILES ==========
@router.get(
    "/{data_received_id}/files",
    response_model=List[DataReceivedFileResponseSchema],
    summary="Get Files for Data Received",
    description="Get all files in this data received batch"
)
async def get_files(
    data_received_id: PyObjectId = Path(..., description="Data Received ID")
):
    """Get all files for a data received batch."""
    try:
        return service.get_files(data_received_id)
        
    except Exception as e:
        print(f"Error in get_files: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.FILES.GET.UNEXPECTED", "message": str(e)}
        )


# ========== GET CONFLICTS ==========
@router.get(
    "/{data_received_id}/conflicts",
    response_model=List[FileWithPipelineDetailsSchema],
    summary="Get Conflicted Files",
    description="Get files with multiple pipeline matches requiring manual resolution"
)
async def get_conflicts(
    data_received_id: PyObjectId = Path(..., description="Data Received ID")
):
    """Get all files with conflict status and their potential matches."""
    try:
        return service.get_conflicts(data_received_id)
        
    except Exception as e:
        print(f"Error in get_conflicts: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CONFLICTS.GET.UNEXPECTED", "message": str(e)}
        )


# ========== GET UNMATCHED ==========
@router.get(
    "/{data_received_id}/unmatched",
    response_model=List[DataReceivedFileResponseSchema],
    summary="Get Unmatched Files",
    description="Get files that couldn't be auto-matched to any pipeline"
)
async def get_unmatched(
    data_received_id: PyObjectId = Path(..., description="Data Received ID")
):
    """Get all unmatched files."""
    try:
        return service.get_unmatched(data_received_id)
        
    except Exception as e:
        print(f"Error in get_unmatched: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.UNMATCHED.GET.UNEXPECTED", "message": str(e)}
        )


# ========== RESOLVE CONFLICT ==========
@router.post(
    "/resolve-conflict",
    response_model=DataReceivedFileResponseSchema,
    summary="Resolve File Conflict",
    description="Manually resolve conflict by selecting correct pipeline"
)
async def resolve_conflict(
    conflict_data: ResolveConflictSchema = Body(..., description="File and pipeline selection"),
    request: Request = ...
):
    """
    Resolve conflict by selecting correct pipeline.
    
    Used when a file matches multiple pipelines and needs manual selection.
    """
    try:
        resolved_by = get_current_user_id()
        resolved_ip = get_client_ip(request)
        
        result = service.resolve_conflict(conflict_data, resolved_by, resolved_ip)
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.error_code, "message": e.message}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ERR.CONFLICT.RESOLVE.INVALID", "message": str(e)}
        )
    except DatabaseOperationError as e:
        print(f"Database error in resolve_conflict: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error in resolve_conflict: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.CONFLICT.RESOLVE.UNEXPECTED", "message": str(e)}
        )


# ========== SEARCH ==========
@router.get(
    "",
    response_model=DataReceivedListResponseSchema,
    summary="Search Data Received",
    description="Search and filter data received records with pagination"
)
async def search_data_received(
    operator_id: Optional[PyObjectId] = Query(None, alias="operatorId", description="Filter by operator"),
    processing_status: Optional[ProcessingStatus] = Query(None, alias="processingStatus", description="Filter by status"),
    received_date_from: Optional[datetime] = Query(None, alias="receivedDateFrom", description="From date"),
    received_date_to: Optional[datetime] = Query(None, alias="receivedDateTo", description="To date"),
    include_inactive: bool = Query(False, alias="includeInactive", description="Include inactive records"),
    sort_by: str = Query("receivedAt", alias="sortBy", description="Sort field"),
    sort_order: str = Query("desc", alias="sortOrder", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize", description="Items per page")
):
    """Search data received records with filters and pagination."""
    try:
        search_params = DataReceivedSearchSchema(
            operatorId=operator_id,
            processingStatus=processing_status,
            receivedDateFrom=received_date_from,
            receivedDateTo=received_date_to,
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
        print(f"Database error in search_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.error_code, "message": e.message}
        )
    except Exception as e:
        print(f"Error in search_data_received: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ERR.SEARCH.UNEXPECTED", "message": str(e)}
        )

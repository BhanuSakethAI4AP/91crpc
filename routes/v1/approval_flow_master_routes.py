"""
Purpose: FastAPI router for Approval Flow Master endpoints.
Provides RESTful API for CRUD operations on approval workflow definitions.

Based on TFS: ApprovalFlowMaster.CREATE, READ, UPDATE, DELETE
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path
from typing import Optional
import traceback

from models.approval_flow_master_models import (
    ApprovalFlowMasterCreateSchema,
    ApprovalFlowMasterUpdateSchema,
    ApprovalFlowMasterResponseSchema,
    ApprovalFlowMasterListResponseSchema,
    ApprovalFlowMasterSearchSchema,
)
from services.approval_flow_master_service import (
    ApprovalFlowMasterService,
    ApprovalFlowNotFoundError,
    InvalidStepsError,
    DatabaseOperationError,
    ApprovalFlowMasterError,
)
from utils.validators import PyObjectId
from constants.value_sets import ApprovalRole


router = APIRouter(
    prefix="/api/v1/approval-flows",
    tags=["Approval Flow Master"],
)

service = ApprovalFlowMasterService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request.
    
    Returns:
        str: Client IP address or 'unknown'
    """
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """
    Get current authenticated user ID.
    
    TODO: Replace with actual JWT authentication
    RBAC: Extract user ID from JWT token
    
    Returns:
        PyObjectId: Current user ID
    """
    # This will be replaced with actual JWT token validation
    # For now, returns a dummy user ID
    return PyObjectId("6710000000000000000000a1")


# ========== CREATE Endpoint (TFS: ApprovalFlowMaster.CREATE) ==========
@router.post(
    "",
    response_model=ApprovalFlowMasterResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Approval Flow",
    description="Create a new approval workflow definition (TFS: ApprovalFlowMaster.CREATE)",
    responses={
        201: {"description": "Approval flow created successfully"},
        400: {"description": "Validation error (empty steps, invalid role, invalid order)"},
        500: {"description": "Internal server error"}
    }
)
async def create_approval_flow(
    data: ApprovalFlowMasterCreateSchema,
    request: Request
):
    """
    Create a new approval flow.
    
    TFS Reference: ApprovalFlowMaster.CREATE
    RBAC Permission: PERM.APPROVAL_FLOW.CREATE.GLOBAL
    
    Preconditions:
        - Steps array must not be empty
        - Each role must exist in Enum(ApprovalRoles)
        - Orders must be unique and sequential
    
    Error Codes:
        - ERR.APPROVAL_FLOW.EMPTY_STEPS
        - ERR.APPROVAL_FLOW.INVALID_ROLE
        - ERR.APPROVAL_FLOW.INVALID_ORDER
    
    Raises:
        400: Validation error
        500: Database operation failed
    """
    try:
        # Get current user and IP
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.CREATE.GLOBAL
        
        # Call service layer
        result = service.create_approval_flow(data, created_by, created_ip)
        return result
        
    except ValueError as e:
        # ERROR: Pydantic validation error (steps validation)
        # Codes: ERR.APPROVAL_FLOW.EMPTY_STEPS, ERR.APPROVAL_FLOW.INVALID_ORDER, etc.
        error_msg = str(e)
        
        # Extract error code if present
        if "ERR." in error_msg:
            error_code = error_msg.split(":")[0]
            message = error_msg.split(":", 1)[1].strip() if ":" in error_msg else error_msg
        else:
            error_code = "ERR.APPROVAL_FLOW.CREATE.VALIDATION"
            message = error_msg
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": error_code,
                "message": message,
                "field": "steps"
            }
        )
    except InvalidStepsError as e:
        # ERROR: ERR.APPROVAL_FLOW.INVALID_STEPS
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "steps"
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.APPROVAL_FLOW.CREATE.DB_ERROR
        # Log full traceback for debugging
        print(f"Database error in create_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create approval flow. Please try again later."
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in create_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint (TFS: ApprovalFlowMaster.READ) ==========
@router.get(
    "/{flow_id}",
    response_model=ApprovalFlowMasterResponseSchema,
    summary="Get Approval Flow by ID",
    description="Retrieve an approval flow by its ID (TFS: ApprovalFlowMaster.READ)",
    responses={
        200: {"description": "Approval flow found"},
        404: {"description": "Approval flow not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_approval_flow(
    flow_id: PyObjectId = Path(..., description="Approval Flow ID")
):
    """
    Get approval flow by ID.
    
    TFS Reference: ApprovalFlowMaster.READ
    RBAC Permission: PERM.APPROVAL_FLOW.READ.GLOBAL
    
    Raises:
        404: Approval flow not found
        500: Database operation failed
    """
    try:
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.READ.GLOBAL
        
        result = service.get_approval_flow_by_id(flow_id)
        
        if not result:
            # ERROR: ERR.APPROVAL_FLOW.READ.NOT_FOUND
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_FLOW.READ.NOT_FOUND",
                    "message": f"Approval flow with ID {flow_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        # ERROR: ERR.APPROVAL_FLOW.READ.DB_ERROR
        print(f"Database error in get_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve approval flow"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint (TFS: ApprovalFlowMaster.UPDATE) ==========
@router.put(
    "/{flow_id}",
    response_model=ApprovalFlowMasterResponseSchema,
    summary="Update Approval Flow",
    description="Update an existing approval flow (TFS: ApprovalFlowMaster.UPDATE)",
    responses={
        200: {"description": "Approval flow updated successfully"},
        400: {"description": "Validation error (invalid steps)"},
        404: {"description": "Approval flow not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_approval_flow(
    flow_id: PyObjectId = Path(..., description="Approval Flow ID"),
    data: ApprovalFlowMasterUpdateSchema = ...,
    request: Request = ...
):
    """
    Update approval flow.
    
    TFS Reference: ApprovalFlowMaster.UPDATE
    RBAC Permission: PERM.APPROVAL_FLOW.UPDATE.GLOBAL
    
    Purpose: Modify approval steps or reorder existing approval roles
    
    Raises:
        400: Validation error
        404: Approval flow not found
        500: Database operation failed
    """
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.UPDATE.GLOBAL
        
        result = service.update_approval_flow(flow_id, data, updated_by, updated_ip)
        
        if not result:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_FLOW.NOT_FOUND",
                    "message": f"Approval flow with ID {flow_id} not found"
                }
            )
        
        return result
        
    except ApprovalFlowNotFoundError as e:
        # ERROR: ERR.APPROVAL_FLOW.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except ValueError as e:
        # ERROR: Pydantic validation error
        error_msg = str(e)
        
        # Extract error code if present
        if "ERR." in error_msg:
            error_code = error_msg.split(":")[0]
            message = error_msg.split(":", 1)[1].strip() if ":" in error_msg else error_msg
        else:
            error_code = "ERR.APPROVAL_FLOW.UPDATE.VALIDATION"
            message = error_msg
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": error_code,
                "message": message,
                "field": "steps"
            }
        )
    except InvalidStepsError as e:
        # ERROR: ERR.APPROVAL_FLOW.INVALID_STEPS
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "steps"
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.APPROVAL_FLOW.UPDATE.DB_ERROR
        print(f"Database error in update_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update approval flow"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in update_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== DELETE Endpoint (TFS: ApprovalFlowMaster.DELETE) ==========
@router.delete(
    "/{flow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Approval Flow",
    description="Soft delete an approval flow (TFS: ApprovalFlowMaster.DELETE)",
    responses={
        204: {"description": "Approval flow deleted successfully"},
        404: {"description": "Approval flow not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_approval_flow(
    flow_id: PyObjectId = Path(..., description="Approval Flow ID"),
    request: Request = ...
):
    """
    Soft delete approval flow.
    
    TFS Reference: ApprovalFlowMaster.DELETE
    RBAC Permission: PERM.APPROVAL_FLOW.DELETE.GLOBAL
    
    Purpose: Perform soft delete (is_deleted = true)
    
    Raises:
        404: Approval flow not found
        500: Database operation failed
    """
    try:
        deleted_by = get_current_user_id()
        deleted_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.DELETE.GLOBAL
        
        success = service.delete_approval_flow(flow_id, deleted_by, deleted_ip)
        
        if not success:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_FLOW.NOT_FOUND",
                    "message": f"Approval flow with ID {flow_id} not found"
                }
            )
        
        return None
        
    except ApprovalFlowNotFoundError as e:
        # ERROR: ERR.APPROVAL_FLOW.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.APPROVAL_FLOW.DELETE.DB_ERROR
        print(f"Database error in delete_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to delete approval flow"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in delete_approval_flow: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.DELETE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint (Extended TFS: ApprovalFlowMaster.READ) ==========
@router.get(
    "",
    response_model=ApprovalFlowMasterListResponseSchema,
    summary="Search Approval Flows",
    description="Search, filter, sort, and paginate approval flows (Extended TFS: ApprovalFlowMaster.READ)"
)
async def search_approval_flows(
    role: Optional[ApprovalRole] = Query(None, description="Filter by specific role in workflow"),
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted"),
    sort_by: str = Query("createdAt", description="Field to sort by", alias="sortBy"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)", alias="sortOrder"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page", alias="pageSize")
):
    """
    Search and filter approval flows with pagination.
    
    TFS Reference: ApprovalFlowMaster.READ (extended)
    RBAC Permission: PERM.APPROVAL_FLOW.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.READ.GLOBAL
        
        search_params = ApprovalFlowMasterSearchSchema(
            role=role,
            includeDeleted=include_deleted,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_approval_flows(search_params)
        
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "data": results,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages
        }
        
    except ValueError as e:
        # ERROR: Validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.APPROVAL_FLOW.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        print(f"Database error in search_approval_flows: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search approval flows"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in search_approval_flows: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET ALL Endpoint (Utility) ==========
@router.get(
    "/list/all",
    response_model=list[ApprovalFlowMasterResponseSchema],
    summary="Get All Approval Flows",
    description="Get all approval flows (for dropdowns)"
)
async def get_all_approval_flows(
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted")
):
    """Get all approval flows."""
    try:
        # TODO: Check RBAC permission: PERM.APPROVAL_FLOW.READ.GLOBAL
        
        results = service.get_all_approval_flows(include_deleted=include_deleted)
        return results
        
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve approval flows"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_all_approval_flows: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_FLOW.GET_ALL.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

"""
Purpose: FastAPI router for Approval Chain endpoints.
Provides RESTful API for approval chain operations and approval processing.

Handles approval tracking and workflow management for CrPC requests.
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path, Body
from typing import Optional, List
import traceback

from models.approval_chain_models import (
    ApprovalChainCreateSchema,
    ApprovalChainUpdateSchema,
    ApprovalChainResponseSchema,
    ApprovalChainListResponseSchema,
    ApprovalChainSearchSchema,
    ApprovalActionSchema,
)
from services.approval_chain_service import (
    ApprovalChainService,
    ApprovalChainNotFoundError,
    InvalidStepError,
    UnauthorizedApprovalError,
    AlreadyProcessedError,
    MissingRejectReasonError,
    DatabaseOperationError,
    ApprovalChainError,
)
from utils.validators import PyObjectId
from constants.value_sets import ApprovalChainStatus


router = APIRouter(
    prefix="/api/v1/approval-chains",
    tags=["Approval Chain"],
)

service = ApprovalChainService()


# ========== Helper Functions ==========
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def get_current_user_id() -> PyObjectId:
    """
    Get current authenticated user ID.
    TODO: Replace with actual JWT authentication
    """
    return PyObjectId("6710000000000000000000a4")


def get_current_user_role() -> str:
    """
    Get current authenticated user's role.
    TODO: Replace with actual JWT token extraction
    """
    return "SHO"  # Dummy role for now


# ========== CREATE Endpoint ==========
@router.post(
    "",
    response_model=ApprovalChainResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Approval Chain",
    description="Create a new approval chain (auto-created with pipeline)"
)
async def create_approval_chain(
    data: ApprovalChainCreateSchema,
    request: Request
):
    """
    Create approval chain.
    
    Note: Typically auto-created when pipeline is created.
    This endpoint is for manual creation if needed.
    """
    try:
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        result = service.create_approval_chain(data, created_by, created_ip)
        return result
        
    except InvalidStepError as e:
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
                "error": "ERR.APPROVAL_CHAIN.CREATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in create_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create approval chain"
            }
        )
    except Exception as e:
        print(f"Unexpected error in create_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint ==========
@router.get(
    "/{chain_id}",
    response_model=ApprovalChainResponseSchema,
    summary="Get Approval Chain by ID",
    description="Retrieve an approval chain by its ID"
)
async def get_approval_chain(
    chain_id: PyObjectId = Path(..., description="Approval Chain ID")
):
    """Get approval chain by ID."""
    try:
        result = service.get_approval_chain_by_id(chain_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_CHAIN.NOT_FOUND",
                    "message": f"Approval chain with ID {chain_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        print(f"Database error in get_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve approval chain"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET BY PIPELINE ID ==========
@router.get(
    "/pipeline/{pipeline_id}",
    response_model=ApprovalChainResponseSchema,
    summary="Get Approval Chain by Pipeline ID",
    description="Get approval chain for a specific pipeline"
)
async def get_by_pipeline_id(
    pipeline_id: PyObjectId = Path(..., description="Pipeline ID")
):
    """Get approval chain for a pipeline."""
    try:
        result = service.get_by_pipeline_id(pipeline_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_CHAIN.NOT_FOUND",
                    "message": f"Approval chain for pipeline {pipeline_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve approval chain"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_by_pipeline_id: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.GET_BY_PIPELINE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint ==========
@router.put(
    "/{chain_id}",
    response_model=ApprovalChainResponseSchema,
    summary="Update Approval Chain",
    description="Update an approval chain (use /approve or /reject instead for workflow actions)"
)
async def update_approval_chain(
    chain_id: PyObjectId = Path(..., description="Approval Chain ID"),
    data: ApprovalChainUpdateSchema = ...,
    request: Request = ...
):
    """Update approval chain (direct update - not recommended, use approve/reject endpoints)."""
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        result = service.update_approval_chain(chain_id, data, updated_by, updated_ip)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.APPROVAL_CHAIN.NOT_FOUND",
                    "message": f"Approval chain with ID {chain_id} not found"
                }
            )
        
        return result
        
    except ApprovalChainNotFoundError as e:
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
                "error": "ERR.APPROVAL_CHAIN.UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in update_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update approval chain"
            }
        )
    except Exception as e:
        print(f"Unexpected error in update_approval_chain: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== PROCESS APPROVAL/REJECTION ==========
@router.post(
    "/{chain_id}/process",
    response_model=ApprovalChainResponseSchema,
    summary="Process Approval/Rejection",
    description="Approve or reject an approval chain"
)
async def process_approval(
    chain_id: PyObjectId = Path(..., description="Approval Chain ID"),
    action_data: ApprovalActionSchema = Body(...),
    request: Request = ...
):
    """
    Process approval or rejection.
    
    Required: User must have permission for current step.
    """
    try:
        user_role = get_current_user_role()
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission based on role and step
        
        result = service.process_approval(
            chain_id,
            action_data,
            user_role,
            updated_by,
            updated_ip
        )
        
        return result
        
    except ApprovalChainNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except UnauthorizedApprovalError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except AlreadyProcessedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except MissingRejectReasonError as e:
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
                "error": "ERR.APPROVAL_CHAIN.PROCESS.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in process_approval: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to process approval"
            }
        )
    except Exception as e:
        print(f"Unexpected error in process_approval: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.PROCESS.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== BULK APPROVE ==========
@router.post(
    "/bulk-approve",
    summary="Bulk Approve",
    description="Approve multiple approval chains at once"
)
async def bulk_approve(
    chain_ids: List[PyObjectId] = Body(..., description="List of approval chain IDs"),
    comments: Optional[str] = Body(None, description="Optional comments"),
    request: Request = ...
):
    """Approve multiple approval chains."""
    try:
        user_role = get_current_user_role()
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission
        
        result = service.bulk_approve(
            chain_ids,
            user_role,
            updated_by,
            updated_ip,
            comments
        )
        
        return result
        
    except DatabaseOperationError as e:
        print(f"Database error in bulk_approve: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to process bulk approval"
            }
        )
    except Exception as e:
        print(f"Unexpected error in bulk_approve: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.BULK_APPROVE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET PENDING APPROVALS ==========
@router.get(
    "/pending/my-approvals",
    response_model=list[ApprovalChainResponseSchema],
    summary="Get My Pending Approvals",
    description="Get all approval chains pending for current user"
)
async def get_pending_approvals():
    """Get pending approvals for current user."""
    try:
        user_role = get_current_user_role()
        
        # TODO: Check RBAC permission
        
        results = service.get_pending_for_user(user_role)
        return results
        
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve pending approvals"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_pending_approvals: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.GET_PENDING.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint ==========
@router.get(
    "",
    response_model=ApprovalChainListResponseSchema,
    summary="Search Approval Chains",
    description="Search, filter, sort, and paginate approval chains"
)
async def search_approval_chains(
    crpc_request_pipeline_id: Optional[PyObjectId] = Query(None, alias="crpcRequestPipelineId"),
    approval_flow_id: Optional[PyObjectId] = Query(None, alias="approvalFlowId"),
    current_step: Optional[int] = Query(None, ge=1, le=6, alias="currentStep"),
    approval_chain_status: Optional[ApprovalChainStatus] = Query(None, alias="approvalChainStatus"),
    include_inactive: bool = Query(False, alias="includeInactive"),
    sort_by: str = Query("createdAt", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize")
):
    """Search and filter approval chains."""
    try:
        search_params = ApprovalChainSearchSchema(
            crpcRequestPipelineId=crpc_request_pipeline_id,
            approvalFlowId=approval_flow_id,
            currentStep=current_step,
            approvalChainStatus=approval_chain_status,
            includeInactive=include_inactive,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_approval_chains(search_params)
        
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
                "error": "ERR.APPROVAL_CHAIN.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        print(f"Database error in search_approval_chains: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search approval chains"
            }
        )
    except Exception as e:
        print(f"Unexpected error in search_approval_chains: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.APPROVAL_CHAIN.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

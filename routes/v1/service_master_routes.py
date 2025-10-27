"""
Purpose: FastAPI router for Service Master endpoints.
Provides RESTful API for CRUD operations, search, and filtering.

Based on TFS: ServiceMaster.CREATE, READ, UPDATE, DELETE
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path
from typing import Optional
import traceback

from models.service_master_models import (
    ServiceMasterCreateSchema,
    ServiceMasterUpdateSchema,
    ServiceMasterResponseSchema,
    ServiceMasterListResponseSchema,
    ServiceMasterSearchSchema,
)
from services.service_master_service import (
    ServiceMasterService,
    DuplicateServiceError,
    ServiceNotFoundError,
    InvalidOperatorTypeError,
    DatabaseOperationError,
    ServiceMasterError,
)
from utils.validators import PyObjectId


router = APIRouter(
    prefix="/api/v1/service-masters",
    tags=["Service Master"],
)

service = ServiceMasterService()


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


# ========== CREATE Endpoint (TFS: ServiceMaster.CREATE) ==========
@router.post(
    "",
    response_model=ServiceMasterResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Service Master",
    description="Create a new service master record (TFS: ServiceMaster.CREATE)",
    responses={
        201: {"description": "Service master created successfully"},
        400: {"description": "Validation error or duplicate service name"},
        500: {"description": "Internal server error"}
    }
)
async def create_service_master(
    data: ServiceMasterCreateSchema,
    request: Request
):
    """
    Create a new service master.
    
    TFS Reference: ServiceMaster.CREATE
    RBAC Permission: PERM.SERVICE_MASTER.CREATE.GLOBAL
    
    Raises:
        400: Duplicate service name or validation error
        500: Database operation failed
    """
    try:
        # Get current user and IP
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.CREATE.GLOBAL
        
        # Call service layer
        result = service.create_service_master(data, created_by, created_ip)
        return result
        
    except DuplicateServiceError as e:
        # ERROR: ERR.SERVICE_MASTER.CREATE.DUPLICATE
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "serviceName"
            }
        )
    except ValueError as e:
        # ERROR: Pydantic validation error (operator types, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.SERVICE_MASTER.CREATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.SERVICE_MASTER.CREATE.DB_ERROR
        # Log full traceback for debugging
        print(f"Database error in create_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create service master. Please try again later."
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in create_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint (TFS: ServiceMaster.READ) ==========
@router.get(
    "/{service_id}",
    response_model=ServiceMasterResponseSchema,
    summary="Get Service Master by ID",
    description="Retrieve a service master by its ID (TFS: ServiceMaster.READ)",
    responses={
        200: {"description": "Service master found"},
        404: {"description": "Service master not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_service_master(
    service_id: PyObjectId = Path(..., description="Service Master ID")
):
    """
    Get service master by ID.
    
    TFS Reference: ServiceMaster.READ
    RBAC Permission: PERM.SERVICE_MASTER.READ.GLOBAL
    
    Raises:
        404: Service not found
        500: Database operation failed
    """
    try:
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.READ.GLOBAL
        
        result = service.get_service_master_by_id(service_id)
        
        if not result:
            # ERROR: ERR.SERVICE_MASTER.READ.NOT_FOUND
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.SERVICE_MASTER.READ.NOT_FOUND",
                    "message": f"Service master with ID {service_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        # ERROR: ERR.SERVICE_MASTER.READ.DB_ERROR
        print(f"Database error in get_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve service master"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint (TFS: ServiceMaster.UPDATE) ==========
@router.put(
    "/{service_id}",
    response_model=ServiceMasterResponseSchema,
    summary="Update Service Master",
    description="Update an existing service master record (TFS: ServiceMaster.UPDATE)",
    responses={
        200: {"description": "Service master updated successfully"},
        400: {"description": "Validation error or duplicate service name"},
        404: {"description": "Service master not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_service_master(
    service_id: PyObjectId = Path(..., description="Service Master ID"),
    data: ServiceMasterUpdateSchema = ...,
    request: Request = ...
):
    """
    Update service master.
    
    TFS Reference: ServiceMaster.UPDATE
    RBAC Permission: PERM.SERVICE_MASTER.UPDATE.GLOBAL
    
    Raises:
        400: Duplicate service name or validation error
        404: Service not found
        500: Database operation failed
    """
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.UPDATE.GLOBAL
        
        result = service.update_service_master(service_id, data, updated_by, updated_ip)
        
        if not result:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.SERVICE_MASTER.NOT_FOUND",
                    "message": f"Service master with ID {service_id} not found"
                }
            )
        
        return result
        
    except ServiceNotFoundError as e:
        # ERROR: ERR.SERVICE_MASTER.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DuplicateServiceError as e:
        # ERROR: ERR.SERVICE_MASTER.UPDATE.DUPLICATE
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "serviceName"
            }
        )
    except ValueError as e:
        # ERROR: Validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.SERVICE_MASTER.UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.SERVICE_MASTER.UPDATE.DB_ERROR
        print(f"Database error in update_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update service master"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in update_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== DELETE Endpoint (TFS: ServiceMaster.DELETE) ==========
@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Service Master",
    description="Soft delete a service master record (TFS: ServiceMaster.DELETE)",
    responses={
        204: {"description": "Service master deleted successfully"},
        404: {"description": "Service master not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_service_master(
    service_id: PyObjectId = Path(..., description="Service Master ID"),
    request: Request = ...
):
    """
    Soft delete service master.
    
    TFS Reference: ServiceMaster.DELETE
    RBAC Permission: PERM.SERVICE_MASTER.DELETE.GLOBAL
    
    Raises:
        404: Service not found
        500: Database operation failed
    """
    try:
        deleted_by = get_current_user_id()
        deleted_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.DELETE.GLOBAL
        
        success = service.delete_service_master(service_id, deleted_by, deleted_ip)
        
        if not success:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.SERVICE_MASTER.NOT_FOUND",
                    "message": f"Service master with ID {service_id} not found"
                }
            )
        
        return None
        
    except ServiceNotFoundError as e:
        # ERROR: ERR.SERVICE_MASTER.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.SERVICE_MASTER.DELETE.DB_ERROR
        print(f"Database error in delete_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to delete service master"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in delete_service_master: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.DELETE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint (Extended TFS: ServiceMaster.READ) ==========
@router.get(
    "",
    response_model=ServiceMasterListResponseSchema,
    summary="Search Service Masters",
    description="Search, filter, sort, and paginate service masters (Extended TFS: ServiceMaster.READ)"
)
async def search_service_masters(
    service_name: Optional[str] = Query(None, description="Search by service name (partial match)", alias="serviceName"),
    operator_type: Optional[str] = Query(None, description="Filter by operator type", alias="operatorType"),
    can_be_consolidated: Optional[bool] = Query(None, description="Filter by consolidation capability", alias="canBeConsolidated"),
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted"),
    sort_by: str = Query("serviceName", description="Field to sort by", alias="sortBy"),
    sort_order: str = Query("asc", description="Sort order (asc or desc)", alias="sortOrder"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page", alias="pageSize")
):
    """
    Search and filter service masters with pagination.
    
    TFS Reference: ServiceMaster.READ (extended)
    RBAC Permission: PERM.SERVICE_MASTER.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.READ.GLOBAL
        
        search_params = ServiceMasterSearchSchema(
            serviceName=service_name,
            operatorType=operator_type,
            canBeConsolidated=can_be_consolidated,
            includeDeleted=include_deleted,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_service_masters(search_params)
        
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
                "error": "ERR.SERVICE_MASTER.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        print(f"Database error in search_service_masters: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search service masters"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in search_service_masters: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET ALL Endpoint (Utility) ==========
@router.get(
    "/list/all",
    response_model=list[ServiceMasterResponseSchema],
    summary="Get All Service Masters",
    description="Get all service masters (for dropdowns)"
)
async def get_all_service_masters(
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted")
):
    """Get all service masters."""
    try:
        # TODO: Check RBAC permission: PERM.SERVICE_MASTER.READ.GLOBAL
        
        results = service.get_all_service_masters(include_deleted=include_deleted)
        return results
        
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve service masters"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_all_service_masters: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.SERVICE_MASTER.GET_ALL.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

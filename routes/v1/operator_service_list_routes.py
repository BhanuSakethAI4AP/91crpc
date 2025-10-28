"""
Purpose: FastAPI router for Operator Service List endpoints.
Provides RESTful API for CRUD operations on operator-service mappings.

UPDATED: Operator-centric design with new exception names and endpoints.
Based on TFS: OperatorServiceList.CREATE, READ, UPDATE, DELETE
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path
from typing import Optional
import traceback

from models.operator_service_list_models import (
    OperatorServiceListCreateSchema,
    OperatorServiceListUpdateSchema,
    OperatorServiceListResponseSchema,
    OperatorServiceListListResponseSchema,
    OperatorServiceListSearchSchema,
    ServiceFormatResponseSchema,
)
from services.operator_service_list_service import (
    OperatorServiceListService,
    DuplicateOperatorMappingError,  # UPDATED: Was DuplicateOperatorFormatError
    OperatorServiceNotFoundError,
    InvalidServiceIdError,
    InvalidOperatorIdError,
    NoFormatAvailableError,  # NEW
    DatabaseOperationError,
    OperatorServiceListError,
)
from utils.validators import PyObjectId

router = APIRouter(
    prefix="/api/v1/operator-services",
    tags=["Operator Service List"],
)

service = OperatorServiceListService()


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
    return PyObjectId("6710000000000000000000a2")


# ========== CREATE Endpoint (TFS: OperatorServiceList.CREATE) ==========
@router.post(
    "",
    response_model=OperatorServiceListResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Operator Service Mapping",
    description="Create a new operator-service mapping record (TFS: OperatorServiceList.CREATE)",
    responses={
        201: {"description": "Operator service mapping created successfully"},
        400: {"description": "Validation error or duplicate mapping"},
        500: {"description": "Internal server error"}
    }
)
async def create_operator_service(
    data: OperatorServiceListCreateSchema,
    request: Request
):
    """
    Create a new operator service mapping (operator-centric).
    
    TFS Reference: OperatorServiceList.CREATE
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.CREATE.GLOBAL
    
    Preconditions:
        - operatorId exists in operators_list
        - all serviceIds exist in service_master
        - no duplicate operator mapping
        - format available for each service (global or specific)
    
    Raises:
        400: Validation error or duplicate mapping
        500: Database operation failed
    """
    try:
        # Get current user and IP
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.CREATE.GLOBAL
        
        # Call service layer
        result = service.create_operator_service(data, created_by, created_ip)
        return result
        
    except InvalidOperatorIdError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.INVALID_OPERATOR_ID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "operatorId"
            }
        )
    except InvalidServiceIdError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "services.serviceId"
            }
        )
    except DuplicateOperatorMappingError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.CREATE.DUPLICATE_OPERATOR
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except NoFormatAvailableError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.NO_FORMAT_AVAILABLE
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except ValueError as e:
        # ERROR: Pydantic validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.CREATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.CREATE.DB_ERROR
        print(f"Database error in create_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create operator service mapping. Please try again later."
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in create_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint (TFS: OperatorServiceList.READ) ==========
@router.get(
    "/{record_id}",
    response_model=OperatorServiceListResponseSchema,
    summary="Get Operator Service Mapping by ID",
    description="Retrieve an operator service mapping by its ID (TFS: OperatorServiceList.READ)",
    responses={
        200: {"description": "Operator service mapping found"},
        404: {"description": "Operator service mapping not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_operator_service(
    record_id: PyObjectId = Path(..., description="Operator Service Mapping ID")
):
    """
    Get operator service mapping by ID.
    
    TFS Reference: OperatorServiceList.READ
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
    
    Raises:
        404: Operator service mapping not found
        500: Database operation failed
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        result = service.get_operator_service_by_id(record_id)
        
        if not result:
            # ERROR: ERR.OPERATOR_SERVICE_LIST.READ.NOT_FOUND
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATOR_SERVICE_LIST.READ.NOT_FOUND",
                    "message": f"Operator service mapping with ID {record_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.READ.DB_ERROR
        print(f"Database error in get_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operator service mapping"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET BY OPERATOR ID (PRIMARY LOOKUP) ==========
@router.get(
    "/operator/{operator_id}",
    response_model=OperatorServiceListResponseSchema,
    summary="Get Operator Service Mapping by Operator ID",
    description="Get operator service mapping for a specific operator (PRIMARY LOOKUP)"
)
async def get_by_operator_id(
    operator_id: PyObjectId = Path(..., description="Operator ID")
):
    """
    Get operator service mapping for a specific operator.
    
    PRIMARY LOOKUP METHOD (operator-centric design).
    
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        result = service.get_by_operator_id(operator_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATOR_SERVICE_LIST.NOT_FOUND",
                    "message": f"No service mapping found for operator {operator_id}"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operator service mapping"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_by_operator_id: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.GET_BY_OPERATOR.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET FORMAT FOR SERVICE (NEW ENDPOINT) ==========
@router.get(
    "/operator/{operator_id}/service/{service_id}/format",
    response_model=ServiceFormatResponseSchema,
    summary="Get Format Configuration for Service",
    description="Get resolved format configuration for a specific operator-service combination"
)
async def get_format_for_service(
    operator_id: PyObjectId = Path(..., description="Operator ID"),
    service_id: PyObjectId = Path(..., description="Service ID")
):
    """
    Get the resolved format configuration for a specific operator-service combination.
    
    Resolution Logic:
    1. Find operator config
    2. Find service in services[]
    3. If serviceSpecificFormat exists, return it
    4. Else return globalFormat
    
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        result = service.get_format_for_service(operator_id, service_id)
        return result
        
    except OperatorServiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except InvalidServiceIdError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except NoFormatAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve format configuration"
            }
        )
    except Exception as e:
        print(f"Unexpected error in get_format_for_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.GET_FORMAT.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET OPERATORS FOR SERVICE ==========
@router.get(
    "/service/{service_id}/operators",
    response_model=list[OperatorServiceListResponseSchema],
    summary="Get Operators Providing a Service",
    description="Get all operators that provide a specific service"
)
async def get_operators_for_service(
    service_id: PyObjectId = Path(..., description="Service ID")
):
    """
    Get all operators that provide a specific service.
    
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        results = service.get_operators_for_service(service_id)
        return results
        
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operators"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_operators_for_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.GET_OPERATORS.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint (TFS: OperatorServiceList.UPDATE) ==========
@router.put(
    "/{record_id}",
    response_model=OperatorServiceListResponseSchema,
    summary="Update Operator Service Mapping",
    description="Update an existing operator service mapping (TFS: OperatorServiceList.UPDATE)",
    responses={
        200: {"description": "Operator service mapping updated successfully"},
        400: {"description": "Validation error"},
        404: {"description": "Operator service mapping not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_operator_service(
    record_id: PyObjectId = Path(..., description="Operator Service Mapping ID"),
    data: OperatorServiceListUpdateSchema = ...,
    request: Request = ...
):
    """
    Update operator service mapping.
    
    TFS Reference: OperatorServiceList.UPDATE
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.UPDATE.GLOBAL
    
    Raises:
        400: Validation error
        404: Operator service mapping not found
        500: Database operation failed
    """
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.UPDATE.GLOBAL
        
        result = service.update_operator_service(record_id, data, updated_by, updated_ip)
        
        if not result:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATOR_SERVICE_LIST.NOT_FOUND",
                    "message": f"Operator service mapping with ID {record_id} not found"
                }
            )
        
        return result
        
    except OperatorServiceNotFoundError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except InvalidServiceIdError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "services.serviceId"
            }
        )
    except ValueError as e:
        # ERROR: Validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.UPDATE.DB_ERROR
        print(f"Database error in update_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update operator service mapping"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in update_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== DELETE Endpoint (TFS: OperatorServiceList.DELETE) ==========
@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Operator Service Mapping",
    description="Soft delete an operator service mapping (TFS: OperatorServiceList.DELETE)",
    responses={
        204: {"description": "Operator service mapping deleted successfully"},
        404: {"description": "Operator service mapping not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_operator_service(
    record_id: PyObjectId = Path(..., description="Operator Service Mapping ID"),
    request: Request = ...
):
    """
    Soft delete operator service mapping.
    
    TFS Reference: OperatorServiceList.DELETE
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.DELETE.GLOBAL
    
    Raises:
        404: Operator service mapping not found
        500: Database operation failed
    """
    try:
        deleted_by = get_current_user_id()
        deleted_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.DELETE.GLOBAL
        
        success = service.delete_operator_service(record_id, deleted_by, deleted_ip)
        
        if not success:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATOR_SERVICE_LIST.NOT_FOUND",
                    "message": f"Operator service mapping with ID {record_id} not found"
                }
            )
        
        return None
        
    except OperatorServiceNotFoundError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATOR_SERVICE_LIST.DELETE.DB_ERROR
        print(f"Database error in delete_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to delete operator service mapping"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in delete_operator_service: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.DELETE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint (Extended TFS: OperatorServiceList.READ) ==========
@router.get(
    "",
    response_model=OperatorServiceListListResponseSchema,
    summary="Search Operator Service Mappings",
    description="Search, filter, sort, and paginate operator service mappings (Extended TFS: OperatorServiceList.READ)"
)
async def search_operator_services(
    operator_id: Optional[PyObjectId] = Query(None, description="Filter by operator ID", alias="operatorId"),
    service_id: Optional[PyObjectId] = Query(None, description="Filter by service ID (within services array)", alias="serviceId"),
    operator_name: Optional[str] = Query(None, description="Filter by operator name (partial match)", alias="operatorName"),
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted"),
    sort_by: str = Query("createdAt", description="Field to sort by", alias="sortBy"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)", alias="sortOrder"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page", alias="pageSize")
):
    """
    Search and filter operator service mappings with pagination.
    
    TFS Reference: OperatorServiceList.READ (extended)
    RBAC Permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        search_params = OperatorServiceListSearchSchema(
            operatorId=operator_id,
            serviceId=service_id,
            operatorName=operator_name,
            includeDeleted=include_deleted,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_operator_services(search_params)
        
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
                "error": "ERR.OPERATOR_SERVICE_LIST.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        print(f"Database error in search_operator_services: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search operator service mappings"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in search_operator_services: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET ALL Endpoint (Utility) ==========
@router.get(
    "/list/all",
    response_model=list[OperatorServiceListResponseSchema],
    summary="Get All Operator Service Mappings",
    description="Get all operator service mappings (for dropdowns)"
)
async def get_all_operator_services(
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted")
):
    """Get all operator service mappings."""
    try:
        # TODO: Check RBAC permission: PERM.OPERATOR_SERVICE_LIST.READ.GLOBAL
        
        results = service.get_all_operator_services(include_deleted=include_deleted)
        return results
        
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operator service mappings"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_all_operator_services: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATOR_SERVICE_LIST.GET_ALL.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

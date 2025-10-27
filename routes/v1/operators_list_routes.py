"""
Purpose: FastAPI router for Operators List endpoints.
Provides RESTful API for CRUD operations, search, and filtering.

Based on TFS: OperatorsList.CREATE, READ, UPDATE, DELETE
"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Path
from typing import Optional
import traceback

from models.operators_list_models import (
    OperatorsListCreateSchema,
    OperatorsListUpdateSchema,
    OperatorsListResponseSchema,
    OperatorsListListResponseSchema,
    OperatorsListSearchSchema,
)
from services.operators_list_service import (
    OperatorsListService,
    DuplicateOperatorError,
    OperatorNotFoundError,
    InvalidOperatorTypeError,
    DatabaseOperationError,
    OperatorsListError,
)
from utils.validators import PyObjectId
from constants.value_sets import OperatorType


router = APIRouter(
    prefix="/api/v1/operators",
    tags=["Operators List"],
)

service = OperatorsListService()


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


# ========== CREATE Endpoint (TFS: OperatorsList.CREATE) ==========
@router.post(
    "",
    response_model=OperatorsListResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create Operator",
    description="Create a new operator record (TFS: OperatorsList.CREATE)",
    responses={
        201: {"description": "Operator created successfully"},
        400: {"description": "Validation error or duplicate operator"},
        500: {"description": "Internal server error"}
    }
)
async def create_operator(
    data: OperatorsListCreateSchema,
    request: Request
):
    """
    Create a new operator.
    
    TFS Reference: OperatorsList.CREATE
    RBAC Permission: PERM.OPERATORS_LIST.CREATE.GLOBAL
    
    Preconditions:
        - operator_type must exist in 91CrPCOperatorType
        - operator_name must be unique within its type
    
    Raises:
        400: Duplicate operator or validation error
        500: Database operation failed
    """
    try:
        # Get current user and IP
        created_by = get_current_user_id()
        created_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.CREATE.GLOBAL
        
        # Call service layer
        result = service.create_operator(data, created_by, created_ip)
        return result
        
    except DuplicateOperatorError as e:
        # ERROR: ERR.OPERATORS_LIST.CREATE.DUPLICATE
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "operatorName"
            }
        )
    except ValueError as e:
        # ERROR: Pydantic validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.OPERATORS_LIST.CREATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATORS_LIST.CREATE.DB_ERROR
        # Log full traceback for debugging
        print(f"Database error in create_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to create operator. Please try again later."
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in create_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.CREATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== READ Endpoint (TFS: OperatorsList.READ) ==========
@router.get(
    "/{operator_id}",
    response_model=OperatorsListResponseSchema,
    summary="Get Operator by ID",
    description="Retrieve an operator by its ID (TFS: OperatorsList.READ)",
    responses={
        200: {"description": "Operator found"},
        404: {"description": "Operator not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_operator(
    operator_id: PyObjectId = Path(..., description="Operator ID")
):
    """
    Get operator by ID.
    
    TFS Reference: OperatorsList.READ
    RBAC Permission: PERM.OPERATORS_LIST.READ.GLOBAL
    
    Raises:
        404: Operator not found
        500: Database operation failed
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.READ.GLOBAL
        
        result = service.get_operator_by_id(operator_id)
        
        if not result:
            # ERROR: ERR.OPERATORS_LIST.READ.NOT_FOUND
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATORS_LIST.READ.NOT_FOUND",
                    "message": f"Operator with ID {operator_id} not found"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATORS_LIST.READ.DB_ERROR
        print(f"Database error in get_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operator"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.READ.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== UPDATE Endpoint (TFS: OperatorsList.UPDATE) ==========
@router.put(
    "/{operator_id}",
    response_model=OperatorsListResponseSchema,
    summary="Update Operator",
    description="Update an existing operator record (TFS: OperatorsList.UPDATE)",
    responses={
        200: {"description": "Operator updated successfully"},
        400: {"description": "Validation error or duplicate operator"},
        404: {"description": "Operator not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_operator(
    operator_id: PyObjectId = Path(..., description="Operator ID"),
    data: OperatorsListUpdateSchema = ...,
    request: Request = ...
):
    """
    Update operator.
    
    TFS Reference: OperatorsList.UPDATE
    RBAC Permission: PERM.OPERATORS_LIST.UPDATE.GLOBAL
    
    Raises:
        400: Duplicate operator or validation error
        404: Operator not found
        500: Database operation failed
    """
    try:
        updated_by = get_current_user_id()
        updated_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.UPDATE.GLOBAL
        
        result = service.update_operator(operator_id, data, updated_by, updated_ip)
        
        if not result:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATORS_LIST.NOT_FOUND",
                    "message": f"Operator with ID {operator_id} not found"
                }
            )
        
        return result
        
    except OperatorNotFoundError as e:
        # ERROR: ERR.OPERATORS_LIST.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DuplicateOperatorError as e:
        # ERROR: ERR.OPERATORS_LIST.UPDATE.DUPLICATE
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": "operatorName"
            }
        )
    except ValueError as e:
        # ERROR: Validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ERR.OPERATORS_LIST.UPDATE.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATORS_LIST.UPDATE.DB_ERROR
        print(f"Database error in update_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to update operator"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in update_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.UPDATE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== DELETE Endpoint (TFS: OperatorsList.DELETE) ==========
@router.delete(
    "/{operator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Operator",
    description="Soft delete an operator record (TFS: OperatorsList.DELETE)",
    responses={
        204: {"description": "Operator deleted successfully"},
        404: {"description": "Operator not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_operator(
    operator_id: PyObjectId = Path(..., description="Operator ID"),
    request: Request = ...
):
    """
    Soft delete operator.
    
    TFS Reference: OperatorsList.DELETE
    RBAC Permission: PERM.OPERATORS_LIST.DELETE.GLOBAL
    
    Raises:
        404: Operator not found
        500: Database operation failed
    """
    try:
        deleted_by = get_current_user_id()
        deleted_ip = get_client_ip(request)
        
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.DELETE.GLOBAL
        
        success = service.delete_operator(operator_id, deleted_by, deleted_ip)
        
        if not success:
            # This shouldn't happen due to service layer error handling
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ERR.OPERATORS_LIST.NOT_FOUND",
                    "message": f"Operator with ID {operator_id} not found"
                }
            )
        
        return None
        
    except OperatorNotFoundError as e:
        # ERROR: ERR.OPERATORS_LIST.NOT_FOUND
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    except DatabaseOperationError as e:
        # ERROR: ERR.OPERATORS_LIST.DELETE.DB_ERROR
        print(f"Database error in delete_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to delete operator"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in delete_operator: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.DELETE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== SEARCH Endpoint (Extended TFS: OperatorsList.READ) ==========
@router.get(
    "",
    response_model=OperatorsListListResponseSchema,
    summary="Search Operators",
    description="Search, filter, sort, and paginate operators (Extended TFS: OperatorsList.READ)"
)
async def search_operators(
    operator_name: Optional[str] = Query(None, description="Search by operator name (partial match)", alias="operatorName"),
    operator_type: Optional[OperatorType] = Query(None, description="Filter by operator type", alias="operatorType"),
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted"),
    sort_by: str = Query("operatorName", description="Field to sort by", alias="sortBy"),
    sort_order: str = Query("asc", description="Sort order (asc or desc)", alias="sortOrder"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page", alias="pageSize")
):
    """
    Search and filter operators with pagination.
    
    TFS Reference: OperatorsList.READ (extended)
    RBAC Permission: PERM.OPERATORS_LIST.READ.GLOBAL
    """
    try:
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.READ.GLOBAL
        
        search_params = OperatorsListSearchSchema(
            operatorName=operator_name,
            operatorType=operator_type,
            includeDeleted=include_deleted,
            sortBy=sort_by,
            sortOrder=sort_order,
            page=page,
            pageSize=page_size
        )
        
        results, total = service.search_operators(search_params)
        
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
                "error": "ERR.OPERATORS_LIST.SEARCH.VALIDATION",
                "message": str(e)
            }
        )
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        print(f"Database error in search_operators: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to search operators"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in search_operators: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.SEARCH.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET ALL Endpoint (Utility) ==========
@router.get(
    "/list/all",
    response_model=list[OperatorsListResponseSchema],
    summary="Get All Operators",
    description="Get all operators (for dropdowns)"
)
async def get_all_operators(
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted")
):
    """Get all operators."""
    try:
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.READ.GLOBAL
        
        results = service.get_all_operators(include_deleted=include_deleted)
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
        print(f"Unexpected error in get_all_operators: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.GET_ALL.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )


# ========== GET BY TYPE Endpoint (Utility) ==========
@router.get(
    "/by-type/{operator_type}",
    response_model=list[OperatorsListResponseSchema],
    summary="Get Operators by Type",
    description="Get all operators of a specific type (Telecom, Bank, ISP)"
)
async def get_operators_by_type(
    operator_type: OperatorType = Path(..., description="Operator type to filter by"),
    include_deleted: bool = Query(False, description="Include soft-deleted records", alias="includeDeleted")
):
    """Get operators by type."""
    try:
        # TODO: Check RBAC permission: PERM.OPERATORS_LIST.READ.GLOBAL
        
        results = service.get_operators_by_type(operator_type, include_deleted=include_deleted)
        return results
        
    except DatabaseOperationError as e:
        # ERROR: Database operation failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": "Failed to retrieve operators by type"
            }
        )
    except Exception as e:
        # ERROR: Unexpected error
        print(f"Unexpected error in get_operators_by_type: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERR.OPERATORS_LIST.GET_BY_TYPE.UNEXPECTED",
                "message": "An unexpected error occurred"
            }
        )

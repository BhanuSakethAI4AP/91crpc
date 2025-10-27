"""
Purpose: Pydantic schemas for Approval Flow Master CRUD operations.
Handles validation and serialization for approval workflow definitions.

Based on TFS: ApprovalFlowMaster.CREATE, READ, UPDATE, DELETE
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import ApprovalRole


# ========== Approval Step Schema ==========
class ApprovalStepSchema(BaseModel):
    """
    Individual approval step in the workflow.
    Defines role and order for each approval level.
    """
    role: ApprovalRole = Field(
        ...,
        description="Approval role (IO, SHO, CI, DSP, Admin ASP, SP)",
        examples=["SP", "ASP", "DSP"]
    )
    order: int = Field(
        ...,
        ge=1,
        description="Order/sequence of this approval step (must be >= 1)",
        examples=[1, 2, 3]
    )


# ========== Base Schema ==========
class ApprovalFlowMasterBase(BaseModel):
    """
    Base schema with common fields for Approval Flow Master.
    Defines the ordered sequence of approval roles in a workflow.
    """
    steps: List[ApprovalStepSchema] = Field(
        ...,
        min_items=1,
        description="List of approval steps in sequential order"
    )

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v: List[ApprovalStepSchema]) -> List[ApprovalStepSchema]:
        """
        Validate approval steps for uniqueness and sequential ordering.
        
        TFS Preconditions:
            - Steps array must not be empty (handled by min_items=1)
            - Each role must exist in Enum(ApprovalRoles) (handled by Pydantic enum)
            - Orders must be unique and sequential
        
        Raises:
            ValueError: If orders are not unique or not sequential
        """
        if not v:
            raise ValueError("ERR.APPROVAL_FLOW.EMPTY_STEPS: Steps array cannot be empty")
        
        # Check for unique orders
        orders = [step.order for step in v]
        if len(orders) != len(set(orders)):
            raise ValueError("ERR.APPROVAL_FLOW.INVALID_ORDER: Order numbers must be unique")
        
        # Check for sequential orders (1, 2, 3, ... n)
        sorted_orders = sorted(orders)
        expected_orders = list(range(1, len(orders) + 1))
        if sorted_orders != expected_orders:
            raise ValueError(
                f"ERR.APPROVAL_FLOW.INVALID_ORDER: Orders must be sequential starting from 1. "
                f"Expected {expected_orders}, got {sorted_orders}"
            )
        
        # Check for duplicate roles
        roles = [step.role.value for step in v]
        if len(roles) != len(set(roles)):
            raise ValueError("ERR.APPROVAL_FLOW.DUPLICATE_ROLE: Roles must be unique in the workflow")
        
        return v


# ========== Create Schema (TFS: ApprovalFlowMaster.CREATE) ==========
class ApprovalFlowMasterCreateSchema(ApprovalFlowMasterBase):
    """
    Schema for creating a new approval flow master record.
    
    TFS Reference: ApprovalFlowMaster.CREATE
    Preconditions:
        - Steps array must not be empty
        - Each role must exist in Enum(ApprovalRoles)
        - Orders must be unique and sequential
    """
    pass


# ========== Update Schema (TFS: ApprovalFlowMaster.UPDATE) ==========
class ApprovalFlowMasterUpdateSchema(BaseModel):
    """
    Schema for updating an existing approval flow master record.
    
    TFS Reference: ApprovalFlowMaster.UPDATE
    Allows modification of steps or reordering of roles.
    """
    steps: List[ApprovalStepSchema] = Field(
        ...,
        min_items=1,
        description="Updated list of approval steps"
    )

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v: List[ApprovalStepSchema]) -> List[ApprovalStepSchema]:
        """Validate steps using same rules as create."""
        if not v:
            raise ValueError("ERR.APPROVAL_FLOW.EMPTY_STEPS: Steps array cannot be empty")
        
        # Check for unique orders
        orders = [step.order for step in v]
        if len(orders) != len(set(orders)):
            raise ValueError("ERR.APPROVAL_FLOW.INVALID_ORDER: Order numbers must be unique")
        
        # Check for sequential orders
        sorted_orders = sorted(orders)
        expected_orders = list(range(1, len(orders) + 1))
        if sorted_orders != expected_orders:
            raise ValueError(
                f"ERR.APPROVAL_FLOW.INVALID_ORDER: Orders must be sequential starting from 1"
            )
        
        # Check for duplicate roles
        roles = [step.role.value for step in v]
        if len(roles) != len(set(roles)):
            raise ValueError("ERR.APPROVAL_FLOW.DUPLICATE_ROLE: Roles must be unique")
        
        return v


# ========== Response Schema (TFS: All Operations) ==========
class ApprovalFlowMasterResponseSchema(ApprovalFlowMasterBase):
    """
    Schema for approval flow master responses (includes metadata).
    
    TFS Reference: ApprovalFlowMaster.CREATE/READ/UPDATE/DELETE outputs
    """
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    isDeleted: bool = Field(default=False, description="Soft delete flag")
    createdAt: datetime = Field(..., description="Creation timestamp")
    createdBy: PyObjectId = Field(..., description="User ID who created this record")
    createdIp: str = Field(..., description="IP address of creator")
    updatedAt: datetime = Field(..., description="Last update timestamp")
    updatedBy: PyObjectId = Field(..., description="User ID who last updated this record")
    updatedIp: str = Field(..., description="IP address of last updater")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "671000000000000000000401",
                "steps": [
                    {"role": "SP", "order": 1},
                    {"role": "ASP", "order": 2},
                    {"role": "DSP", "order": 3}
                ],
                "isDeleted": False,
                "createdAt": "2025-08-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a1",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a1",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema (TFS: ApprovalFlowMaster.READ) ==========
class ApprovalFlowMasterSearchSchema(BaseModel):
    """
    Schema for searching and filtering approval flow masters.
    
    TFS Reference: ApprovalFlowMaster.READ
    Supports filtering by role, includeDeleted
    """
    role: Optional[ApprovalRole] = Field(
        None,
        description="Filter by specific role in the workflow"
    )
    includeDeleted: bool = Field(
        default=False,
        description="Include soft-deleted records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="createdAt",
        description="Field to sort by (createdAt, updatedAt)"
    )
    sortOrder: str = Field(
        default="desc",
        description="Sort order: asc or desc"
    )
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(default=25, ge=1, le=100, description="Items per page (1-100)")

    @field_validator('sortBy')
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        """Validate sort field is allowed."""
        allowed_fields = {"createdAt", "updatedAt"}
        if v not in allowed_fields:
            raise ValueError(f"sortBy must be one of {allowed_fields}")
        return v

    @field_validator('sortOrder')
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        """Validate sort order."""
        if v.lower() not in {"asc", "desc"}:
            raise ValueError("sortOrder must be 'asc' or 'desc'")
        return v.lower()


# ========== List Response Schema ==========
class ApprovalFlowMasterListResponseSchema(BaseModel):
    """Paginated response schema for approval flow master list."""
    data: List[ApprovalFlowMasterResponseSchema] = Field(..., description="List of approval flows")
    total: int = Field(..., description="Total number of records matching criteria")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")

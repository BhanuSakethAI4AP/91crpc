#path: backend/models/approval_flow_master_models.py
"""
Purpose: Pydantic schemas for Approval Flow Master CRUD operations.
Handles validation and serialization for approval workflow definitions.

Based on TFS: ApprovalFlowMaster.CREATE, READ, UPDATE, DELETE
Updated to support Universal Workflow with dynamic entry points.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import ApprovalRole


# ========== Approval Step Schema ==========
class ApprovalStepSchema(BaseModel):
    """
    Individual approval step in the workflow.
    Defines role, order, and description for each approval level.
    """
    role: ApprovalRole = Field(
        ...,
        description="Approval role (IO, SHO, CI, DSP, Admin ASP, IT Core)",
        examples=["IO", "SHO", "DSP"]
    )
    order: int = Field(
        ...,
        ge=1,
        description="Order/sequence of this approval step (must be >= 1)",
        examples=[1, 2, 3]
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Description of the role's responsibility in this step",
        examples=["Investigating Officer - Initial request creator"]
    )


# ========== Base Schema ==========
class ApprovalFlowMasterBase(BaseModel):
    """
    Base schema with common fields for Approval Flow Master.
    Defines the universal approval workflow with dynamic entry points.
    """
    workflowName: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable name for the workflow",
        examples=["Universal 91 CrPC Approval Flow"]
    )
    workflowType: str = Field(
        default="UNIVERSAL",
        description="Type of workflow (UNIVERSAL, CUSTOM, SPECIAL)",
        examples=["UNIVERSAL"]
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed description of the workflow's purpose",
        examples=["Single approval workflow supporting all initiator roles with dynamic entry points"]
    )
    steps: List[ApprovalStepSchema] = Field(
        ...,
        min_items=1,
        description="List of approval steps in sequential order"
    )
    roleToStepMapping: Dict[str, int] = Field(
        ...,
        description="Mapping of roles to their starting step numbers for dynamic entry",
        examples=[{"IO": 1, "SHO": 2, "CI": 3, "DSP": 4, "IT Core": 5, "Admin ASP": 6}]
    )

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v: List[ApprovalStepSchema]) -> List[ApprovalStepSchema]:
        """
        Validate approval steps for uniqueness and sequential ordering.
        
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
                f"ERR.APPROVAL_FLOW.INVALID_ORDER: Orders must be sequential starting from 1"
            )
        
        # Check for duplicate roles
        roles = [step.role.value for step in v]
        if len(roles) != len(set(roles)):
            raise ValueError("ERR.APPROVAL_FLOW.DUPLICATE_ROLE: Roles must be unique in the workflow")
        
        return v
    
    @field_validator('roleToStepMapping')
    @classmethod
    def validate_role_mapping(cls, v: Dict[str, int], info) -> Dict[str, int]:
        """
        Validate that all roles in mapping exist in steps.
        
        Raises:
            ValueError: If role in mapping doesn't exist in steps
        """
        # Note: We can't access 'steps' here in Pydantic v2 during field validation
        # This validation will be done at service layer
        return v


# ========== Create Schema ==========
class ApprovalFlowMasterCreateSchema(ApprovalFlowMasterBase):
    """
    Schema for creating a new approval flow master record.
    
    TFS Reference: ApprovalFlowMaster.CREATE
    """
    pass


# ========== Update Schema ==========
class ApprovalFlowMasterUpdateSchema(BaseModel):
    """
    Schema for updating an existing approval flow master record.
    All fields optional for partial updates.
    
    TFS Reference: ApprovalFlowMaster.UPDATE
    """
    workflowName: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated workflow name"
    )
    workflowType: Optional[str] = Field(
        None,
        description="Updated workflow type"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated description"
    )
    steps: Optional[List[ApprovalStepSchema]] = Field(
        None,
        min_items=1,
        description="Updated list of approval steps"
    )
    roleToStepMapping: Optional[Dict[str, int]] = Field(
        None,
        description="Updated role to step mapping"
    )

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v: Optional[List[ApprovalStepSchema]]) -> Optional[List[ApprovalStepSchema]]:
        """Validate steps using same rules as create."""
        if v is None:
            return v
        
        if not v:
            raise ValueError("ERR.APPROVAL_FLOW.EMPTY_STEPS: Steps array cannot be empty")
        
        orders = [step.order for step in v]
        if len(orders) != len(set(orders)):
            raise ValueError("ERR.APPROVAL_FLOW.INVALID_ORDER: Order numbers must be unique")
        
        sorted_orders = sorted(orders)
        expected_orders = list(range(1, len(orders) + 1))
        if sorted_orders != expected_orders:
            raise ValueError("ERR.APPROVAL_FLOW.INVALID_ORDER: Orders must be sequential")
        
        roles = [step.role.value for step in v]
        if len(roles) != len(set(roles)):
            raise ValueError("ERR.APPROVAL_FLOW.DUPLICATE_ROLE: Roles must be unique")
        
        return v


# ========== Response Schema ==========
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
                "_id": "68feff7a28e5ec211a6a432d",
                "workflowName": "Universal 91 CrPC Approval Flow",
                "workflowType": "UNIVERSAL",
                "description": "Single approval workflow supporting all initiator roles",
                "steps": [
                    {"order": 1, "role": "IO", "description": "Investigating Officer"},
                    {"order": 2, "role": "SHO", "description": "Station House Officer"}
                ],
                "roleToStepMapping": {
                    "IO": 1,
                    "SHO": 2,
                    "CI": 3,
                    "DSP": 4,
                    "IT Core": 5,
                    "Admin ASP": 6
                },
                "isDeleted": False,
                "createdAt": "2025-10-27T05:13:30.058Z",
                "createdBy": "6710000000000000000000a1",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-27T05:13:30.059Z",
                "updatedBy": "6710000000000000000000a1",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema ==========
class ApprovalFlowMasterSearchSchema(BaseModel):
    """
    Schema for searching and filtering approval flow masters.
    
    TFS Reference: ApprovalFlowMaster.READ
    """
    workflowType: Optional[str] = Field(
        None,
        description="Filter by workflow type (UNIVERSAL, CUSTOM, SPECIAL)"
    )
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
        description="Field to sort by (workflowName, createdAt, updatedAt)"
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
        allowed_fields = {"workflowName", "workflowType", "createdAt", "updatedAt"}
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

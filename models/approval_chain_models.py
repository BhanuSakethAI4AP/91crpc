"""
Purpose: Pydantic schemas for Approval Chain CRUD operations.
Handles validation and serialization for approval chain tracking.

Tracks step-by-step approval progress for each CrPC request pipeline item.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import ApprovalChainStatus


# ========== Base Schema ==========
class ApprovalChainBase(BaseModel):
    """
    Base schema with common fields for Approval Chain.
    Tracks approval progress through the workflow.
    """
    crpcRequestPipelineId: PyObjectId = Field(
        ...,
        description="Reference to the pipeline item being approved"
    )
    approvalFlowId: PyObjectId = Field(
        ...,
        description="Reference to the universal approval workflow"
    )
    currentStep: int = Field(
        ...,
        ge=1,
        le=6,
        description="Current step in the approval workflow (1-6)"
    )
    approvalChainStatus: ApprovalChainStatus = Field(
        default=ApprovalChainStatus.PENDING,
        description="Current status of the approval chain"
    )
    rejectReason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Reason for rejection (required if status is Reject)"
    )

    @field_validator('rejectReason')
    @classmethod
    def validate_reject_reason(cls, v: Optional[str], info) -> Optional[str]:
        """
        Validate that reject reason is provided when status is Reject.
        
        Note: This validator runs before we can check approvalChainStatus,
        so the actual validation happens in the service layer.
        """
        return v


# ========== Create Schema ==========
class ApprovalChainCreateSchema(ApprovalChainBase):
    """
    Schema for creating a new approval chain.
    
    Auto-created when a CrPC request pipeline is created.
    """
    pass


# ========== Update Schema ==========
class ApprovalChainUpdateSchema(BaseModel):
    """
    Schema for updating an approval chain.
    Used when processing approvals/rejections.
    """
    currentStep: Optional[int] = Field(
        None,
        ge=1,
        le=6,
        description="Updated current step"
    )
    approvalChainStatus: Optional[ApprovalChainStatus] = Field(
        None,
        description="Updated status"
    )
    rejectReason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Rejection reason (required if rejecting)"
    )


# ========== Approval Action Schema ==========
class ApprovalActionSchema(BaseModel):
    """
    Schema for processing an approval or rejection.
    Used in approval endpoints.
    """
    action: str = Field(
        ...,
        description="Action to perform (APPROVE or REJECT)"
    )
    comments: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional comments for this approval/rejection"
    )
    rejectReason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Required if action is REJECT"
    )

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is APPROVE or REJECT."""
        if v.upper() not in ["APPROVE", "REJECT"]:
            raise ValueError("Action must be either 'APPROVE' or 'REJECT'")
        return v.upper()
    
    @field_validator('rejectReason')
    @classmethod
    def validate_reject_reason(cls, v: Optional[str], info) -> Optional[str]:
        """Validate reject reason is provided if action is REJECT."""
        # Note: Full validation happens in service layer
        return v


# ========== Response Schema ==========
class ApprovalChainResponseSchema(ApprovalChainBase):
    """
    Schema for approval chain responses (includes metadata).
    """
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    isActive: bool = Field(default=True, description="Active flag")
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
                "_id": "671000000000000000000701",
                "crpcRequestPipelineId": "671000000000000000000601",
                "approvalFlowId": "68feff7a28e5ec211a6a432d",
                "currentStep": 2,
                "approvalChainStatus": "Pending",
                "rejectReason": None,
                "isActive": True,
                "createdAt": "2025-09-15T10:00:00.000Z",
                "createdBy": "6710000000000000000000a4",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a4",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema ==========
class ApprovalChainSearchSchema(BaseModel):
    """
    Schema for searching and filtering approval chains.
    """
    crpcRequestPipelineId: Optional[PyObjectId] = Field(
        None,
        description="Filter by pipeline ID"
    )
    approvalFlowId: Optional[PyObjectId] = Field(
        None,
        description="Filter by workflow ID"
    )
    currentStep: Optional[int] = Field(
        None,
        ge=1,
        le=6,
        description="Filter by current step"
    )
    approvalChainStatus: Optional[ApprovalChainStatus] = Field(
        None,
        description="Filter by status"
    )
    includeInactive: bool = Field(
        default=False,
        description="Include inactive records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="createdAt",
        description="Field to sort by"
    )
    sortOrder: str = Field(
        default="desc",
        description="Sort order: asc or desc"
    )
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    pageSize: int = Field(default=25, ge=1, le=100, description="Items per page")

    @field_validator('sortBy')
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        """Validate sort field."""
        allowed_fields = {"currentStep", "approvalChainStatus", "createdAt", "updatedAt"}
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
class ApprovalChainListResponseSchema(BaseModel):
    """Paginated response schema for approval chain list."""
    data: List[ApprovalChainResponseSchema] = Field(..., description="List of approval chains")
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")


# ========== Approval History Entry Schema ==========
class ApprovalHistoryEntrySchema(BaseModel):
    """
    Schema for a single approval history entry.
    Tracks each approval/rejection action.
    """
    step: int = Field(..., description="Workflow step number")
    role: str = Field(..., description="Role that performed the action")
    action: str = Field(..., description="APPROVE or REJECT")
    approvedBy: PyObjectId = Field(..., description="User who performed the action")
    timestamp: datetime = Field(..., description="When the action occurred")
    comments: Optional[str] = Field(None, description="Optional comments")
    rejectReason: Optional[str] = Field(None, description="Rejection reason if rejected")


# ========== Pending Approvals Response Schema ==========
class PendingApprovalsResponseSchema(BaseModel):
    """
    Schema for pending approvals response.
    Shows items pending approval for current user.
    """
    pipelineId: PyObjectId = Field(..., description="Pipeline ID")
    approvalChainId: PyObjectId = Field(..., description="Approval chain ID")
    requestId: PyObjectId = Field(..., description="CrPC request ID")
    currentStep: int = Field(..., description="Current step")
    serviceName: str = Field(..., description="Service name")
    operatorName: str = Field(..., description="Operator name")
    keyFieldValue: str = Field(..., description="Key field value")
    requestedBy: str = Field(..., description="Name of requester")
    requestDate: datetime = Field(..., description="Request creation date")

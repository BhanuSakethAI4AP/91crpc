"""
Purpose: Pydantic schemas for CrPC Request Pipelines CRUD operations.
Handles validation and serialization for pipeline line items.

Each pipeline represents one service request to one operator.
Auto-generated from parent CrPC request's serviceList.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import LineItemRequestStatus


# ========== Required Data Schema ==========
class RequiredDataSchema(BaseModel):
    """
    Dynamic required data per service.
    Structure varies by service type (CDR, IPDR, Banking, etc.)
    """
    fromDate: Optional[str] = Field(None, description="Start date for data request")
    toDate: Optional[str] = Field(None, description="End date for data request")
    
    # Additional fields can be added dynamically
    class Config:
        extra = "allow"  # Allow additional fields beyond those defined


# ========== Base Schema ==========
class CrpcRequestPipelineBase(BaseModel):
    """
    Base schema for CrPC Request Pipeline.
    Represents one service request to one operator.
    """
    crpcRequestId: PyObjectId = Field(
        ...,
        description="Reference to parent CrPC request"
    )
    lineItem: int = Field(
        ...,
        ge=1,
        description="Line item number from parent request's serviceList"
    )
    operatorId: PyObjectId = Field(
        ...,
        description="Operator assigned for this service (auto-detected or manual)"
    )
    serviceId: PyObjectId = Field(
        ...,
        description="Service type (CDR, IPDR, Banking, etc.)"
    )
    keyFieldValue: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Identifier value (phone number, account number, IMEI, etc.)"
    )
    requiredData: Dict[str, Any] = Field(
        ...,
        description="Additional data required for this service (dates, account info, etc.)"
    )
    lineItemRequestStatus: LineItemRequestStatus = Field(
        default=LineItemRequestStatus.ON_APPROVAL_QUEUE,
        description="Current status of this pipeline item"
    )


# ========== Create Schema ==========
class CrpcRequestPipelineCreateSchema(CrpcRequestPipelineBase):
    """
    Schema for creating a new pipeline.
    Auto-created when parent CrPC request is created.
    """
    pass


# ========== Update Schema ==========
class CrpcRequestPipelineUpdateSchema(BaseModel):
    """
    Schema for updating a pipeline.
    Typically used by IT Core to update status or add data.
    """
    operatorId: Optional[PyObjectId] = Field(
        None,
        description="Updated operator (if changed)"
    )
    requiredData: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated required data"
    )
    lineItemRequestStatus: Optional[LineItemRequestStatus] = Field(
        None,
        description="Updated status"
    )


# ========== Response Schema ==========
class CrpcRequestPipelineResponseSchema(CrpcRequestPipelineBase):
    """
    Schema for pipeline responses (includes metadata).
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
                "_id": "671000000000000000000601",
                "crpcRequestId": "671000000000000000000501",
                "lineItem": 1,
                "operatorId": "671000000000000000000201",
                "serviceId": "671000000000000000000101",
                "keyFieldValue": "9876543210",
                "requiredData": {
                    "fromDate": "2025-09-01",
                    "toDate": "2025-09-30"
                },
                "lineItemRequestStatus": "OnApprovalQueue",
                "isActive": True,
                "createdAt": "2025-09-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a2",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a2",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema ==========
class CrpcRequestPipelineSearchSchema(BaseModel):
    """
    Schema for searching and filtering pipelines.
    """
    crpcRequestId: Optional[PyObjectId] = Field(
        None,
        description="Filter by parent request ID"
    )
    operatorId: Optional[PyObjectId] = Field(
        None,
        description="Filter by operator"
    )
    serviceId: Optional[PyObjectId] = Field(
        None,
        description="Filter by service type"
    )
    lineItemRequestStatus: Optional[LineItemRequestStatus] = Field(
        None,
        description="Filter by status"
    )
    keyFieldValue: Optional[str] = Field(
        None,
        description="Search by key field value (phone, account, etc.)"
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
        allowed_fields = {
            "lineItem", "lineItemRequestStatus", 
            "keyFieldValue", "createdAt", "updatedAt"
        }
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
class CrpcRequestPipelineListResponseSchema(BaseModel):
    """Paginated response schema for pipeline list."""
    data: List[CrpcRequestPipelineResponseSchema] = Field(..., description="List of pipelines")
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")


# ========== Pipeline with Details Schema ==========
class CrpcRequestPipelineWithDetailsSchema(CrpcRequestPipelineResponseSchema):
    """
    Extended pipeline schema with joined data.
    Includes service name, operator name, approval status, etc.
    """
    serviceName: Optional[str] = Field(None, description="Service name from service_master")
    operatorName: Optional[str] = Field(None, description="Operator name from operators_list")
    approvalChainStatus: Optional[str] = Field(None, description="Current approval status")
    currentApprovalStep: Optional[int] = Field(None, description="Current step in approval chain")
    
    class Config:
        populate_by_name = True


# ========== Bulk Update Schema ==========
class BulkPipelineUpdateSchema(BaseModel):
    """
    Schema for bulk updating multiple pipelines.
    Used by IT Core to update multiple items at once.
    """
    pipelineIds: List[PyObjectId] = Field(
        ...,
        min_items=1,
        description="List of pipeline IDs to update"
    )
    updates: Dict[str, Any] = Field(
        ...,
        description="Fields to update (e.g., status, operator)"
    )


# ========== Status Update Schema ==========
class PipelineStatusUpdateSchema(BaseModel):
    """
    Schema for updating pipeline status.
    Simple status change endpoint.
    """
    lineItemRequestStatus: LineItemRequestStatus = Field(
        ...,
        description="New status for the pipeline"
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional notes for this status change"
    )

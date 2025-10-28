"""
Purpose: Pydantic schemas for Consolidated CrPC Requests.
Handles batch consolidation of pipelines for dispatch.

Groups approved pipelines by operator and service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import DispatchMode, ConsolidatedRequestStatus


# ========== Attachment Schema ==========
class AttachmentSchema(BaseModel):
    """Attachment information."""
    attachmentName: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Attachment name"
    )
    formatFilePath: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="File path"
    )


# ========== Base Schema ==========
class ConsolidatedCrpcRequestBase(BaseModel):
    """Base schema for consolidated requests."""
    mode: DispatchMode = Field(
        ...,
        description="Dispatch mode (Email or SMS)"
    )
    serviceId: PyObjectId = Field(
        ...,
        description="Service type for consolidation"
    )
    operatorId: PyObjectId = Field(
        ...,
        description="Target operator"
    )
    crpcRequestPipelineIds: List[PyObjectId] = Field(
        ...,
        min_items=1,
        description="List of consolidated pipeline IDs"
    )
    attachmentsForSendingMail: List[AttachmentSchema] = Field(
        default_factory=list,
        description="Attachments to include in dispatch"
    )
    letterFilePaths: List[AttachmentSchema] = Field(
        default_factory=list,
        description="Generated letter files"
    )
    totalRequests: int = Field(
        ...,
        ge=1,
        description="Total requests in consolidation"
    )


# ========== Create Schema ==========
class ConsolidatedCrpcRequestCreateSchema(ConsolidatedCrpcRequestBase):
    """Schema for creating consolidated request."""
    pass


# ========== Response Schema ==========
class ConsolidatedCrpcRequestResponseSchema(ConsolidatedCrpcRequestBase):
    """Schema for consolidated request responses."""
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    consolidatedCrpcRequestStatus: ConsolidatedRequestStatus = Field(
        ...,
        description="Current status"
    )
    downloadedAt: Optional[datetime] = Field(
        None,
        description="Download timestamp"
    )
    isActive: bool = Field(default=True, description="Active flag")
    createdAt: datetime = Field(..., description="Creation timestamp")
    createdBy: PyObjectId = Field(..., description="User who created")
    createdIp: str = Field(..., description="IP address")
    updatedAt: datetime = Field(..., description="Last update timestamp")
    updatedBy: PyObjectId = Field(..., description="User who updated")
    updatedIp: str = Field(..., description="IP address")

    class Config:
        populate_by_name = True


# ========== Search Schema ==========
class ConsolidatedSearchSchema(BaseModel):
    """Schema for searching consolidated requests."""
    serviceId: Optional[PyObjectId] = Field(None, description="Filter by service")
    operatorId: Optional[PyObjectId] = Field(None, description="Filter by operator")
    status: Optional[ConsolidatedRequestStatus] = Field(None, description="Filter by status")
    createdDateFrom: Optional[datetime] = Field(None, description="From date")
    createdDateTo: Optional[datetime] = Field(None, description="To date")
    includeInactive: bool = Field(default=False, description="Include inactive")
    sortBy: str = Field(default="createdAt", description="Sort field")
    sortOrder: str = Field(default="desc", description="Sort order")
    page: int = Field(default=1, ge=1, description="Page number")
    pageSize: int = Field(default=25, ge=1, le=100, description="Items per page")

    @field_validator('sortBy')
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        allowed = {"createdAt", "totalRequests", "consolidatedCrpcRequestStatus"}
        if v not in allowed:
            raise ValueError(f"sortBy must be one of {allowed}")
        return v

    @field_validator('sortOrder')
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        if v.lower() not in {"asc", "desc"}:
            raise ValueError("sortOrder must be 'asc' or 'desc'")
        return v.lower()


# ========== List Response Schema ==========
class ConsolidatedListResponseSchema(BaseModel):
    """Paginated response for consolidated requests."""
    data: List[ConsolidatedCrpcRequestResponseSchema] = Field(..., description="List of records")
    total: int = Field(..., description="Total records")
    page: int = Field(..., description="Current page")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total pages")


# ========== Mark Downloaded Schema ==========
class MarkDownloadedSchema(BaseModel):
    """Schema for marking request as downloaded."""
    consolidatedRequestId: PyObjectId = Field(
        ...,
        description="Consolidated request ID"
    )


# ========== Available Consolidation Schema ==========
class AvailableConsolidationSchema(BaseModel):
    """Schema for available consolidation summary."""
    serviceId: str = Field(..., description="Service ID")
    serviceName: str = Field(..., description="Service name")
    operatorId: str = Field(..., description="Operator ID")
    operatorName: str = Field(..., description="Operator name")
    pipelineCount: int = Field(..., description="Number of pending pipelines")
    oldestRequestDate: Optional[datetime] = Field(None, description="Oldest request date")

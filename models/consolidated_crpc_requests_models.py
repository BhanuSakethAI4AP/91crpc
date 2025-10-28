"""
Purpose: Pydantic schemas for Consolidated CrPC Requests.
Handles batch consolidation of pipelines for dispatch.

UPDATED: Groups approved pipelines by OPERATOR only (not by service).
Multiple services can be consolidated together for the same operator.
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
    """
    Base schema for consolidated requests.
    
    IMPORTANT: Consolidation is by OPERATOR only, not by service.
    A single consolidation can contain pipelines from multiple services.
    """
    mode: DispatchMode = Field(
        ...,
        description="Dispatch mode (Email, SMS, Portal)"
    )
    operatorId: PyObjectId = Field(
        ...,
        description="PRIMARY GROUPING: Target operator for consolidation"
    )
    crpcRequestPipelineIds: List[PyObjectId] = Field(
        ...,
        min_items=1,
        description="List of consolidated pipeline IDs (can be mixed services: CDR, IMEI, Banking, etc.)"
    )
    attachmentsForSendingMail: List[AttachmentSchema] = Field(
        default_factory=list,
        description="Attachments to include in dispatch (from operator's format config)"
    )
    letterFilePaths: List[AttachmentSchema] = Field(
        default_factory=list,
        description="Generated consolidated files (e.g., Airtel_AllServices_*.xlsx)"
    )
    totalRequests: int = Field(
        ...,
        ge=1,
        description="Total number of pipelines consolidated"
    )


# ========== Create Schema ==========
class ConsolidatedCrpcRequestCreateSchema(ConsolidatedCrpcRequestBase):
    """
    Schema for creating consolidated request.
    
    Preconditions:
        - All pipelines in crpcRequestPipelineIds must exist
        - All pipelines must have status = "Approved"
        - All pipelines must belong to the same operatorId
        - Services in pipelines must have canBeConsolidated = true
    """
    pass


# ========== Response Schema ==========
class ConsolidatedCrpcRequestResponseSchema(ConsolidatedCrpcRequestBase):
    """Schema for consolidated request responses."""
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    consolidatedCrpcRequestStatus: ConsolidatedRequestStatus = Field(
        ...,
        description="Current status (NotDownloaded, Downloaded)"
    )
    downloadedAt: Optional[datetime] = Field(
        None,
        description="Download timestamp (first download only)"
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
        json_schema_extra = {
            "example": {
                "_id": "671000000000000000000b01",
                "mode": "Email",
                "operatorId": "671000000000000000000201",
                "crpcRequestPipelineIds": [
                    "671000000000000000000701",
                    "671000000000000000000702",
                    "671000000000000000000713"
                ],
                "attachmentsForSendingMail": [
                    {
                        "attachmentName": "Authorization_Letter.pdf",
                        "formatFilePath": "/attachments/airtel/authorization_global.pdf"
                    },
                    {
                        "attachmentName": "Court_Order.pdf",
                        "formatFilePath": "/attachments/airtel/court_order.pdf"
                    }
                ],
                "letterFilePaths": [
                    {
                        "attachmentName": "Airtel_AllServices_20251026_143000.xlsx",
                        "formatFilePath": "/uploads/consolidated/Airtel_AllServices_20251026_143000.xlsx"
                    }
                ],
                "consolidatedCrpcRequestStatus": "Downloaded",
                "downloadedAt": "2025-10-26T15:00:00.000Z",
                "totalRequests": 3,
                "isActive": True,
                "createdAt": "2025-10-26T14:30:00.000Z",
                "createdBy": "6710000000000000000000a1",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-26T15:00:00.000Z",
                "updatedBy": "6710000000000000000000a5",
                "updatedIp": "10.10.20.45"
            }
        }


# ========== Search Schema ==========
class ConsolidatedSearchSchema(BaseModel):
    """Schema for searching consolidated requests."""
    operatorId: Optional[PyObjectId] = Field(None, description="Filter by operator")
    status: Optional[ConsolidatedRequestStatus] = Field(None, description="Filter by status")
    mode: Optional[DispatchMode] = Field(None, description="Filter by dispatch mode")
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
        allowed = {"createdAt", "totalRequests", "consolidatedCrpcRequestStatus", "operatorId"}
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
    """
    Schema for available consolidation summary.
    
    Represents a group of pipelines ready for consolidation by operator.
    NOTE: No longer grouped by service - only by operator.
    """
    operatorId: str = Field(..., description="Operator ID")
    operatorName: str = Field(..., description="Operator name")
    pipelineCount: int = Field(..., ge=1, description="Number of approved pipelines ready for consolidation")
    serviceBreakdown: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Breakdown by service types in this consolidation",
        examples=[
            [
                {"serviceId": "671000000000000000000101", "serviceName": "CDR", "count": 5},
                {"serviceId": "671000000000000000000104", "serviceName": "IMEI", "count": 2}
            ]
        ]
    )
    oldestRequestDate: Optional[datetime] = Field(None, description="Oldest request date in group")
    totalPipelinesValue: int = Field(
        ...,
        description="Total pipelines (same as pipelineCount, for backward compatibility)"
    )


# ========== Consolidation Summary Schema ==========
class ConsolidationSummarySchema(BaseModel):
    """
    Summary of what will be consolidated for an operator.
    Used before actual consolidation creation.
    """
    operatorId: PyObjectId = Field(..., description="Operator ID")
    operatorName: str = Field(..., description="Operator name")
    pipelineIds: List[PyObjectId] = Field(..., description="Pipeline IDs to be consolidated")
    totalPipelines: int = Field(..., description="Total number of pipelines")
    servicesSummary: List[Dict[str, Any]] = Field(
        ...,
        description="Summary by service type"
    )
    attachments: List[AttachmentSchema] = Field(
        ...,
        description="Attachments that will be included"
    )
    estimatedFileSize: Optional[str] = Field(
        None,
        description="Estimated file size (e.g., '2.5 MB')"
    )


# ========== Consolidation Creation Response Schema ==========
class ConsolidationCreationResponseSchema(BaseModel):
    """
    Response after creating a consolidation.
    Includes consolidation details and generation status.
    """
    consolidation: ConsolidatedCrpcRequestResponseSchema = Field(
        ...,
        description="Created consolidation record"
    )
    fileGenerated: bool = Field(
        ...,
        description="Whether output file was successfully generated"
    )
    fileName: Optional[str] = Field(
        None,
        description="Name of generated file"
    )
    filePath: Optional[str] = Field(
        None,
        description="Path to generated file"
    )
    updatedPipelineIds: List[PyObjectId] = Field(
        ...,
        description="Pipeline IDs that were updated to 'Consolidated' status"
    )

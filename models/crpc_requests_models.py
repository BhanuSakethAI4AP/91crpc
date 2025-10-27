"""
Purpose: Pydantic schemas for CrPC Requests CRUD operations.
Handles validation and serialization for main CrPC requests.

Parent entity that contains service list and generates pipelines.
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import CrpcRequestStatus


# ========== FIR Schema ==========
class FirSchema(BaseModel):
    """
    FIR (First Information Report) details.
    """
    firNo: int = Field(
        ...,
        ge=1,
        description="FIR number",
        examples=[12345]
    )
    path: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to FIR document",
        examples=["/firs/12345.pdf"]
    )


# ========== Service List Item Schema ==========
class ServiceListItemSchema(BaseModel):
    """
    Individual service request item.
    Each item will become a separate pipeline.
    """
    lineNo: int = Field(
        ...,
        ge=1,
        description="Sequential line number",
        examples=[1, 2, 3]
    )
    serviceId: PyObjectId = Field(
        ...,
        description="Service type (CDR, IPDR, Banking, etc.)"
    )
    keyFieldValue: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Identifier (phone, account, IMEI, etc.)",
        examples=["9876543210", "SBIN000123456"]
    )
    requiredData: Dict[str, Any] = Field(
        ...,
        description="Additional data required for this service",
        examples=[
            {"fromDate": "2025-09-01", "toDate": "2025-09-30"},
            {"fromDate": "2025-08-01", "toDate": "2025-10-01", "AccNo": "5438957362946856394"}
        ]
    )


# ========== Attachment Schema ==========
class AttachmentSchema(BaseModel):
    """
    Attachment required for the request.
    """
    attachmentName: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the attachment",
        examples=["Authorization", "FIR Copy"]
    )
    formatFilePath: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to the attachment file",
        examples=["/auth/12345.pdf"]
    )


# ========== Base Schema ==========
class CrpcRequestBase(BaseModel):
    """
    Base schema for CrPC Request.
    Contains all service requests for one FIR.
    """
    unitId: PyObjectId = Field(
        ...,
        description="Police unit/station reference (from core service)"
    )
    requestedBy: PyObjectId = Field(
        ...,
        description="User who created the request (from core service)"
    )
    fir: List[FirSchema] = Field(
        ...,
        min_items=1,
        description="FIR details (can have multiple FIRs)"
    )
    serviceList: List[ServiceListItemSchema] = Field(
        ...,
        min_items=1,
        description="List of services requested (will generate pipelines)"
    )
    attachmentsNeededForRequest: List[AttachmentSchema] = Field(
        default_factory=list,
        description="Common attachments for all services"
    )
    requestDate: datetime = Field(
    default_factory=lambda: datetime.now(timezone.utc),
    description="Date of request creation"
    )
    ackNo: Optional[str] = Field(
        None,
        max_length=100,
        description="NCRP acknowledgment number (for bank requests)"
    )

    @field_validator('serviceList')
    @classmethod
    def validate_unique_line_numbers(cls, v: List[ServiceListItemSchema]) -> List[ServiceListItemSchema]:
        """Validate that line numbers are unique and sequential."""
        line_numbers = [item.lineNo for item in v]
        
        # Check uniqueness
        if len(line_numbers) != len(set(line_numbers)):
            raise ValueError("Line numbers must be unique")
        
        # Check sequential (1, 2, 3, ...)
        sorted_numbers = sorted(line_numbers)
        expected_numbers = list(range(1, len(line_numbers) + 1))
        if sorted_numbers != expected_numbers:
            raise ValueError("Line numbers must be sequential starting from 1")
        
        return v


# ========== Create Schema ==========
class CrpcRequestCreateSchema(CrpcRequestBase):
    """
    Schema for creating a new CrPC request.
    
    Will automatically:
    1. Detect operators for each service
    2. Create pipeline records
    3. Create approval chains
    4. Determine starting step based on initiator
    """
    pass


# ========== Update Schema ==========
class CrpcRequestUpdateSchema(BaseModel):
    """
    Schema for updating a CrPC request.
    Limited fields can be updated after creation.
    """
    attachmentsNeededForRequest: Optional[List[AttachmentSchema]] = Field(
        None,
        description="Updated attachments"
    )
    ackNo: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated NCRP acknowledgment number"
    )
    # Note: Cannot update serviceList after creation
    # Cannot update status directly (derived from pipelines)


# ========== Response Schema ==========
class CrpcRequestResponseSchema(CrpcRequestBase):
    """
    Schema for CrPC request responses (includes metadata).
    """
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    approvedBy: Optional[PyObjectId] = Field(None, description="User who approved (final approver)")
    CrPCRequestStatus: CrpcRequestStatus = Field(
        ...,
        description="Overall request status (derived from pipelines)"
    )
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
                "_id": "671000000000000000000501",
                "unitId": "6710000000000000000000b1",
                "requestedBy": "6710000000000000000000a5",
                "approvedBy": "6710000000000000000000a4",
                "fir": [{"firNo": 12345, "path": "/firs/12345.pdf"}],
                "serviceList": [
                    {
                        "lineNo": 1,
                        "serviceId": "671000000000000000000101",
                        "keyFieldValue": "9876543210",
                        "requiredData": {"fromDate": "2025-09-01", "toDate": "2025-09-30"}
                    }
                ],
                "attachmentsNeededForRequest": [
                    {"attachmentName": "Authorization", "formatFilePath": "/auth/12345.pdf"}
                ],
                "requestDate": "2025-09-01",
                "ackNo": None,
                "CrPCRequestStatus": "OnApprovalQueue",
                "isActive": True,
                "createdAt": "2025-09-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a5",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a4",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema ==========
class CrpcRequestSearchSchema(BaseModel):
    """
    Schema for searching and filtering CrPC requests.
    """
    unitId: Optional[PyObjectId] = Field(None, description="Filter by unit")
    requestedBy: Optional[PyObjectId] = Field(None, description="Filter by requester")
    firNo: Optional[int] = Field(None, description="Search by FIR number")
    CrPCRequestStatus: Optional[CrpcRequestStatus] = Field(None, description="Filter by status")
    requestDateFrom: Optional[date] = Field(None, description="Filter from date")
    requestDateTo: Optional[date] = Field(None, description="Filter to date")
    ackNo: Optional[str] = Field(None, description="Search by NCRP ACK number")
    includeInactive: bool = Field(default=False, description="Include inactive records")
    
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
            "requestDate", "CrPCRequestStatus", 
            "createdAt", "updatedAt"
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
class CrpcRequestListResponseSchema(BaseModel):
    """Paginated response schema for CrPC request list."""
    data: List[CrpcRequestResponseSchema] = Field(..., description="List of CrPC requests")
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")


# ========== Request with Pipelines Schema ==========
class CrpcRequestWithPipelinesSchema(CrpcRequestResponseSchema):
    """
    Extended schema with pipeline details.
    Shows complete request with all line items.
    """
    pipelines: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Associated pipeline items"
    )
    
    class Config:
        populate_by_name = True


# ========== Close Request Schema ==========
class CloseRequestSchema(BaseModel):
    """
    Schema for closing a request.
    Only SHO can close requests.
    """
    closureNotes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Notes for closing the request"
    )

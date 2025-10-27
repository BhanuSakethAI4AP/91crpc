"""
Purpose: Pydantic schemas for Operator Service List CRUD operations.
Handles validation and serialization for operator-service mappings.

Based on TFS: OperatorServiceList.CREATE, READ, UPDATE, DELETE
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId


# ========== Attachment Schema ==========
class AttachmentSchema(BaseModel):
    """
    Attachment information for operator service formats.
    Represents additional documents required for a service request.
    """
    attachmentName: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the attachment",
        examples=["Authorization Letter", "FIR Copy", "Court Order"]
    )
    formatFilePath: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to the format file template",
        examples=["/attachments/airtel/auth.pdf", "/formats/authorization_template.pdf"]
    )


# ========== Operator Format Schema ==========
class OperatorFormatSchema(BaseModel):
    """
    Format specification for a specific operator.
    Defines the template and attachments required for each operator.
    """
    operatorId: PyObjectId = Field(
        ...,
        description="Reference to operator in operators_list collection"
    )
    formatFilePath: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to the operator-specific format template",
        examples=["/formats/airtel.xlsx", "/formats/jio_template.xlsx"]
    )
    listOfAttachments: List[AttachmentSchema] = Field(
        default_factory=list,
        description="List of attachments required for this operator"
    )


# ========== Base Schema ==========
class OperatorServiceListBase(BaseModel):
    """
    Base schema with common fields for Operator Service List.
    Maps services to operator-specific formats and requirements.
    """
    serviceId: PyObjectId = Field(
        ...,
        description="Reference to service in service_master collection"
    )
    operatorFormats: List[OperatorFormatSchema] = Field(
        ...,
        min_items=1,
        description="List of operator-specific format configurations"
    )
    requiredData: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional data requirements (e.g., date ranges, fields)",
        examples=[
            {"fromDate": "2025-09-01", "toDate": "2025-09-30"},
            {"fields": ["callerId", "duration", "location"]}
        ]
    )

    @field_validator('operatorFormats')
    @classmethod
    def validate_unique_operators(cls, v: List[OperatorFormatSchema]) -> List[OperatorFormatSchema]:
        """
        Validate that operatorIds are unique within the list.
        
        Raises:
            ValueError: If duplicate operator IDs found
        """
        operator_ids = [fmt.operatorId for fmt in v]
        if len(operator_ids) != len(set(operator_ids)):
            raise ValueError("Duplicate operator IDs found in operatorFormats")
        return v


# ========== Create Schema (TFS: OperatorServiceList.CREATE) ==========
class OperatorServiceListCreateSchema(OperatorServiceListBase):
    """
    Schema for creating a new operator service mapping.
    
    TFS Reference: OperatorServiceList.CREATE
    Preconditions:
        - serviceId exists in service_master
        - all operatorIds exist in operators_list
        - no duplicate operatorFormats per serviceId
    """
    pass


# ========== Update Schema (TFS: OperatorServiceList.UPDATE) ==========
class OperatorServiceListUpdateSchema(BaseModel):
    """
    Schema for updating an existing operator service mapping.
    All fields optional for partial updates.
    
    TFS Reference: OperatorServiceList.UPDATE
    """
    operatorFormats: Optional[List[OperatorFormatSchema]] = Field(
        None,
        min_items=1,
        description="Updated operator format configurations"
    )
    requiredData: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated data requirements"
    )

    @field_validator('operatorFormats')
    @classmethod
    def validate_unique_operators(cls, v: Optional[List[OperatorFormatSchema]]) -> Optional[List[OperatorFormatSchema]]:
        """Validate unique operator IDs if provided."""
        if v is None:
            return v
        operator_ids = [fmt.operatorId for fmt in v]
        if len(operator_ids) != len(set(operator_ids)):
            raise ValueError("Duplicate operator IDs found in operatorFormats")
        return v


# ========== Response Schema (TFS: All Operations) ==========
class OperatorServiceListResponseSchema(OperatorServiceListBase):
    """
    Schema for operator service list responses (includes metadata).
    
    TFS Reference: OperatorServiceList.CREATE/READ/UPDATE/DELETE outputs
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
                "_id": "671000000000000000000301",
                "serviceId": "671000000000000000000101",
                "operatorFormats": [
                    {
                        "operatorId": "671000000000000000000201",
                        "formatFilePath": "/formats/airtel.xlsx",
                        "listOfAttachments": [
                            {
                                "attachmentName": "Authorization",
                                "formatFilePath": "/attachments/airtel/auth.pdf"
                            }
                        ]
                    }
                ],
                "requiredData": {
                    "fromDate": "2025-09-01",
                    "toDate": "2025-09-30"
                },
                "isDeleted": False,
                "createdAt": "2025-09-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a2",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a2",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema (TFS: OperatorServiceList.READ) ==========
class OperatorServiceListSearchSchema(BaseModel):
    """
    Schema for searching and filtering operator service mappings.
    
    TFS Reference: OperatorServiceList.READ
    Supports filtering by serviceId, operatorId, isDeleted
    """
    serviceId: Optional[PyObjectId] = Field(
        None,
        description="Filter by service ID"
    )
    operatorId: Optional[PyObjectId] = Field(
        None,
        description="Filter by operator ID (within operatorFormats)"
    )
    includeDeleted: bool = Field(
        default=False,
        description="Include soft-deleted records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="createdAt",
        description="Field to sort by (serviceId, createdAt, updatedAt)"
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
        allowed_fields = {"serviceId", "createdAt", "updatedAt"}
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
class OperatorServiceListListResponseSchema(BaseModel):
    """Paginated response schema for operator service list."""
    data: List[OperatorServiceListResponseSchema] = Field(..., description="List of operator service mappings")
    total: int = Field(..., description="Total number of records matching criteria")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")

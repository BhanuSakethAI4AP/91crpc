"""
Purpose: Pydantic schemas for Service Master CRUD operations.
Handles validation and serialization for service master data.

Based on TFS: ServiceMaster.CREATE, READ, UPDATE, DELETE
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId


# ========== Base Schema ==========
class ServiceMasterBase(BaseModel):
    """
    Base schema with common fields for Service Master.
    Used as foundation for create/update schemas.
    """
    serviceName: str = Field(
        ..., 
        min_length=1, 
        max_length=100, 
        description="Name of the service (e.g., CDR, IPDR, CAF)",
        examples=["CDR", "IPDR", "CAF"]
    )
    operatorType: list[str] = Field(
        ..., 
        min_items=1, 
        description="List of operator types (telecom, bank, isp)",
        examples=[["telecom"], ["telecom", "bank"]]
    )
    keyField: str = Field(
        ..., 
        min_length=1, 
        max_length=50, 
        description="Key field for this service (e.g., phoneNo, accountNo, ipAddress)",
        examples=["phoneNo", "accountNo", "ipAddress"]
    )
    canBeConsolidated: bool = Field(
        ..., 
        description="Whether this service can be consolidated for batch dispatch"
    )

    @field_validator('operatorType')
    @classmethod
    def validate_operator_types(cls, v: list[str]) -> list[str]:
        """
        Validate operator types are valid and lowercase.
        
        Raises:
            ValueError: If operator type is not in valid set
        """
        valid_types = {"telecom", "bank", "isp"}
        for op_type in v:
            if op_type.lower() not in valid_types:
                raise ValueError(
                    f"Invalid operator type: '{op_type}'. "
                    f"Must be one of {valid_types}"
                )
        return [op.lower() for op in v]


# ========== Create Schema (TFS: ServiceMaster.CREATE) ==========
class ServiceMasterCreateSchema(ServiceMasterBase):
    """
    Schema for creating a new service master record.
    
    TFS Reference: ServiceMaster.CREATE
    Inputs: serviceName, operatorType, keyField, canBeConsolidated, user_id
    """
    pass


# ========== Update Schema (TFS: ServiceMaster.UPDATE) ==========
class ServiceMasterUpdateSchema(BaseModel):
    """
    Schema for updating an existing service master record.
    All fields optional for partial updates.
    
    TFS Reference: ServiceMaster.UPDATE
    Inputs: _id (required), serviceName, operatorType, keyField, canBeConsolidated, user_id
    """
    serviceName: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=100,
        description="Updated service name"
    )
    operatorType: Optional[list[str]] = Field(
        None, 
        min_items=1,
        description="Updated operator types"
    )
    keyField: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=50,
        description="Updated key field"
    )
    canBeConsolidated: Optional[bool] = Field(
        None,
        description="Updated consolidation flag"
    )

    @field_validator('operatorType')
    @classmethod
    def validate_operator_types(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate operator types if provided."""
        if v is None:
            return v
        valid_types = {"telecom", "bank", "isp"}
        for op_type in v:
            if op_type.lower() not in valid_types:
                raise ValueError(
                    f"Invalid operator type: '{op_type}'. "
                    f"Must be one of {valid_types}"
                )
        return [op.lower() for op in v]


# ========== Response Schema (TFS: All Operations) ==========
class ServiceMasterResponseSchema(ServiceMasterBase):
    """
    Schema for service master responses (includes metadata).
    
    TFS Reference: ServiceMaster.CREATE/READ/UPDATE/DELETE outputs
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
                "_id": "671000000000000000000101",
                "serviceName": "CDR",
                "operatorType": ["telecom"],
                "keyField": "phoneNo",
                "canBeConsolidated": True,
                "isDeleted": False,
                "createdAt": "2025-08-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a1",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-10-01T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a1",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema (TFS: ServiceMaster.READ) ==========
class ServiceMasterSearchSchema(BaseModel):
    """
    Schema for searching and filtering service masters.
    
    TFS Reference: ServiceMaster.READ
    Supports filtering by serviceName, operatorType, isDeleted
    """
    serviceName: Optional[str] = Field(
        None, 
        description="Search by service name (partial match, case-insensitive)"
    )
    operatorType: Optional[str] = Field(
        None, 
        description="Filter by operator type (exact match)"
    )
    canBeConsolidated: Optional[bool] = Field(
        None, 
        description="Filter by consolidation capability"
    )
    includeDeleted: bool = Field(
        default=False, 
        description="Include soft-deleted records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="serviceName", 
        description="Field to sort by (serviceName, createdAt, updatedAt)"
    )
    sortOrder: str = Field(
        default="asc", 
        description="Sort order: asc or desc"
    )
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(default=25, ge=1, le=100, description="Items per page (1-100)")

    @field_validator('sortBy')
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        """Validate sort field is allowed."""
        allowed_fields = {"serviceName", "createdAt", "updatedAt"}
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
class ServiceMasterListResponseSchema(BaseModel):
    """Paginated response schema for service master list."""
    data: list[ServiceMasterResponseSchema] = Field(..., description="List of service masters")
    total: int = Field(..., description="Total number of records matching criteria")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")

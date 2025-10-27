"""
Purpose: Pydantic schemas for Operators List CRUD operations.
Handles validation and serialization for operator data.

Based on TFS: OperatorsList.CREATE, READ, UPDATE, DELETE
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, field_validator
from utils.validators import PyObjectId
from constants.value_sets import OperatorType


# ========== Contact Schema ==========
class ContactSchema(BaseModel):
    """
    Contact information for operator representatives.
    Used in operator records for communication purposes.
    """
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Full name of the contact person",
        examples=["John Doe", "Airtel Nodal 1"]
    )
    designation: Optional[str] = Field(
        None,
        max_length=100,
        description="Job title or designation",
        examples=["Manager", "Nodal Officer", "Senior Executive"]
    )
    email: EmailStr = Field(
        ...,
        description="Email address of the contact",
        examples=["john@example.com", "nodal1@airtel.example"]
    )
    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number with country code",
        examples=["+911100000001", "9876543210"]
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Validate phone number format.
        
        Raises:
            ValueError: If phone contains invalid characters
        """
        # Remove common formatting characters
        cleaned = v.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        
        # Check if remaining characters are digits
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits and standard formatting characters (+, -, space, parentheses)")
        
        return v


# ========== Base Schema ==========
class OperatorsListBase(BaseModel):
    """
    Base schema with common fields for Operators List.
    Used as foundation for create/update schemas.
    """
    operatorType: OperatorType = Field(
        ...,
        description="Type of operator (Telecom, Bank, ISP)",
        examples=["Telecom", "Bank", "ISP"]
    )
    operatorName: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the operator company",
        examples=["Airtel", "HDFC Bank", "ACT Fibernet"]
    )
    contact: List[ContactSchema] = Field(
        ...,
        min_items=1,
        description="List of contact persons for this operator"
    )


# ========== Create Schema (TFS: OperatorsList.CREATE) ==========
class OperatorsListCreateSchema(OperatorsListBase):
    """
    Schema for creating a new operator record.
    
    TFS Reference: OperatorsList.CREATE
    Inputs: operator_type, operator_name, contact, user_id
    Preconditions: 
        - operator_type must exist in 91CrPCOperatorType
        - operator_name must be unique within its type
    """
    pass


# ========== Update Schema (TFS: OperatorsList.UPDATE) ==========
class OperatorsListUpdateSchema(BaseModel):
    """
    Schema for updating an existing operator record.
    All fields optional for partial updates.
    
    TFS Reference: OperatorsList.UPDATE
    Inputs: _id (required), operator_type, operator_name, contact, user_id
    """
    operatorType: Optional[OperatorType] = Field(
        None,
        description="Updated operator type"
    )
    operatorName: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated operator name"
    )
    contact: Optional[List[ContactSchema]] = Field(
        None,
        min_items=1,
        description="Updated contact list"
    )


# ========== Response Schema (TFS: All Operations) ==========
class OperatorsListResponseSchema(OperatorsListBase):
    """
    Schema for operator responses (includes metadata).
    
    TFS Reference: OperatorsList.CREATE/READ/UPDATE/DELETE outputs
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
                "_id": "671000000000000000000201",
                "operatorType": "Telecom",
                "operatorName": "Airtel",
                "contact": [
                    {
                        "name": "Airtel Nodal 1",
                        "designation": "Nodal Officer",
                        "email": "nodal1@airtel.example",
                        "phone": "+911100000001"
                    }
                ],
                "isDeleted": False,
                "createdAt": "2025-08-01T10:00:00.000Z",
                "createdBy": "6710000000000000000000a1",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-09-15T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a2",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema (TFS: OperatorsList.READ) ==========
class OperatorsListSearchSchema(BaseModel):
    """
    Schema for searching and filtering operators.
    
    TFS Reference: OperatorsList.READ
    Supports filtering by operatorType, operatorName, isDeleted
    """
    operatorName: Optional[str] = Field(
        None,
        description="Search by operator name (partial match, case-insensitive)"
    )
    operatorType: Optional[OperatorType] = Field(
        None,
        description="Filter by operator type (exact match)"
    )
    includeDeleted: bool = Field(
        default=False,
        description="Include soft-deleted records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="operatorName",
        description="Field to sort by (operatorName, operatorType, createdAt, updatedAt)"
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
        allowed_fields = {"operatorName", "operatorType", "createdAt", "updatedAt"}
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
class OperatorsListListResponseSchema(BaseModel):
    """Paginated response schema for operators list."""
    data: List[OperatorsListResponseSchema] = Field(..., description="List of operators")
    total: int = Field(..., description="Total number of records matching criteria")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total number of pages")

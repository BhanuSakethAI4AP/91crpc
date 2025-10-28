"""
Purpose: Pydantic schemas for Data Received operations.
Handles validation for received data BATCHES only.

File operations are in data_received_files_models.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from utils.validators import PyObjectId
from constants.value_sets import ProcessingStatus


# ========== Email Metadata Schema ==========
class EmailMetaDataSchema(BaseModel):
    """Email metadata for received data."""
    fromEmail: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Sender email address",
        alias="from"
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Email subject"
    )
    password: Optional[str] = Field(
        None,
        max_length=100,
        description="ZIP file password if provided"
    )

    class Config:
        populate_by_name = True


# ========== Data Received Base Schema ==========
class DataReceivedBase(BaseModel):
    """Base schema for data received batches."""
    receivedAt: datetime = Field(
        ...,
        description="When the data was received"
    )
    operatorId: PyObjectId = Field(
        ...,
        description="Operator who sent this data"
    )
    totalFiles: int = Field(
        ...,
        ge=1,
        description="Total number of files in batch"
    )
    emailMetaData: Optional[EmailMetaDataSchema] = Field(
        None,
        description="Email metadata if received via email"
    )


# ========== Create Schema ==========
class DataReceivedCreateSchema(DataReceivedBase):
    """Schema for creating data received record."""
    pass


# ========== Update Schema ==========
class DataReceivedUpdateSchema(BaseModel):
    """Schema for updating data received record."""
    processingStatus: Optional[ProcessingStatus] = Field(
        None,
        description="Updated processing status"
    )
    autoMatchedCount: Optional[int] = Field(
        None,
        ge=0,
        description="Updated auto-matched count"
    )
    conflictCount: Optional[int] = Field(
        None,
        ge=0,
        description="Updated conflict count"
    )
    unmatchedCount: Optional[int] = Field(
        None,
        ge=0,
        description="Updated unmatched count"
    )


# ========== Response Schema ==========
class DataReceivedResponseSchema(DataReceivedBase):
    """Schema for data received responses."""
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    processingStatus: ProcessingStatus = Field(
        ...,
        description="Current processing status"
    )
    autoMatchedCount: int = Field(..., description="Count of auto-matched files")
    conflictCount: int = Field(..., description="Count of conflicted files")
    unmatchedCount: int = Field(..., description="Count of unmatched files")
    isActive: bool = Field(default=True, description="Active flag")
    createdAt: datetime = Field(..., description="Creation timestamp")
    createdBy: PyObjectId = Field(..., description="User who created")
    createdIp: str = Field(..., description="IP address")
    updatedAt: datetime = Field(..., description="Last update timestamp")
    updatedBy: PyObjectId = Field(..., description="User who updated")
    updatedIp: str = Field(..., description="IP address")

    class Config:
        populate_by_name = True


# ========== Conflict Resolution Schema ==========
class ResolveConflictSchema(BaseModel):
    """Schema for resolving file conflicts."""
    fileId: PyObjectId = Field(
        ...,
        description="File ID to resolve"
    )
    selectedPipelineId: PyObjectId = Field(
        ...,
        description="Selected pipeline ID"
    )


# ========== Upload Request Schema ==========
class UploadDataReceivedSchema(BaseModel):
    """Schema for uploading received data."""
    operatorId: PyObjectId = Field(
        ...,
        description="Operator ID"
    )
    emailMetaData: Optional[EmailMetaDataSchema] = Field(
        None,
        description="Email metadata"
    )
    # Note: Files will be handled separately via FormData


# ========== Search Schema ==========
class DataReceivedSearchSchema(BaseModel):
    """Schema for searching data received."""
    operatorId: Optional[PyObjectId] = Field(None, description="Filter by operator")
    processingStatus: Optional[ProcessingStatus] = Field(None, description="Filter by status")
    receivedDateFrom: Optional[datetime] = Field(None, description="From date")
    receivedDateTo: Optional[datetime] = Field(None, description="To date")
    includeInactive: bool = Field(default=False, description="Include inactive")
    sortBy: str = Field(default="receivedAt", description="Sort field")
    sortOrder: str = Field(default="desc", description="Sort order")
    page: int = Field(default=1, ge=1, description="Page number")
    pageSize: int = Field(default=25, ge=1, le=100, description="Items per page")

    @field_validator('sortBy')
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        allowed = {"receivedAt", "processingStatus", "totalFiles", "createdAt"}
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
class DataReceivedListResponseSchema(BaseModel):
    """Paginated response for data received list."""
    data: List[DataReceivedResponseSchema] = Field(..., description="List of records")
    total: int = Field(..., description="Total records")
    page: int = Field(..., description="Current page")
    pageSize: int = Field(..., description="Items per page")
    totalPages: int = Field(..., description="Total pages")

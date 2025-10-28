"""
Purpose: Pydantic schemas for Data Received Files operations.
Handles validation for individual file operations.

Separate from data_received_models for clarity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from utils.validators import PyObjectId
from constants.value_sets import MatchingStatus


# ========== File Base Schema ==========
class DataReceivedFileBase(BaseModel):
    """Base schema for individual received files."""
    dataReceivedId: PyObjectId = Field(
        ...,
        description="Reference to parent data_received batch"
    )
    fileName: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Original filename"
    )
    fileType: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of service data (CDR, IPDR, Banking)"
    )
    filePath: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Storage path"
    )
    fileSize: int = Field(
        ...,
        ge=0,
        description="File size in bytes"
    )
    uploadedAt: datetime = Field(
        ...,
        description="Upload timestamp"
    )


# ========== File Create Schema ==========
class DataReceivedFileCreateSchema(DataReceivedFileBase):
    """Schema for creating file record."""
    extractedKeyFieldValue: Optional[str] = Field(
        None,
        max_length=200,
        description="Extracted key value from filename"
    )


# ========== File Response Schema ==========
class DataReceivedFileResponseSchema(DataReceivedFileBase):
    """Schema for file responses."""
    id: PyObjectId = Field(..., alias="_id", description="Unique identifier")
    extractedKeyFieldValue: Optional[str] = Field(
        None,
        description="Extracted key value"
    )
    matchingStatus: MatchingStatus = Field(
        ...,
        description="Current matching status"
    )
    matchedPipelineId: Optional[PyObjectId] = Field(
        None,
        description="Matched pipeline ID"
    )
    conflictPipelineIds: List[PyObjectId] = Field(
        default_factory=list,
        description="Conflicting pipeline IDs"
    )
    manuallyMappedBy: Optional[PyObjectId] = Field(
        None,
        description="User who manually mapped"
    )
    manuallyMappedAt: Optional[datetime] = Field(
        None,
        description="Manual mapping timestamp"
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


# ========== File with Pipeline Details ==========
class FileWithPipelineDetailsSchema(DataReceivedFileResponseSchema):
    """Extended file schema with pipeline details."""
    matchedPipelineDetails: Optional[Dict[str, Any]] = Field(
        None,
        description="Details of matched pipeline"
    )
    potentialMatches: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Potential pipeline matches for conflicts"
    )

"""
Purpose: Pydantic schemas for Operator Service List CRUD operations.
Handles validation and serialization for operator-service mappings.

UPDATED: Operator-centric design with globalFormat and service-specific overrides.
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


# ========== Format Schema (Used for both global and service-specific) ==========
class FormatSchema(BaseModel):
    """
    Format configuration containing file path and attachments.
    Used for both globalFormat and serviceSpecificFormat.
    """
    formatFilePath: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to the format template file",
        examples=["/formats/airtel_all_services.xlsx", "/formats/airtel_cdr.xlsx"]
    )
    listOfAttachments: List[AttachmentSchema] = Field(
        default_factory=list,
        description="List of attachments required for this format"
    )


# ========== Service Configuration Schema ==========
class ServiceConfigSchema(BaseModel):
    """
    Configuration for a specific service provided by the operator.
    Contains service-specific format overrides and requirements.
    """
    serviceId: PyObjectId = Field(
        ...,
        description="Reference to service in service_master collection"
    )
    serviceName: Optional[str] = Field(
        None,
        max_length=100,
        description="Denormalized service name for quick lookup"
    )
    serviceSpecificFormat: Optional[FormatSchema] = Field(
        None,
        description="Service-specific format (overrides globalFormat if provided)"
    )
    requiredData: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Required data fields for this service",
        examples=[
            {"fromDate": "datetime", "toDate": "datetime"},
            {"fromDate": "datetime", "toDate": "datetime", "cellId": "string"}
        ]
    )
    maxDateRange: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum date range in days (if applicable)"
    )
    turnaroundTime: Optional[int] = Field(
        None,
        ge=1,
        description="Expected turnaround time in days"
    )
    isActive: bool = Field(
        default=True,
        description="Whether this service is currently active for the operator"
    )


# ========== Base Schema ==========
class OperatorServiceListBase(BaseModel):
    """
    Base schema for Operator Service List (operator-centric).
    Maps operator to multiple services with format configurations.
    """
    operatorId: PyObjectId = Field(
        ...,
        description="PRIMARY: Reference to operator in operators_list collection"
    )
    operatorName: Optional[str] = Field(
        None,
        max_length=100,
        description="Denormalized operator name for quick lookup"
    )
    globalFormat: Optional[FormatSchema] = Field(
        None,
        description="Global format used for all services (unless overridden)"
    )
    services: List[ServiceConfigSchema] = Field(
        ...,
        min_items=1,
        description="List of services provided by this operator"
    )

    @field_validator('services')
    @classmethod
    def validate_unique_services(cls, v: List[ServiceConfigSchema]) -> List[ServiceConfigSchema]:
        """
        Validate that serviceIds are unique within the list.
        
        Raises:
            ValueError: If duplicate service IDs found
        """
        service_ids = [svc.serviceId for svc in v]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("Duplicate service IDs found in services list")
        return v

    @field_validator('services')
    @classmethod
    def validate_format_availability(cls, v: List[ServiceConfigSchema], info) -> List[ServiceConfigSchema]:
        """
        Validate that each service has either serviceSpecificFormat or globalFormat available.
        
        Raises:
            ValueError: If no format is available for a service
        """
        # Access globalFormat from the parent model if available
        global_format = info.data.get('globalFormat')
        
        for service in v:
            if not service.serviceSpecificFormat and not global_format:
                raise ValueError(
                    f"Service {service.serviceId} has no serviceSpecificFormat and no globalFormat is defined"
                )
        return v


# ========== Create Schema (TFS: OperatorServiceList.CREATE) ==========
class OperatorServiceListCreateSchema(OperatorServiceListBase):
    """
    Schema for creating a new operator service mapping.
    
    TFS Reference: OperatorServiceList.CREATE
    Preconditions:
        - operatorId exists in operators_list
        - all serviceIds exist in service_master
        - no duplicate services per operator
        - each service has format available (global or specific)
    """
    pass


# ========== Update Schema (TFS: OperatorServiceList.UPDATE) ==========
class OperatorServiceListUpdateSchema(BaseModel):
    """
    Schema for updating an existing operator service mapping.
    All fields optional for partial updates.
    
    TFS Reference: OperatorServiceList.UPDATE
    """
    operatorName: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated operator name"
    )
    globalFormat: Optional[FormatSchema] = Field(
        None,
        description="Updated global format"
    )
    services: Optional[List[ServiceConfigSchema]] = Field(
        None,
        min_items=1,
        description="Updated services list"
    )

    @field_validator('services')
    @classmethod
    def validate_unique_services(cls, v: Optional[List[ServiceConfigSchema]]) -> Optional[List[ServiceConfigSchema]]:
        """Validate unique service IDs if provided."""
        if v is None:
            return v
        service_ids = [svc.serviceId for svc in v]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("Duplicate service IDs found in services list")
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
                "operatorId": "671000000000000000000201",
                "operatorName": "Airtel",
                "globalFormat": {
                    "formatFilePath": "/formats/airtel_all_services.xlsx",
                    "listOfAttachments": [
                        {
                            "attachmentName": "Authorization Letter",
                            "formatFilePath": "/attachments/airtel/authorization_global.pdf"
                        },
                        {
                            "attachmentName": "Court Order",
                            "formatFilePath": "/attachments/airtel/court_order.pdf"
                        }
                    ]
                },
                "services": [
                    {
                        "serviceId": "671000000000000000000101",
                        "serviceName": "CDR",
                        "serviceSpecificFormat": None,
                        "requiredData": {
                            "fromDate": "datetime",
                            "toDate": "datetime"
                        },
                        "maxDateRange": 90,
                        "turnaroundTime": 7,
                        "isActive": True
                    },
                    {
                        "serviceId": "671000000000000000000104",
                        "serviceName": "IMEI Details",
                        "serviceSpecificFormat": None,
                        "requiredData": {},
                        "maxDateRange": None,
                        "turnaroundTime": 3,
                        "isActive": True
                    },
                    {
                        "serviceId": "671000000000000000000105",
                        "serviceName": "Tower Dump",
                        "serviceSpecificFormat": {
                            "formatFilePath": "/formats/airtel_tower_dump_special.xlsx",
                            "listOfAttachments": [
                                {
                                    "attachmentName": "Tower Authorization",
                                    "formatFilePath": "/attachments/airtel/tower_auth.pdf"
                                }
                            ]
                        },
                        "requiredData": {
                            "fromDate": "datetime",
                            "toDate": "datetime",
                            "cellId": "string",
                            "latitude": "number",
                            "longitude": "number"
                        },
                        "maxDateRange": None,
                        "turnaroundTime": 10,
                        "isActive": True
                    }
                ],
                "isDeleted": False,
                "createdAt": "2025-01-20T10:00:00.000Z",
                "createdBy": "6710000000000000000000a2",
                "createdIp": "10.10.10.21",
                "updatedAt": "2025-01-20T10:00:00.000Z",
                "updatedBy": "6710000000000000000000a2",
                "updatedIp": "10.10.10.21"
            }
        }


# ========== Search/Filter Schema (TFS: OperatorServiceList.READ) ==========
class OperatorServiceListSearchSchema(BaseModel):
    """
    Schema for searching and filtering operator service mappings.
    
    TFS Reference: OperatorServiceList.READ
    Supports filtering by operatorId, serviceId, isDeleted
    """
    operatorId: Optional[PyObjectId] = Field(
        None,
        description="Filter by operator ID"
    )
    serviceId: Optional[PyObjectId] = Field(
        None,
        description="Filter by service ID (searches within services array)"
    )
    operatorName: Optional[str] = Field(
        None,
        max_length=100,
        description="Filter by operator name (partial match)"
    )
    includeDeleted: bool = Field(
        default=False,
        description="Include soft-deleted records"
    )
    
    # Sorting
    sortBy: str = Field(
        default="createdAt",
        description="Field to sort by (operatorName, createdAt, updatedAt)"
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
        allowed_fields = {"operatorId", "operatorName", "createdAt", "updatedAt"}
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


# ========== Service Format Resolution Schema ==========
class ServiceFormatResponseSchema(BaseModel):
    """
    Response schema for resolved format configuration.
    Used when querying which format to use for a specific service.
    """
    operatorId: PyObjectId = Field(..., description="Operator ID")
    operatorName: str = Field(..., description="Operator name")
    serviceId: PyObjectId = Field(..., description="Service ID")
    serviceName: str = Field(..., description="Service name")
    formatSource: str = Field(
        ...,
        description="Source of format: 'global' or 'service-specific'"
    )
    format: FormatSchema = Field(..., description="Resolved format configuration")
    requiredData: Dict[str, Any] = Field(..., description="Required data fields")
    maxDateRange: Optional[int] = Field(None, description="Maximum date range")
    turnaroundTime: Optional[int] = Field(None, description="Expected TAT")

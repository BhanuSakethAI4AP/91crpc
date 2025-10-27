"""
Purpose: Business logic for CrPC Request Pipelines operations.
Handles CRUD operations for pipeline line items.

Each pipeline represents one service request to one operator.
Auto-created from parent CrPC request.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.crpc_request_pipelines_models import (
    CrpcRequestPipelineCreateSchema,
    CrpcRequestPipelineUpdateSchema,
    CrpcRequestPipelineSearchSchema,
    PipelineStatusUpdateSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class CrpcRequestPipelineError(Exception):
    """Base exception for CrPC Request Pipeline operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class PipelineNotFoundError(CrpcRequestPipelineError):
    """Raised when pipeline is not found."""
    def __init__(self, pipeline_id: str):
        super().__init__(
            f"Pipeline with ID '{pipeline_id}' not found",
            "ERR.PIPELINE.NOT_FOUND"
        )


class InvalidOperatorError(CrpcRequestPipelineError):
    """Raised when operator is invalid for the service."""
    def __init__(self, operator_id: str, service_id: str):
        super().__init__(
            f"Operator '{operator_id}' is not valid for service '{service_id}'",
            "ERR.PIPELINE.INVALID_OPERATOR"
        )


class InvalidServiceError(CrpcRequestPipelineError):
    """Raised when service doesn't exist."""
    def __init__(self, service_id: str):
        super().__init__(
            f"Service '{service_id}' not found",
            "ERR.PIPELINE.INVALID_SERVICE"
        )


class DuplicatePipelineError(CrpcRequestPipelineError):
    """Raised when duplicate pipeline exists."""
    def __init__(self, request_id: str, line_item: int):
        super().__init__(
            f"Pipeline already exists for request '{request_id}' line item {line_item}",
            "ERR.PIPELINE.DUPLICATE"
        )


class DatabaseOperationError(CrpcRequestPipelineError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.PIPELINE.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class CrpcRequestPipelineService:
    """
    Service class for CrPC Request Pipeline operations.
    Manages individual service line items and their tracking.
    """
    
    def __init__(self):
        """Initialize service with database collections."""
        try:
            self.collection: Collection = get_collection("crpc_request_pipelines")
            self.service_collection: Collection = get_collection("service_master")
            self.operator_collection: Collection = get_collection("operators_list")
            self.operator_service_collection: Collection = get_collection("operator_service_list")
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== VALIDATION HELPERS ==========
    def _validate_service_exists(self, service_id: PyObjectId) -> dict:
        """Validate service exists."""
        service = self.service_collection.find_one({
            "_id": service_id,
            "isDeleted": False
        })
        
        if not service:
            raise InvalidServiceError(str(service_id))
        
        return service
    
    def _validate_operator_exists(self, operator_id: PyObjectId) -> dict:
        """Validate operator exists."""
        operator = self.operator_collection.find_one({
            "_id": operator_id,
            "isDeleted": False
        })
        
        if not operator:
            raise CrpcRequestPipelineError(
                f"Operator '{operator_id}' not found",
                "ERR.PIPELINE.OPERATOR_NOT_FOUND"
            )
        
        return operator
    
    def _validate_operator_for_service(
        self, 
        operator_id: PyObjectId, 
        service_id: PyObjectId
    ) -> None:
        """
        Validate that operator supports the service.
        Checks operator_service_list mapping.
        """
        # Check if mapping exists
        mapping = self.operator_service_collection.find_one({
            "serviceId": service_id,
            "operatorFormats.operatorId": operator_id,
            "isDeleted": False
        })
        
        if not mapping:
            raise InvalidOperatorError(str(operator_id), str(service_id))
    
    # ========== OPERATOR DETECTION ==========
    def detect_operator_for_service(
        self, 
        service_id: PyObjectId, 
        key_field_value: str
    ) -> PyObjectId:
        """
        Auto-detect operator based on service and key field value.
        
        Logic:
        1. For phone numbers: Use number series or operator_service_list
        2. For bank accounts: Use IFSC code
        3. Default: Return first operator that supports this service
        
        Args:
            service_id: Service ID
            key_field_value: Key field value (phone, account, etc.)
            
        Returns:
            PyObjectId: Detected operator ID
            
        Raises:
            InvalidServiceError: If service not found
            CrpcRequestPipelineError: If no operator found
        """
        try:
            # Get service details
            service = self._validate_service_exists(service_id)
            
            # Get all operator-service mappings for this service
            mappings = list(self.operator_service_collection.find({
                "serviceId": service_id,
                "isDeleted": False
            }))
            
            if not mappings:
                raise CrpcRequestPipelineError(
                    f"No operators configured for service '{service_id}'",
                    "ERR.PIPELINE.NO_OPERATORS_FOR_SERVICE"
                )
            
            # TODO: Implement smart operator detection logic
            # For now, return first operator from first mapping
            first_mapping = mappings[0]
            if first_mapping.get("operatorFormats") and len(first_mapping["operatorFormats"]) > 0:
                return first_mapping["operatorFormats"][0]["operatorId"]
            
            raise CrpcRequestPipelineError(
                f"No operator formats found for service '{service_id}'",
                "ERR.PIPELINE.NO_OPERATOR_FORMATS"
            )
            
        except CrpcRequestPipelineError:
            raise
        except Exception as e:
            raise DatabaseOperationError("DETECT_OPERATOR", str(e))
    
    # ========== CREATE Operation ==========
    def create_pipeline(
        self,
        data: CrpcRequestPipelineCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new pipeline.
        
        Auto-called when parent CrPC request is created.
        
        Args:
            data: Pipeline creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created pipeline document
            
        Raises:
            DuplicatePipelineError: If pipeline already exists
            InvalidServiceError: If service not found
            InvalidOperatorError: If operator invalid for service
            DatabaseOperationError: If database operation fails
        """
        try:
            # Validate service exists
            self._validate_service_exists(data.serviceId)
            
            # Validate operator exists
            self._validate_operator_exists(data.operatorId)
            
            # Validate operator supports this service
            self._validate_operator_for_service(data.operatorId, data.serviceId)
            
            # Check for duplicate
            existing = self.collection.find_one({
                "crpcRequestId": data.crpcRequestId,
                "lineItem": data.lineItem,
                "isActive": True
            })
            
            if existing:
                raise DuplicatePipelineError(str(data.crpcRequestId), data.lineItem)
            
            # Prepare document
            now = datetime.now(timezone.utc)
            pipeline_dict = data.model_dump()
            pipeline_dict["lineItemRequestStatus"] = data.lineItemRequestStatus.value
            
            document = {
                **pipeline_dict,
                "isActive": True,
                "createdAt": now,
                "createdBy": created_by,
                "createdIp": created_ip,
                "updatedAt": now,
                "updatedBy": created_by,
                "updatedIp": created_ip,
            }
            
            # Insert
            result = self.collection.insert_one(document)
            document["_id"] = result.inserted_id
            
            return document
            
        except CrpcRequestPipelineError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("CREATE", str(e))
        except Exception as e:
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation ==========
    def get_pipeline_by_id(self, pipeline_id: PyObjectId) -> Optional[dict]:
        """Get pipeline by ID."""
        try:
            result = self.collection.find_one({
                "_id": pipeline_id,
                "isActive": True
            })
            
            return result
            
        except PyMongoError as e:
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== GET BY REQUEST ID ==========
    def get_by_request_id(self, request_id: PyObjectId) -> List[dict]:
        """Get all pipelines for a CrPC request."""
        try:
            results = list(self.collection.find({
                "crpcRequestId": request_id,
                "isActive": True
            }).sort("lineItem", ASCENDING))
            
            return results
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_REQUEST", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_REQUEST", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation ==========
    def update_pipeline(
        self,
        pipeline_id: PyObjectId,
        data: CrpcRequestPipelineUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """Update pipeline."""
        try:
            # Check if exists
            existing = self.collection.find_one({
                "_id": pipeline_id,
                "isActive": True
            })
            
            if not existing:
                raise PipelineNotFoundError(str(pipeline_id))
            
            # Prepare update
            update_dict = data.model_dump(exclude_unset=True)
            
            # Validate operator if being updated
            if "operatorId" in update_dict and update_dict["operatorId"]:
                self._validate_operator_exists(update_dict["operatorId"])
                self._validate_operator_for_service(
                    update_dict["operatorId"],
                    existing["serviceId"]
                )
            
            if "lineItemRequestStatus" in update_dict:
                update_dict["lineItemRequestStatus"] = update_dict["lineItemRequestStatus"].value
            
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            # Update
            self.collection.update_one(
                {"_id": pipeline_id},
                {"$set": update_dict}
            )
            
            # Return updated document
            return self.collection.find_one({"_id": pipeline_id})
            
        except CrpcRequestPipelineError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("UPDATE", str(e))
        except Exception as e:
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE STATUS ==========
    def update_status(
        self,
        pipeline_id: PyObjectId,
        status_data: PipelineStatusUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> dict:
        """Update pipeline status."""
        try:
            existing = self.collection.find_one({
                "_id": pipeline_id,
                "isActive": True
            })
            
            if not existing:
                raise PipelineNotFoundError(str(pipeline_id))
            
            update_dict = {
                "lineItemRequestStatus": status_data.lineItemRequestStatus.value,
                "updatedAt": datetime.now(timezone.utc),
                "updatedBy": updated_by,
                "updatedIp": updated_ip
            }
            
            # Update
            self.collection.update_one(
                {"_id": pipeline_id},
                {"$set": update_dict}
            )
            
            return self.collection.find_one({"_id": pipeline_id})
            
        except CrpcRequestPipelineError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("UPDATE_STATUS", str(e))
        except Exception as e:
            raise DatabaseOperationError("UPDATE_STATUS", f"Unexpected error: {str(e)}")
    
    # ========== BULK UPDATE ==========
    def bulk_update(
        self,
        pipeline_ids: List[PyObjectId],
        updates: Dict[str, Any],
        updated_by: PyObjectId,
        updated_ip: str
    ) -> dict:
        """Bulk update multiple pipelines."""
        try:
            results = {
                "success": [],
                "failed": []
            }
            
            for pipeline_id in pipeline_ids:
                try:
                    # Prepare update data
                    update_data = CrpcRequestPipelineUpdateSchema(**updates)
                    
                    updated_pipeline = self.update_pipeline(
                        pipeline_id,
                        update_data,
                        updated_by,
                        updated_ip
                    )
                    
                    results["success"].append({
                        "pipelineId": str(pipeline_id),
                        "status": updated_pipeline["lineItemRequestStatus"]
                    })
                    
                except CrpcRequestPipelineError as e:
                    results["failed"].append({
                        "pipelineId": str(pipeline_id),
                        "error": e.error_code,
                        "message": e.message
                    })
            
            return results
            
        except Exception as e:
            raise DatabaseOperationError("BULK_UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation ==========
    def search_pipelines(
        self,
        search_params: CrpcRequestPipelineSearchSchema
    ) -> Tuple[List[dict], int]:
        """Search and filter pipelines with pagination."""
        try:
            # Build query
            query = {}
            
            if not search_params.includeInactive:
                query["isActive"] = True
            
            if search_params.crpcRequestId:
                query["crpcRequestId"] = search_params.crpcRequestId
            
            if search_params.operatorId:
                query["operatorId"] = search_params.operatorId
            
            if search_params.serviceId:
                query["serviceId"] = search_params.serviceId
            
            if search_params.lineItemRequestStatus:
                query["lineItemRequestStatus"] = search_params.lineItemRequestStatus.value
            
            if search_params.keyFieldValue:
                query["keyFieldValue"] = {"$regex": search_params.keyFieldValue, "$options": "i"}
            
            # Get total count
            total = self.collection.count_documents(query)
            
            # Build sort
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            
            # Calculate pagination
            skip = (search_params.page - 1) * search_params.pageSize
            
            # Execute query
            cursor = self.collection.find(query).sort(
                search_params.sortBy, sort_order
            ).skip(skip).limit(search_params.pageSize)
            
            results = list(cursor)
            
            return results, total
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH", str(e))
        except Exception as e:
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== GET PIPELINES WITH DETAILS ==========
    def get_pipelines_with_details(self, request_id: PyObjectId) -> List[dict]:
        """
        Get pipelines with joined service/operator names.
        Used for detailed view.
        """
        try:
            # Get pipelines
            pipelines = self.get_by_request_id(request_id)
            
            # Enrich with service and operator names
            enriched = []
            for pipeline in pipelines:
                # Get service name
                service = self.service_collection.find_one({"_id": pipeline["serviceId"]})
                pipeline["serviceName"] = service.get("serviceName") if service else "Unknown"
                
                # Get operator name
                operator = self.operator_collection.find_one({"_id": pipeline["operatorId"]})
                pipeline["operatorName"] = operator.get("operatorName") if operator else "Unknown"
                
                enriched.append(pipeline)
            
            return enriched
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_WITH_DETAILS", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_WITH_DETAILS", f"Unexpected error: {str(e)}")

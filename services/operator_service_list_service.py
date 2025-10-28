"""
Purpose: Business logic for Operator Service List operations.
Handles CRUD operations for operator-service mappings with comprehensive error handling.

UPDATED: Operator-centric design with globalFormat and service-specific overrides.
Based on TFS: OperatorServiceList.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.OPERATOR_SERVICE_LIST.*
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.operator_service_list_models import (
    OperatorServiceListCreateSchema,
    OperatorServiceListUpdateSchema,
    OperatorServiceListSearchSchema,
    FormatSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class OperatorServiceListError(Exception):
    """Base exception for Operator Service List operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DuplicateOperatorMappingError(OperatorServiceListError):
    """Raised when attempting to create duplicate operator mapping."""
    def __init__(self, operator_id: str):
        super().__init__(
            f"Operator mapping already exists for operator '{operator_id}'",
            "ERR.OPERATOR_SERVICE_LIST.CREATE.DUPLICATE_OPERATOR"
        )


class OperatorServiceNotFoundError(OperatorServiceListError):
    """Raised when operator service record is not found."""
    def __init__(self, record_id: str):
        super().__init__(
            f"Operator service mapping with ID '{record_id}' not found or has been deleted",
            "ERR.OPERATOR_SERVICE_LIST.NOT_FOUND"
        )


class InvalidServiceIdError(OperatorServiceListError):
    """Raised when service ID does not exist."""
    def __init__(self, service_id: str):
        super().__init__(
            f"Service ID '{service_id}' does not exist in service_master",
            "ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID"
        )


class InvalidOperatorIdError(OperatorServiceListError):
    """Raised when operator ID does not exist."""
    def __init__(self, operator_id: str):
        super().__init__(
            f"Operator ID '{operator_id}' does not exist in operators_list",
            "ERR.OPERATOR_SERVICE_LIST.INVALID_OPERATOR_ID"
        )


class NoFormatAvailableError(OperatorServiceListError):
    """Raised when neither global nor service-specific format is available."""
    def __init__(self, operator_id: str, service_id: str):
        super().__init__(
            f"No format available for operator '{operator_id}' and service '{service_id}'. "
            "Must have either globalFormat or serviceSpecificFormat.",
            "ERR.OPERATOR_SERVICE_LIST.NO_FORMAT_AVAILABLE"
        )


class DatabaseOperationError(OperatorServiceListError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.OPERATOR_SERVICE_LIST.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class OperatorServiceListService:
    """
    Service class for Operator Service List operations (Operator-Centric).
    Implements TFS functions: CREATE, READ, UPDATE, DELETE
    """
    
    def __init__(self):
        """Initialize service with database collections."""
        try:
            self.collection: Collection = get_collection("operator_service_list")
            self.service_master_collection: Collection = get_collection("service_master")
            self.operators_collection: Collection = get_collection("operators_list")
        except Exception as e:
            # ERROR: Database collection initialization failed
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== VALIDATION HELPERS ==========
    def _validate_operator_exists(self, operator_id: PyObjectId) -> dict:
        """
        Validate that operator ID exists in operators_list.
        
        TFS Precondition: operatorId exists in operators_list
        
        Returns:
            dict: Operator document
            
        Raises:
            InvalidOperatorIdError: If operator not found
        """
        try:
            operator = self.operators_collection.find_one({
                "_id": operator_id,
                "isDeleted": False
            })
            
            if not operator:
                raise InvalidOperatorIdError(str(operator_id))
            
            return operator
        except PyMongoError as e:
            raise DatabaseOperationError("VALIDATE_OPERATOR", str(e))
    
    def _validate_services_exist(self, service_ids: List[PyObjectId]) -> Dict[str, dict]:
        """
        Validate that all service IDs exist in service_master.
        
        TFS Precondition: all serviceIds exist in service_master
        
        Returns:
            Dict[str, dict]: Map of service_id -> service document
            
        Raises:
            InvalidServiceIdError: If any service not found
        """
        try:
            services_map = {}
            for service_id in service_ids:
                service = self.service_master_collection.find_one({
                    "_id": service_id,
                    "isDeleted": False
                })
                
                if not service:
                    raise InvalidServiceIdError(str(service_id))
                
                services_map[str(service_id)] = service
            
            return services_map
        except PyMongoError as e:
            raise DatabaseOperationError("VALIDATE_SERVICES", str(e))
    
    # ========== CREATE Operation (TFS: OperatorServiceList.CREATE) ==========
    def create_operator_service(
        self,
        data: OperatorServiceListCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new operator service mapping record (operator-centric).
        
        TFS Reference: OperatorServiceList.CREATE
        Error Codes:
            - ERR.OPERATOR_SERVICE_LIST.INVALID_OPERATOR_ID
            - ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID
            - ERR.OPERATOR_SERVICE_LIST.CREATE.DUPLICATE_OPERATOR
            - ERR.OPERATOR_SERVICE_LIST.NO_FORMAT_AVAILABLE
            - ERR.OPERATOR_SERVICE_LIST.CREATE.DB_ERROR
        
        Preconditions:
            - operatorId exists in operators_list
            - all serviceIds exist in service_master
            - no duplicate operator mapping
            - each service has format (global or specific)
        
        Args:
            data: Operator service creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created operator service document
            
        Raises:
            InvalidOperatorIdError: If operator ID not found
            InvalidServiceIdError: If any service ID not found
            DuplicateOperatorMappingError: If operator mapping already exists
            NoFormatAvailableError: If no format available for a service
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if operator exists ==========
            operator = self._validate_operator_exists(data.operatorId)
            
            # ========== VALIDATION: Check if operator mapping already exists ==========
            existing = self.collection.find_one({
                "operatorId": data.operatorId,
                "isDeleted": False
            })
            
            if existing:
                # ERROR: Operator mapping already exists
                # Log: LOG.OPERATOR_SERVICE_LIST.CREATE.END.ERROR.DUPLICATE
                raise DuplicateOperatorMappingError(str(data.operatorId))
            
            # ========== VALIDATION: Check if all services exist ==========
            service_ids = [svc.serviceId for svc in data.services]
            services_map = self._validate_services_exist(service_ids)
            
            # ========== VALIDATION: Ensure format availability ==========
            for service_config in data.services:
                if not service_config.serviceSpecificFormat and not data.globalFormat:
                    # ERROR: No format available
                    raise NoFormatAvailableError(str(data.operatorId), str(service_config.serviceId))
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            
            # Convert Pydantic models to dict
            operator_service_dict = data.model_dump()
            
            # Add denormalized operator name if not provided
            if not operator_service_dict.get("operatorName"):
                operator_service_dict["operatorName"] = operator.get("operatorName")
            
            # Add denormalized service names if not provided
            for i, service_config in enumerate(operator_service_dict["services"]):
                if not service_config.get("serviceName"):
                    service_doc = services_map.get(str(service_config["serviceId"]))
                    if service_doc:
                        operator_service_dict["services"][i]["serviceName"] = service_doc.get("serviceName")
            
            document = {
                **operator_service_dict,
                "isDeleted": False,
                "createdAt": now,
                "createdBy": created_by,
                "createdIp": created_ip,
                "updatedAt": now,
                "updatedBy": created_by,
                "updatedIp": created_ip,
            }
            
            # ========== DATABASE INSERT ==========
            try:
                result = self.collection.insert_one(document)
                document["_id"] = result.inserted_id
            except PyMongoError as e:
                # ERROR: Database insert operation failed
                # Log: LOG.OPERATOR_SERVICE_LIST.CREATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("CREATE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATOR_SERVICE_LIST.CREATE.END.SUCCESS (INFO)
            # TODO: Implement logging
            # self._log_event("CREATE", "SUCCESS", document["_id"], created_by)
            
            # NOTIFICATION: In-App and Email notification required
            # Channels: In-App, Email
            # Template Tokens: {{operatorId}}, {{operatorName}}, {{services}}
            # TODO: Implement notification service
            # self._notify_operator_service_created(document, created_by)
            
            return document
            
        except OperatorServiceListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during create operation
            # Log: LOG.OPERATOR_SERVICE_LIST.CREATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation (TFS: OperatorServiceList.READ) ==========
    def get_operator_service_by_id(self, record_id: PyObjectId) -> Optional[dict]:
        """
        Get operator service mapping by ID.
        
        TFS Reference: OperatorServiceList.READ
        Error Codes: ERR.OPERATOR_SERVICE_LIST.READ.NOT_FOUND
        
        Args:
            record_id: Operator service mapping ID
            
        Returns:
            dict: Operator service document or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE QUERY ==========
            result = self.collection.find_one({
                "_id": record_id,
                "isDeleted": False
            })
            
            if result:
                # Log: LOG.OPERATOR_SERVICE_LIST.READ.END.SUCCESS
                pass  # TODO: Implement logging
            
            return result
            
        except PyMongoError as e:
            # ERROR: Database query failed
            # Log: LOG.OPERATOR_SERVICE_LIST.READ.END.ERROR.DB_FAILED
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            # ERROR: Unexpected error during read operation
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== GET BY OPERATOR ID (Primary Lookup) ==========
    def get_by_operator_id(self, operator_id: PyObjectId) -> Optional[dict]:
        """
        Get operator service mapping for a specific operator.
        
        PRIMARY LOOKUP METHOD (operator-centric design).
        
        Args:
            operator_id: Operator ID to query
            
        Returns:
            dict: Operator service mapping or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = self.collection.find_one({
                "operatorId": operator_id,
                "isDeleted": False
            })
            
            return result
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_OPERATOR", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_OPERATOR", f"Unexpected error: {str(e)}")
    
    # ========== GET FORMAT FOR SERVICE (Format Resolution) ==========
    def get_format_for_service(
        self,
        operator_id: PyObjectId,
        service_id: PyObjectId
    ) -> Dict[str, Any]:
        """
        Get the resolved format configuration for a specific operator-service combination.
        
        Resolution Logic:
        1. Find operator config
        2. Find service in services[]
        3. If serviceSpecificFormat exists, return it
        4. Else return globalFormat
        
        Args:
            operator_id: Operator ID
            service_id: Service ID
            
        Returns:
            dict: Resolved format with metadata
                {
                    "operatorId": ObjectId,
                    "operatorName": str,
                    "serviceId": ObjectId,
                    "serviceName": str,
                    "formatSource": "global" | "service-specific",
                    "format": FormatSchema,
                    "requiredData": dict,
                    "maxDateRange": int,
                    "turnaroundTime": int
                }
            
        Raises:
            OperatorServiceNotFoundError: If operator mapping not found
            InvalidServiceIdError: If service not found in operator's services
            NoFormatAvailableError: If no format available
            DatabaseOperationError: If database operation fails
        """
        try:
            # Get operator config
            operator_config = self.get_by_operator_id(operator_id)
            
            if not operator_config:
                raise OperatorServiceNotFoundError(f"No mapping found for operator {operator_id}")
            
            # Find service in services array
            service_config = None
            for svc in operator_config.get("services", []):
                if svc.get("serviceId") == service_id:
                    service_config = svc
                    break
            
            if not service_config:
                raise InvalidServiceIdError(f"Service {service_id} not configured for operator {operator_id}")
            
            # Resolve format
            if service_config.get("serviceSpecificFormat"):
                format_data = service_config["serviceSpecificFormat"]
                format_source = "service-specific"
            elif operator_config.get("globalFormat"):
                format_data = operator_config["globalFormat"]
                format_source = "global"
            else:
                raise NoFormatAvailableError(str(operator_id), str(service_id))
            
            # Build response
            return {
                "operatorId": operator_config["operatorId"],
                "operatorName": operator_config.get("operatorName", ""),
                "serviceId": service_config["serviceId"],
                "serviceName": service_config.get("serviceName", ""),
                "formatSource": format_source,
                "format": format_data,
                "requiredData": service_config.get("requiredData", {}),
                "maxDateRange": service_config.get("maxDateRange"),
                "turnaroundTime": service_config.get("turnaroundTime")
            }
            
        except OperatorServiceListError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("GET_FORMAT", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_FORMAT", f"Unexpected error: {str(e)}")
    
    # ========== GET SERVICES BY OPERATOR ==========
    def get_services_by_operator(self, operator_id: PyObjectId) -> List[dict]:
        """
        Get list of services provided by an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            List[dict]: List of service configurations
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            operator_config = self.get_by_operator_id(operator_id)
            
            if not operator_config:
                return []
            
            return operator_config.get("services", [])
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_SERVICES", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_SERVICES", f"Unexpected error: {str(e)}")
    
    # ========== GET OPERATORS FOR SERVICE ==========
    def get_operators_for_service(self, service_id: PyObjectId) -> List[dict]:
        """
        Get all operators that provide a specific service.
        
        Args:
            service_id: Service ID
            
        Returns:
            List[dict]: List of operator configs that include this service
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            results = list(self.collection.find({
                "services.serviceId": service_id,
                "services.isActive": True,
                "isDeleted": False
            }))
            
            return results
        except PyMongoError as e:
            raise DatabaseOperationError("GET_OPERATORS_FOR_SERVICE", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_OPERATORS_FOR_SERVICE", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation (TFS: OperatorServiceList.UPDATE) ==========
    def update_operator_service(
        self,
        record_id: PyObjectId,
        data: OperatorServiceListUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """
        Update operator service mapping record.
        
        TFS Reference: OperatorServiceList.UPDATE
        Error Codes:
            - ERR.OPERATOR_SERVICE_LIST.NOT_FOUND
            - ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID
            - ERR.OPERATOR_SERVICE_LIST.UPDATE.DB_ERROR
        
        Preconditions:
            - _id exists and not deleted
        
        Args:
            record_id: Operator service mapping ID to update
            data: Update data (partial)
            updated_by: User ID performing the update
            updated_ip: IP address of the updater
            
        Returns:
            dict: Updated operator service document or None if not found
            
        Raises:
            OperatorServiceNotFoundError: If record not found or deleted
            InvalidServiceIdError: If any service ID not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if record exists ==========
            existing = self.collection.find_one({
                "_id": record_id,
                "isDeleted": False
            })
            
            if not existing:
                # ERROR: Operator service mapping not found
                # Log: LOG.OPERATOR_SERVICE_LIST.UPDATE.END.ERROR.NOT_FOUND
                raise OperatorServiceNotFoundError(str(record_id))
            
            # ========== PREPARE UPDATE DATA ==========
            update_dict = data.model_dump(exclude_unset=True)
            
            # ========== VALIDATION: Validate service IDs if being updated ==========
            if "services" in update_dict and update_dict["services"] is not None:
                service_ids = [svc.serviceId for svc in data.services]
                self._validate_services_exist(service_ids)
            
            # ========== ADD AUDIT FIELDS ==========
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            # ========== DATABASE UPDATE ==========
            try:
                result = self.collection.update_one(
                    {"_id": record_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    # WARNING: No changes made (data same as existing)
                    pass  # Not an error, just informational
                
            except PyMongoError as e:
                # ERROR: Database update operation failed
                # Log: LOG.OPERATOR_SERVICE_LIST.UPDATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("UPDATE", str(e))
            
            # ========== FETCH UPDATED DOCUMENT ==========
            updated_document = self.collection.find_one({"_id": record_id})
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATOR_SERVICE_LIST.UPDATE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("UPDATE", "SUCCESS", record_id, updated_by)
            
            # NOTIFICATION: In-App notification required
            # Template Tokens: {{_id}}, {{operatorName}}, {{services}}
            # TODO: Implement notification service
            # self._notify_operator_service_updated(updated_document, updated_by)
            
            return updated_document
            
        except OperatorServiceListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during update operation
            # Log: LOG.OPERATOR_SERVICE_LIST.UPDATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== DELETE Operation (TFS: OperatorServiceList.DELETE) ==========
    def delete_operator_service(
        self,
        record_id: PyObjectId,
        deleted_by: PyObjectId,
        deleted_ip: str
    ) -> bool:
        """
        Soft delete operator service mapping record.
        
        TFS Reference: OperatorServiceList.DELETE
        Error Codes:
            - ERR.OPERATOR_SERVICE_LIST.NOT_FOUND
            - ERR.OPERATOR_SERVICE_LIST.DELETE.DB_ERROR
        
        Preconditions:
            - _id exists and not already deleted
        
        Postconditions:
            - isDeleted=true
            - audit fields updated
        
        Args:
            record_id: Operator service mapping ID to delete
            deleted_by: User ID performing the deletion
            deleted_ip: IP address of the deleter
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            OperatorServiceNotFoundError: If record not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE SOFT DELETE ==========
            # TFS: Set isDeleted = True, update audit fields
            try:
                result = self.collection.update_one(
                    {"_id": record_id, "isDeleted": False},
                    {
                        "$set": {
                            "isDeleted": True,
                            "updatedAt": datetime.now(timezone.utc),
                            "updatedBy": deleted_by,
                            "updatedIp": deleted_ip,
                        }
                    }
                )
                
                if result.matched_count == 0:
                    # ERROR: Operator service mapping not found or already deleted
                    # Log: LOG.OPERATOR_SERVICE_LIST.DELETE.END.ERROR.NOT_FOUND
                    raise OperatorServiceNotFoundError(str(record_id))
                
            except PyMongoError as e:
                # ERROR: Database delete operation failed
                # Log: LOG.OPERATOR_SERVICE_LIST.DELETE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("DELETE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATOR_SERVICE_LIST.DELETE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("DELETE", "SUCCESS", record_id, deleted_by)
            
            # NOTIFICATION: In-App notification required
            # Template Tokens: {{_id}}
            # TODO: Implement notification service
            # self._notify_operator_service_deleted(record_id, deleted_by)
            
            return result.modified_count > 0
            
        except OperatorServiceListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during delete operation
            # Log: LOG.OPERATOR_SERVICE_LIST.DELETE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("DELETE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation (Extended TFS: OperatorServiceList.READ) ==========
    def search_operator_services(
        self,
        search_params: OperatorServiceListSearchSchema
    ) -> Tuple[List[dict], int]:
        """
        Search and filter operator service mappings with pagination.
        
        TFS Reference: OperatorServiceList.READ (extended)
        Supports: filtering by operatorId/serviceId/operatorName, sorting, pagination
        
        Args:
            search_params: Search and filter criteria
            
        Returns:
            Tuple[List[dict], int]: (list of documents, total count)
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== BUILD QUERY FILTER ==========
            query = {}
            
            # Include/exclude deleted records
            if not search_params.includeDeleted:
                query["isDeleted"] = False
            
            # Operator ID filter (PRIMARY)
            if search_params.operatorId:
                query["operatorId"] = search_params.operatorId
            
            # Service ID filter (within services array)
            if search_params.serviceId:
                query["services.serviceId"] = search_params.serviceId
            
            # Operator name filter (partial match)
            if search_params.operatorName:
                query["operatorName"] = {
                    "$regex": search_params.operatorName,
                    "$options": "i"  # case-insensitive
                }
            
            # ========== GET TOTAL COUNT ==========
            try:
                total = self.collection.count_documents(query)
            except PyMongoError as e:
                # ERROR: Count operation failed
                raise DatabaseOperationError("SEARCH.COUNT", str(e))
            
            # ========== BUILD SORT ==========
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            sort_field = search_params.sortBy
            
            # ========== CALCULATE PAGINATION ==========
            skip = (search_params.page - 1) * search_params.pageSize
            
            # ========== EXECUTE QUERY ==========
            try:
                cursor = self.collection.find(query).sort(
                    sort_field, sort_order
                ).skip(skip).limit(search_params.pageSize)
                
                results = list(cursor)
            except PyMongoError as e:
                # ERROR: Search query execution failed
                raise DatabaseOperationError("SEARCH.QUERY", str(e))
            
            # Log: LOG.OPERATOR_SERVICE_LIST.READ.END.SUCCESS
            # TODO: Implement logging
            
            return results, total
            
        except OperatorServiceListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during search operation
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== UTILITY: Get all operator service mappings ==========
    def get_all_operator_services(self, include_deleted: bool = False) -> List[dict]:
        """
        Get all operator service mappings.
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List[dict]: List of all operator service documents
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            query = {} if include_deleted else {"isDeleted": False}
            return list(self.collection.find(query).sort("operatorName", ASCENDING))
        except PyMongoError as e:
            # ERROR: Get all operation failed
            raise DatabaseOperationError("GET_ALL", str(e))
        except Exception as e:
            # ERROR: Unexpected error
            raise DatabaseOperationError("GET_ALL", f"Unexpected error: {str(e)}")
    
    # ========== PLACEHOLDER: Logging Methods ==========
    # TODO: Implement actual logging service integration
    
    def _log_event(self, operation: str, status: str, record_id: PyObjectId, user_id: PyObjectId):
        """
        Log operator service operation event.
        
        Logs:
            - LOG.OPERATOR_SERVICE_LIST.{operation}.END.{status}
        
        TODO: Implement actual logging to database or external service
        """
        pass
    
    # ========== PLACEHOLDER: Notification Methods ==========
    # TODO: Implement actual notification service integration
    
    def _notify_operator_service_created(self, document: dict, user_id: PyObjectId):
        """
        Send notification when operator service mapping is created.
        
        Notification Type: In-App, Email
        Template Tokens: {{operatorId}}, {{operatorName}}, {{services}}
        TODO: Implement notification service
        """
        pass
    
    def _notify_operator_service_updated(self, document: dict, user_id: PyObjectId):
        """
        Send notification when operator service mapping is updated.
        
        Notification Type: In-App
        Template Tokens: {{_id}}, {{operatorName}}, {{services}}
        TODO: Implement notification service
        """
        pass
    
    def _notify_operator_service_deleted(self, record_id: PyObjectId, user_id: PyObjectId):
        """
        Send notification when operator service mapping is deleted.
        
        Notification Type: In-App
        Template Tokens: {{_id}}
        TODO: Implement notification service
        """
        pass

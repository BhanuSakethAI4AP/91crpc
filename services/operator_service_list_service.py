"""
Purpose: Business logic for Operator Service List operations.
Handles CRUD operations for operator-service mappings with comprehensive error handling.

Based on TFS: OperatorServiceList.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.OPERATOR_SERVICE_LIST.*
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.operator_service_list_models import (
    OperatorServiceListCreateSchema,
    OperatorServiceListUpdateSchema,
    OperatorServiceListSearchSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class OperatorServiceListError(Exception):
    """Base exception for Operator Service List operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DuplicateOperatorFormatError(OperatorServiceListError):
    """Raised when attempting to create duplicate operator format mapping."""
    def __init__(self, service_id: str, operator_id: str):
        super().__init__(
            f"Operator format mapping already exists for service '{service_id}' and operator '{operator_id}'",
            "ERR.OPERATOR_SERVICE_LIST.CREATE.DUPLICATE_OPERATOR_FORMAT"
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
    Service class for Operator Service List operations.
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
    def _validate_service_exists(self, service_id: PyObjectId) -> None:
        """
        Validate that service ID exists in service_master.
        
        TFS Precondition: serviceId exists in service_master
        
        Raises:
            InvalidServiceIdError: If service not found
        """
        try:
            exists = self.service_master_collection.find_one({
                "_id": service_id,
                "isDeleted": False
            })
            
            if not exists:
                raise InvalidServiceIdError(str(service_id))
        except PyMongoError as e:
            raise DatabaseOperationError("VALIDATE_SERVICE", str(e))
    
    def _validate_operators_exist(self, operator_ids: List[PyObjectId]) -> None:
        """
        Validate that all operator IDs exist in operators_list.
        
        TFS Precondition: all operatorIds exist in operators_list
        
        Raises:
            InvalidOperatorIdError: If any operator not found
        """
        try:
            for operator_id in operator_ids:
                exists = self.operators_collection.find_one({
                    "_id": operator_id,
                    "isDeleted": False
                })
                
                if not exists:
                    raise InvalidOperatorIdError(str(operator_id))
        except PyMongoError as e:
            raise DatabaseOperationError("VALIDATE_OPERATORS", str(e))
    
    # ========== CREATE Operation (TFS: OperatorServiceList.CREATE) ==========
    def create_operator_service(
        self,
        data: OperatorServiceListCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new operator service mapping record.
        
        TFS Reference: OperatorServiceList.CREATE
        Error Codes:
            - ERR.OPERATOR_SERVICE_LIST.INVALID_SERVICE_ID
            - ERR.OPERATOR_SERVICE_LIST.INVALID_OPERATOR_ID
            - ERR.OPERATOR_SERVICE_LIST.CREATE.DUPLICATE_OPERATOR_FORMAT
            - ERR.OPERATOR_SERVICE_LIST.CREATE.DB_ERROR
        
        Preconditions:
            - serviceId exists in service_master
            - all operatorIds exist in operators_list
            - no duplicate operatorFormats per serviceId
        
        Args:
            data: Operator service creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created operator service document
            
        Raises:
            InvalidServiceIdError: If service ID not found
            InvalidOperatorIdError: If any operator ID not found
            DuplicateOperatorFormatError: If mapping already exists
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if service exists ==========
            # TFS Precondition: serviceId exists in service_master
            self._validate_service_exists(data.serviceId)
            
            # ========== VALIDATION: Check if all operators exist ==========
            # TFS Precondition: all operatorIds exist in operators_list
            operator_ids = [fmt.operatorId for fmt in data.operatorFormats]
            self._validate_operators_exist(operator_ids)
            
            # ========== VALIDATION: Check for duplicate operator formats ==========
            # TFS Precondition: no duplicate operatorFormats per serviceId
            for operator_id in operator_ids:
                existing = self.collection.find_one({
                    "serviceId": data.serviceId,
                    "operatorFormats.operatorId": operator_id,
                    "isDeleted": False
                })
                
                if existing:
                    # ERROR: Duplicate operator format mapping
                    # Log: LOG.OPERATOR_SERVICE_LIST.CREATE.END.ERROR.DUPLICATE
                    raise DuplicateOperatorFormatError(str(data.serviceId), str(operator_id))
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            
            # Convert Pydantic models to dict
            operator_service_dict = data.model_dump()
            
            # Convert nested Pydantic models to dicts
            operator_service_dict["operatorFormats"] = [
                {
                    "operatorId": fmt.operatorId,
                    "formatFilePath": fmt.formatFilePath,
                    "listOfAttachments": [
                        att.model_dump() for att in fmt.listOfAttachments
                    ]
                }
                for fmt in data.operatorFormats
            ]
            
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
            # Template Tokens: {{serviceId}}, {{operatorFormats}}
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
    
    # ========== GET BY SERVICE ID ==========
    def get_by_service_id(self, service_id: PyObjectId) -> List[dict]:
        """
        Get all operator service mappings for a specific service.
        
        Args:
            service_id: Service ID to filter by
            
        Returns:
            List[dict]: List of operator service mappings
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            results = list(self.collection.find({
                "serviceId": service_id,
                "isDeleted": False
            }).sort("createdAt", DESCENDING))
            
            return results
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_SERVICE", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_SERVICE", f"Unexpected error: {str(e)}")
    
    # ========== GET BY OPERATOR ID ==========
    def get_by_operator_id(self, operator_id: PyObjectId) -> List[dict]:
        """
        Get all operator service mappings for a specific operator.
        
        Args:
            operator_id: Operator ID to filter by
            
        Returns:
            List[dict]: List of operator service mappings
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            results = list(self.collection.find({
                "operatorFormats.operatorId": operator_id,
                "isDeleted": False
            }).sort("createdAt", DESCENDING))
            
            return results
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_OPERATOR", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_OPERATOR", f"Unexpected error: {str(e)}")
    
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
            - ERR.OPERATOR_SERVICE_LIST.INVALID_OPERATOR_ID
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
            InvalidOperatorIdError: If any operator ID not found
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
            
            # ========== VALIDATION: Validate operator IDs if being updated ==========
            if "operatorFormats" in update_dict and update_dict["operatorFormats"] is not None:
                operator_ids = [fmt.operatorId for fmt in data.operatorFormats]
                self._validate_operators_exist(operator_ids)
                
                # Convert nested Pydantic models to dicts
                update_dict["operatorFormats"] = [
                    {
                        "operatorId": fmt.operatorId,
                        "formatFilePath": fmt.formatFilePath,
                        "listOfAttachments": [
                            att.model_dump() for att in fmt.listOfAttachments
                        ]
                    }
                    for fmt in data.operatorFormats
                ]
            
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
            # Template Tokens: {{_id}}, {{operatorFormats}}
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
        Supports: filtering by serviceId/operatorId, sorting, pagination
        
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
            
            # Service ID filter
            if search_params.serviceId:
                query["serviceId"] = search_params.serviceId
            
            # Operator ID filter (within operatorFormats array)
            if search_params.operatorId:
                query["operatorFormats.operatorId"] = search_params.operatorId
            
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
            return list(self.collection.find(query).sort("createdAt", DESCENDING))
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
        Template Tokens: {{serviceId}}, {{operatorFormats}}
        TODO: Implement notification service
        """
        pass
    
    def _notify_operator_service_updated(self, document: dict, user_id: PyObjectId):
        """
        Send notification when operator service mapping is updated.
        
        Notification Type: In-App
        Template Tokens: {{_id}}, {{operatorFormats}}
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

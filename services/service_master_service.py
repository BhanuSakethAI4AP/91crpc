#path: backend/services/service_master_service.py
"""
Purpose: Business logic for Service Master operations.
Handles CRUD operations, search, filtering, and sorting with comprehensive error handling.

Based on TFS: ServiceMaster.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.SERVICE_MASTER.*
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId

from database import get_collection
from models.service_master_models import (
    ServiceMasterCreateSchema,
    ServiceMasterUpdateSchema,
    ServiceMasterSearchSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class ServiceMasterError(Exception):
    """Base exception for Service Master operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DuplicateServiceError(ServiceMasterError):
    """Raised when attempting to create a duplicate service name."""
    def __init__(self, service_name: str):
        super().__init__(
            f"Service with name '{service_name}' already exists",
            "ERR.SERVICE_MASTER.CREATE.DUPLICATE"
        )


class ServiceNotFoundError(ServiceMasterError):
    """Raised when service master record is not found."""
    def __init__(self, service_id: str):
        super().__init__(
            f"Service master with ID '{service_id}' not found or has been deleted",
            "ERR.SERVICE_MASTER.NOT_FOUND"
        )


class InvalidOperatorTypeError(ServiceMasterError):
    """Raised when operator type validation fails."""
    def __init__(self, operator_type: str):
        super().__init__(
            f"Invalid operator type '{operator_type}'. Must be telecom, bank, or isp",
            "ERR.SERVICE_MASTER.INVALID_OPERATOR_TYPE"
        )


class DatabaseOperationError(ServiceMasterError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.SERVICE_MASTER.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class ServiceMasterService:
    """
    Service class for Service Master operations.
    Implements TFS functions: CREATE, READ, UPDATE, DELETE
    """
    
    def __init__(self):
        """Initialize service with database collection."""
        try:
            self.collection: Collection = get_collection("service_master")
        except Exception as e:
            # ERROR: Database collection initialization failed
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== CREATE Operation (TFS: ServiceMaster.CREATE) ==========
    def create_service_master(
        self,
        data: ServiceMasterCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new service master record.
        
        TFS Reference: ServiceMaster.CREATE
        Error Codes: 
            - ERR.SERVICE_MASTER.CREATE.DUPLICATE
            - ERR.SERVICE_MASTER.CREATE.DB_ERROR
        
        Args:
            data: Service master creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created service master document
            
        Raises:
            DuplicateServiceError: If service name already exists
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check for duplicate serviceName ==========
            # TFS Precondition: serviceName must be unique among non-deleted entries
            existing = self.collection.find_one({
                "serviceName": data.serviceName,
                "isDeleted": False
            })
            
            if existing:
                # ERROR: Duplicate service name detected
                # Log: LOG.SERVICE_MASTER.CREATE.END.ERROR.DUPLICATE
                raise DuplicateServiceError(data.serviceName)
            
            # ========== VALIDATION: Operator types already validated by Pydantic ==========
            # Pydantic validator ensures operatorType values are in valid set
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            document = {
                **data.model_dump(),
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
            except DuplicateKeyError as e:
                # ERROR: Unique index violation (serviceName)
                # This shouldn't happen due to pre-check, but handle it
                raise DuplicateServiceError(data.serviceName)
            except PyMongoError as e:
                # ERROR: Database insert operation failed
                # Log: LOG.SERVICE_MASTER.CREATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("CREATE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.SERVICE_MASTER.CREATE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("CREATE", "SUCCESS", document["_id"], created_by)
            
            # NOTIFICATION: In-App notification required
            # TODO: Implement notification service
            # self._notify_service_created(document, created_by)
            
            return document
            
        except ServiceMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during create operation
            # Log: LOG.SERVICE_MASTER.CREATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation (TFS: ServiceMaster.READ) ==========
    def get_service_master_by_id(self, service_id: PyObjectId) -> Optional[dict]:
        """
        Get service master by ID.
        
        TFS Reference: ServiceMaster.READ
        Error Codes: ERR.SERVICE_MASTER.READ.NOT_FOUND
        
        Args:
            service_id: Service master ID
            
        Returns:
            dict: Service master document or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE QUERY ==========
            result = self.collection.find_one({
                "_id": service_id,
                "isDeleted": False
            })
            
            if result:
                # Log: LOG.SERVICE_MASTER.READ.END.SUCCESS
                pass  # TODO: Implement logging
            
            return result
            
        except PyMongoError as e:
            # ERROR: Database query failed
            # Log: LOG.SERVICE_MASTER.READ.END.ERROR.DB_FAILED
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            # ERROR: Unexpected error during read operation
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation (TFS: ServiceMaster.UPDATE) ==========
    def update_service_master(
        self,
        service_id: PyObjectId,
        data: ServiceMasterUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """
        Update service master record.
        
        TFS Reference: ServiceMaster.UPDATE
        Error Codes:
            - ERR.SERVICE_MASTER.NOT_FOUND
            - ERR.SERVICE_MASTER.UPDATE.DUPLICATE
            - ERR.SERVICE_MASTER.UPDATE.DB_ERROR
        
        Args:
            service_id: Service master ID to update
            data: Update data (partial)
            updated_by: User ID performing the update
            updated_ip: IP address of the updater
            
        Returns:
            dict: Updated service master document or None if not found
            
        Raises:
            ServiceNotFoundError: If service not found or deleted
            DuplicateServiceError: If service name conflict
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if record exists ==========
            existing = self.collection.find_one({
                "_id": service_id,
                "isDeleted": False
            })
            
            if not existing:
                # ERROR: Service master not found
                # Log: LOG.SERVICE_MASTER.UPDATE.END.ERROR.NOT_FOUND
                raise ServiceNotFoundError(str(service_id))
            
            # ========== PREPARE UPDATE DATA ==========
            update_dict = data.model_dump(exclude_unset=True)
            
            # ========== VALIDATION: Check service name uniqueness if being updated ==========
            if "serviceName" in update_dict and update_dict["serviceName"] != existing["serviceName"]:
                name_conflict = self.collection.find_one({
                    "serviceName": update_dict["serviceName"],
                    "isDeleted": False,
                    "_id": {"$ne": service_id}
                })
                
                if name_conflict:
                    # ERROR: Duplicate service name
                    # Log: LOG.SERVICE_MASTER.UPDATE.END.ERROR.DUPLICATE
                    raise DuplicateServiceError(update_dict["serviceName"])
            
            # ========== ADD AUDIT FIELDS ==========
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            # ========== DATABASE UPDATE ==========
            try:
                result = self.collection.update_one(
                    {"_id": service_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    # WARNING: No changes made (data same as existing)
                    pass  # Not an error, just informational
                
            except PyMongoError as e:
                # ERROR: Database update operation failed
                # Log: LOG.SERVICE_MASTER.UPDATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("UPDATE", str(e))
            
            # ========== FETCH UPDATED DOCUMENT ==========
            updated_document = self.collection.find_one({"_id": service_id})
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.SERVICE_MASTER.UPDATE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("UPDATE", "SUCCESS", service_id, updated_by)
            
            # NOTIFICATION: In-App notification required
            # TODO: Implement notification service
            # self._notify_service_updated(updated_document, updated_by)
            
            return updated_document
            
        except ServiceMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during update operation
            # Log: LOG.SERVICE_MASTER.UPDATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== DELETE Operation (TFS: ServiceMaster.DELETE) ==========
    def delete_service_master(
        self,
        service_id: PyObjectId,
        deleted_by: PyObjectId,
        deleted_ip: str
    ) -> bool:
        """
        Soft delete service master record.
        
        TFS Reference: ServiceMaster.DELETE
        Error Codes:
            - ERR.SERVICE_MASTER.NOT_FOUND
            - ERR.SERVICE_MASTER.DELETE.DB_ERROR
        
        Args:
            service_id: Service master ID to delete
            deleted_by: User ID performing the deletion
            deleted_ip: IP address of the deleter
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            ServiceNotFoundError: If service not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE SOFT DELETE ==========
            # TFS: Set isDeleted = True, update audit fields
            try:
                result = self.collection.update_one(
                    {"_id": service_id, "isDeleted": False},
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
                    # ERROR: Service master not found or already deleted
                    # Log: LOG.SERVICE_MASTER.DELETE.END.ERROR.NOT_FOUND
                    raise ServiceNotFoundError(str(service_id))
                
            except PyMongoError as e:
                # ERROR: Database delete operation failed
                # Log: LOG.SERVICE_MASTER.DELETE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("DELETE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.SERVICE_MASTER.DELETE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("DELETE", "SUCCESS", service_id, deleted_by)
            
            # NOTIFICATION: In-App notification required
            # TODO: Implement notification service
            # self._notify_service_deleted(service_id, deleted_by)
            
            return result.modified_count > 0
            
        except ServiceMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during delete operation
            # Log: LOG.SERVICE_MASTER.DELETE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("DELETE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation (Extended TFS: ServiceMaster.READ) ==========
    def search_service_masters(
        self,
        search_params: ServiceMasterSearchSchema
    ) -> Tuple[list[dict], int]:
        """
        Search and filter service masters with pagination.
        
        TFS Reference: ServiceMaster.READ (extended)
        Supports: filtering, sorting, pagination
        
        Args:
            search_params: Search and filter criteria
            
        Returns:
            Tuple[list[dict], int]: (list of documents, total count)
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== BUILD QUERY FILTER ==========
            query = {}
            
            # Include/exclude deleted records
            if not search_params.includeDeleted:
                query["isDeleted"] = False
            
            # Service name search (case-insensitive partial match)
            if search_params.serviceName:
                query["serviceName"] = {
                    "$regex": search_params.serviceName,
                    "$options": "i"  # Case-insensitive
                }
            
            # Operator type filter (exact match in array)
            if search_params.operatorType:
                query["operatorType"] = search_params.operatorType.lower()
            
            # Can be consolidated filter
            if search_params.canBeConsolidated is not None:
                query["canBeConsolidated"] = search_params.canBeConsolidated
            
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
            
            # Log: LOG.SERVICE_MASTER.READ.END.SUCCESS
            # TODO: Implement logging
            
            return results, total
            
        except ServiceMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during search operation
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== UTILITY: Get all service masters (for dropdowns) ==========
    def get_all_service_masters(self, include_deleted: bool = False) -> list[dict]:
        """
        Get all service masters (for dropdowns, etc.).
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            list[dict]: List of all service master documents
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            query = {} if include_deleted else {"isDeleted": False}
            return list(self.collection.find(query).sort("serviceName", ASCENDING))
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
        Log service master operation event.
        
        Logs:
            - LOG.SERVICE_MASTER.{operation}.END.{status}
        
        TODO: Implement actual logging to database or external service
        """
        pass
    
    # ========== PLACEHOLDER: Notification Methods ==========
    # TODO: Implement actual notification service integration
    
    def _notify_service_created(self, document: dict, user_id: PyObjectId):
        """
        Send notification when service is created.
        
        Notification Type: In-App
        TODO: Implement notification service
        """
        pass
    
    def _notify_service_updated(self, document: dict, user_id: PyObjectId):
        """
        Send notification when service is updated.
        
        Notification Type: In-App
        TODO: Implement notification service
        """
        pass
    
    def _notify_service_deleted(self, service_id: PyObjectId, user_id: PyObjectId):
        """
        Send notification when service is deleted.
        
        Notification Type: In-App
        TODO: Implement notification service
        """
        pass

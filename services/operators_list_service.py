"""
Purpose: Business logic for Operators List operations.
Handles CRUD operations, search, filtering with comprehensive error handling.

Based on TFS: OperatorsList.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.OPERATORS_LIST.*
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId

from database import get_collection
from models.operators_list_models import (
    OperatorsListCreateSchema,
    OperatorsListUpdateSchema,
    OperatorsListSearchSchema,
)
from utils.validators import PyObjectId
from constants.value_sets import OperatorType


# ========== Custom Exceptions ==========
class OperatorsListError(Exception):
    """Base exception for Operators List operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DuplicateOperatorError(OperatorsListError):
    """Raised when attempting to create a duplicate operator name/type combination."""
    def __init__(self, operator_name: str, operator_type: str):
        super().__init__(
            f"Operator '{operator_name}' of type '{operator_type}' already exists",
            "ERR.OPERATORS_LIST.CREATE.DUPLICATE"
        )


class OperatorNotFoundError(OperatorsListError):
    """Raised when operator record is not found."""
    def __init__(self, operator_id: str):
        super().__init__(
            f"Operator with ID '{operator_id}' not found or has been deleted",
            "ERR.OPERATORS_LIST.NOT_FOUND"
        )


class InvalidOperatorTypeError(OperatorsListError):
    """Raised when operator type validation fails."""
    def __init__(self, operator_type: str):
        super().__init__(
            f"Invalid operator type '{operator_type}'. Must be Telecom, Bank, or ISP",
            "ERR.OPERATORS_LIST.INVALID_OPERATOR_TYPE"
        )


class DatabaseOperationError(OperatorsListError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.OPERATORS_LIST.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class OperatorsListService:
    """
    Service class for Operators List operations.
    Implements TFS functions: CREATE, READ, UPDATE, DELETE
    """
    
    def __init__(self):
        """Initialize service with database collection."""
        try:
            self.collection: Collection = get_collection("operators_list")
        except Exception as e:
            # ERROR: Database collection initialization failed
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== CREATE Operation (TFS: OperatorsList.CREATE) ==========
    def create_operator(
        self,
        data: OperatorsListCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new operator record.
        
        TFS Reference: OperatorsList.CREATE
        Error Codes:
            - ERR.OPERATORS_LIST.CREATE.DUPLICATE
            - ERR.OPERATORS_LIST.INVALID_OPERATOR_TYPE
            - ERR.OPERATORS_LIST.CREATE.DB_ERROR
        
        Preconditions:
            - operator_type must exist in 91CrPCOperatorType (validated by Pydantic enum)
            - operator_name must be unique within its type
        
        Args:
            data: Operator creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created operator document
            
        Raises:
            DuplicateOperatorError: If operator name/type combination exists
            InvalidOperatorTypeError: If operator type is invalid
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check for duplicate operatorName + operatorType ==========
            # TFS Precondition: operator_name must be unique within its type
            existing = self.collection.find_one({
                "operatorName": data.operatorName,
                "operatorType": data.operatorType.value,
                "isDeleted": False
            })
            
            if existing:
                # ERROR: Duplicate operator name/type combination detected
                # Log: LOG.OPERATORS_LIST.CREATE.END.ERROR.DUPLICATE
                raise DuplicateOperatorError(data.operatorName, data.operatorType.value)
            
            # ========== VALIDATION: Operator type validation ==========
            # Already validated by Pydantic enum (OperatorType)
            # This ensures operator_type exists in 91CrPCOperatorType registry
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            
            # Convert Pydantic models to dict
            operator_dict = data.model_dump()
            
            # Convert enum to string value
            operator_dict["operatorType"] = data.operatorType.value
            
            # Convert contact list of Pydantic models to list of dicts
            operator_dict["contact"] = [contact.model_dump() for contact in data.contact]
            
            document = {
                **operator_dict,
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
                # ERROR: Unique index violation (operatorType + operatorName)
                raise DuplicateOperatorError(data.operatorName, data.operatorType.value)
            except PyMongoError as e:
                # ERROR: Database insert operation failed
                # Log: LOG.OPERATORS_LIST.CREATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("CREATE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATORS_LIST.CREATE.END.SUCCESS (INFO)
            # TODO: Implement logging
            # self._log_event("CREATE", "SUCCESS", document["_id"], created_by)
            
            # NOTIFICATION: In-App notification required
            # Channel: In-App
            # Trigger: record created
            # TODO: Implement notification service
            # self._notify_operator_created(document, created_by)
            
            return document
            
        except OperatorsListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during create operation
            # Log: LOG.OPERATORS_LIST.CREATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation (TFS: OperatorsList.READ) ==========
    def get_operator_by_id(self, operator_id: PyObjectId) -> Optional[dict]:
        """
        Get operator by ID.
        
        TFS Reference: OperatorsList.READ
        Error Codes: ERR.OPERATORS_LIST.READ.NOT_FOUND
        
        Args:
            operator_id: Operator ID
            
        Returns:
            dict: Operator document or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE QUERY ==========
            result = self.collection.find_one({
                "_id": operator_id,
                "isDeleted": False
            })
            
            if result:
                # Log: LOG.OPERATORS_LIST.READ.END.SUCCESS
                pass  # TODO: Implement logging
            
            return result
            
        except PyMongoError as e:
            # ERROR: Database query failed
            # Log: LOG.OPERATORS_LIST.READ.END.ERROR.DB_FAILED
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            # ERROR: Unexpected error during read operation
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation (TFS: OperatorsList.UPDATE) ==========
    def update_operator(
        self,
        operator_id: PyObjectId,
        data: OperatorsListUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """
        Update operator record.
        
        TFS Reference: OperatorsList.UPDATE
        Error Codes:
            - ERR.OPERATORS_LIST.NOT_FOUND
            - ERR.OPERATORS_LIST.UPDATE.DUPLICATE
            - ERR.OPERATORS_LIST.INVALID_OPERATOR_TYPE
            - ERR.OPERATORS_LIST.UPDATE.DB_ERROR
        
        Preconditions:
            - _id exists and not deleted
            - operator_type valid (if provided)
        
        Args:
            operator_id: Operator ID to update
            data: Update data (partial)
            updated_by: User ID performing the update
            updated_ip: IP address of the updater
            
        Returns:
            dict: Updated operator document or None if not found
            
        Raises:
            OperatorNotFoundError: If operator not found or deleted
            DuplicateOperatorError: If operator name/type conflict
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if record exists ==========
            existing = self.collection.find_one({
                "_id": operator_id,
                "isDeleted": False
            })
            
            if not existing:
                # ERROR: Operator not found
                # Log: LOG.OPERATORS_LIST.UPDATE.END.ERROR.NOT_FOUND
                raise OperatorNotFoundError(str(operator_id))
            
            # ========== PREPARE UPDATE DATA ==========
            update_dict = data.model_dump(exclude_unset=True)
            
            # Convert enum to string if operatorType is being updated
            if "operatorType" in update_dict and update_dict["operatorType"] is not None:
                update_dict["operatorType"] = update_dict["operatorType"].value
            
            # Convert contact Pydantic models to dicts if being updated
            if "contact" in update_dict and update_dict["contact"] is not None:
                update_dict["contact"] = [contact.model_dump() for contact in data.contact]
            
            # ========== VALIDATION: Check uniqueness if name or type is being updated ==========
            # TFS Precondition: operator_name must be unique within its type
            if "operatorName" in update_dict or "operatorType" in update_dict:
                check_name = update_dict.get("operatorName", existing["operatorName"])
                check_type = update_dict.get("operatorType", existing["operatorType"])
                
                if check_name != existing["operatorName"] or check_type != existing["operatorType"]:
                    conflict = self.collection.find_one({
                        "operatorName": check_name,
                        "operatorType": check_type,
                        "isDeleted": False,
                        "_id": {"$ne": operator_id}
                    })
                    
                    if conflict:
                        # ERROR: Duplicate operator name/type
                        # Log: LOG.OPERATORS_LIST.UPDATE.END.ERROR.DUPLICATE
                        raise DuplicateOperatorError(check_name, check_type)
            
            # ========== ADD AUDIT FIELDS ==========
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            # ========== DATABASE UPDATE ==========
            try:
                result = self.collection.update_one(
                    {"_id": operator_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    # WARNING: No changes made (data same as existing)
                    pass  # Not an error, just informational
                
            except PyMongoError as e:
                # ERROR: Database update operation failed
                # Log: LOG.OPERATORS_LIST.UPDATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("UPDATE", str(e))
            
            # ========== FETCH UPDATED DOCUMENT ==========
            updated_document = self.collection.find_one({"_id": operator_id})
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATORS_LIST.UPDATE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("UPDATE", "SUCCESS", operator_id, updated_by)
            
            # NOTIFICATION: In-App notification required
            # Channel: NOTIF.OPERATORS_LIST.UPDATED.INAPP
            # TODO: Implement notification service
            # self._notify_operator_updated(updated_document, updated_by)
            
            return updated_document
            
        except OperatorsListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during update operation
            # Log: LOG.OPERATORS_LIST.UPDATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== DELETE Operation (TFS: OperatorsList.DELETE) ==========
    def delete_operator(
        self,
        operator_id: PyObjectId,
        deleted_by: PyObjectId,
        deleted_ip: str
    ) -> bool:
        """
        Soft delete operator record.
        
        TFS Reference: OperatorsList.DELETE
        Error Codes:
            - ERR.OPERATORS_LIST.NOT_FOUND
            - ERR.OPERATORS_LIST.DELETE.DB_ERROR
        
        Preconditions:
            - _id exists and not already deleted
        
        Postconditions:
            - Record soft-deleted (is_deleted=true)
            - Audit fields updated
        
        Args:
            operator_id: Operator ID to delete
            deleted_by: User ID performing the deletion
            deleted_ip: IP address of the deleter
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            OperatorNotFoundError: If operator not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE SOFT DELETE ==========
            # TFS: Set is_deleted = True, update audit fields
            try:
                result = self.collection.update_one(
                    {"_id": operator_id, "isDeleted": False},
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
                    # ERROR: Operator not found or already deleted
                    # Log: LOG.OPERATORS_LIST.DELETE.END.ERROR.NOT_FOUND
                    # TFS: Already deleted → idempotent skip (treat as success)
                    raise OperatorNotFoundError(str(operator_id))
                
            except PyMongoError as e:
                # ERROR: Database delete operation failed
                # Log: LOG.OPERATORS_LIST.DELETE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("DELETE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.OPERATORS_LIST.DELETE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("DELETE", "SUCCESS", operator_id, deleted_by)
            
            # NOTIFICATION: In-App notification required
            # Channel: NOTIF.OPERATORS_LIST.DELETED.INAPP
            # TODO: Implement notification service
            # self._notify_operator_deleted(operator_id, deleted_by)
            
            return result.modified_count > 0
            
        except OperatorsListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during delete operation
            # Log: LOG.OPERATORS_LIST.DELETE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("DELETE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation (Extended TFS: OperatorsList.READ) ==========
    def search_operators(
        self,
        search_params: OperatorsListSearchSchema
    ) -> Tuple[List[dict], int]:
        """
        Search and filter operators with pagination.
        
        TFS Reference: OperatorsList.READ (extended)
        Supports: filtering, sorting, pagination
        
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
            
            # Operator name search (case-insensitive partial match)
            if search_params.operatorName:
                query["operatorName"] = {
                    "$regex": search_params.operatorName,
                    "$options": "i"  # Case-insensitive
                }
            
            # Operator type filter (exact match)
            if search_params.operatorType:
                query["operatorType"] = search_params.operatorType.value
            
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
            
            # Log: LOG.OPERATORS_LIST.READ.END.SUCCESS
            # TODO: Implement logging
            
            return results, total
            
        except OperatorsListError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during search operation
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== UTILITY: Get all operators (for dropdowns) ==========
    def get_all_operators(self, include_deleted: bool = False) -> List[dict]:
        """
        Get all operators (for dropdowns, etc.).
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List[dict]: List of all operator documents
            
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
    
    # ========== UTILITY: Get operators by type ==========
    def get_operators_by_type(self, operator_type: OperatorType, include_deleted: bool = False) -> List[dict]:
        """
        Get all operators of a specific type.
        
        Args:
            operator_type: Type of operator to filter by
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List[dict]: List of operator documents
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            query = {
                "operatorType": operator_type.value
            }
            if not include_deleted:
                query["isDeleted"] = False
            
            return list(self.collection.find(query).sort("operatorName", ASCENDING))
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_TYPE", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_TYPE", f"Unexpected error: {str(e)}")
    
    # ========== PLACEHOLDER: Logging Methods ==========
    # TODO: Implement actual logging service integration
    
    def _log_event(self, operation: str, status: str, record_id: PyObjectId, user_id: PyObjectId):
        """
        Log operator operation event.
        
        Logs:
            - LOG.OPERATORS_LIST.{operation}.END.{status}
        
        TODO: Implement actual logging to database or external service
        """
        pass
    
    # ========== PLACEHOLDER: Notification Methods ==========
    # TODO: Implement actual notification service integration
    
    def _notify_operator_created(self, document: dict, user_id: PyObjectId):
        """
        Send notification when operator is created.
        
        Notification Type: In-App
        Channel: In-App
        TODO: Implement notification service
        """
        pass
    
    def _notify_operator_updated(self, document: dict, user_id: PyObjectId):
        """
        Send notification when operator is updated.
        
        Notification Type: In-App
        Channel: NOTIF.OPERATORS_LIST.UPDATED.INAPP
        TODO: Implement notification service
        """
        pass
    
    def _notify_operator_deleted(self, operator_id: PyObjectId, user_id: PyObjectId):
        """
        Send notification when operator is deleted.
        
        Notification Type: In-App
        Channel: NOTIF.OPERATORS_LIST.DELETED.INAPP
        TODO: Implement notification service
        """
        pass

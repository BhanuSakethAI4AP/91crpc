"""
Purpose: Business logic for Approval Flow Master operations.
Handles CRUD operations for approval workflow definitions.

Based on TFS: ApprovalFlowMaster.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.APPROVAL_FLOW.*
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.approval_flow_master_models import (
    ApprovalFlowMasterCreateSchema,
    ApprovalFlowMasterUpdateSchema,
    ApprovalFlowMasterSearchSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class ApprovalFlowMasterError(Exception):
    """Base exception for Approval Flow Master operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ApprovalFlowNotFoundError(ApprovalFlowMasterError):
    """Raised when approval flow record is not found."""
    def __init__(self, flow_id: str):
        super().__init__(
            f"Approval flow with ID '{flow_id}' not found or has been deleted",
            "ERR.APPROVAL_FLOW.NOT_FOUND"
        )


class InvalidStepsError(ApprovalFlowMasterError):
    """Raised when approval steps validation fails."""
    def __init__(self, details: str):
        super().__init__(
            f"Invalid approval steps: {details}",
            "ERR.APPROVAL_FLOW.INVALID_STEPS"
        )


class DatabaseOperationError(ApprovalFlowMasterError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.APPROVAL_FLOW.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class ApprovalFlowMasterService:
    """
    Service class for Approval Flow Master operations.
    Implements TFS functions: CREATE, READ, UPDATE, DELETE
    """
    
    def __init__(self):
        """Initialize service with database collection."""
        try:
            self.collection: Collection = get_collection("approval_flow_master")
        except Exception as e:
            # ERROR: Database collection initialization failed
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== CREATE Operation (TFS: ApprovalFlowMaster.CREATE) ==========
    def create_approval_flow(
        self,
        data: ApprovalFlowMasterCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new approval flow master record.
        
        TFS Reference: ApprovalFlowMaster.CREATE
        Error Codes:
            - ERR.APPROVAL_FLOW.EMPTY_STEPS
            - ERR.APPROVAL_FLOW.INVALID_ROLE
            - ERR.APPROVAL_FLOW.INVALID_ORDER
            - ERR.APPROVAL_FLOW.CREATE.DB_ERROR
        
        Preconditions:
            - Steps array must not be empty (validated by Pydantic)
            - Each role must exist in Enum(ApprovalRoles) (validated by Pydantic)
            - Orders must be unique and sequential (validated by Pydantic)
        
        Args:
            data: Approval flow creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created approval flow document
            
        Raises:
            InvalidStepsError: If steps validation fails
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Steps validated by Pydantic ==========
            # Pydantic validator ensures:
            # - Steps array not empty
            # - Roles exist in ApprovalRoles enum
            # - Orders are unique and sequential
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            
            # Convert Pydantic models to dict
            flow_dict = data.model_dump()
            
            # Convert nested Pydantic models and enums to dicts/values
            flow_dict["steps"] = [
                {
                    "role": step.role.value,
                    "order": step.order
                }
                for step in data.steps
            ]
            
            document = {
                **flow_dict,
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
                # Log: LOG.APPROVAL_FLOW.CREATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("CREATE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.APPROVAL_FLOW.CREATE.END.SUCCESS (INFO)
            # TODO: Implement logging
            # self._log_event("CREATE", "SUCCESS", document["_id"], created_by)
            
            # NOTIFICATION: In-App notification required
            # Code: NOTIF.APPROVAL_FLOW.CREATED.INAPP
            # Channel: In-App
            # TODO: Implement notification service
            # self._notify_approval_flow_created(document, created_by)
            
            return document
            
        except ApprovalFlowMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during create operation
            # Log: LOG.APPROVAL_FLOW.CREATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation (TFS: ApprovalFlowMaster.READ) ==========
    def get_approval_flow_by_id(self, flow_id: PyObjectId) -> Optional[dict]:
        """
        Get approval flow by ID.
        
        TFS Reference: ApprovalFlowMaster.READ
        Error Codes: ERR.APPROVAL_FLOW.READ.NOT_FOUND
        
        Args:
            flow_id: Approval flow ID
            
        Returns:
            dict: Approval flow document or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE QUERY ==========
            result = self.collection.find_one({
                "_id": flow_id,
                "isDeleted": False
            })
            
            if result:
                # Log: LOG.APPROVAL_FLOW.READ.END.SUCCESS
                pass  # TODO: Implement logging
            
            return result
            
        except PyMongoError as e:
            # ERROR: Database query failed
            # Log: LOG.APPROVAL_FLOW.READ.END.ERROR.DB_FAILED
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            # ERROR: Unexpected error during read operation
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation (TFS: ApprovalFlowMaster.UPDATE) ==========
    def update_approval_flow(
        self,
        flow_id: PyObjectId,
        data: ApprovalFlowMasterUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """
        Update approval flow record.
        
        TFS Reference: ApprovalFlowMaster.UPDATE
        Error Codes:
            - ERR.APPROVAL_FLOW.NOT_FOUND
            - ERR.APPROVAL_FLOW.INVALID_STEPS
            - ERR.APPROVAL_FLOW.UPDATE.DB_ERROR
        
        Preconditions:
            - _id must exist and not be deleted
            - Steps must be valid (roles exist, orders unique/sequential)
        
        Args:
            flow_id: Approval flow ID to update
            data: Update data
            updated_by: User ID performing the update
            updated_ip: IP address of the updater
            
        Returns:
            dict: Updated approval flow document or None if not found
            
        Raises:
            ApprovalFlowNotFoundError: If flow not found or deleted
            InvalidStepsError: If steps validation fails
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check if record exists ==========
            existing = self.collection.find_one({
                "_id": flow_id,
                "isDeleted": False
            })
            
            if not existing:
                # ERROR: Approval flow not found
                # Log: LOG.APPROVAL_FLOW.UPDATE.END.ERROR.NOT_FOUND
                raise ApprovalFlowNotFoundError(str(flow_id))
            
            # ========== VALIDATION: Steps validated by Pydantic ==========
            # Pydantic validator ensures steps are valid
            
            # ========== PREPARE UPDATE DATA ==========
            update_dict = {
                "steps": [
                    {
                        "role": step.role.value,
                        "order": step.order
                    }
                    for step in data.steps
                ],
                "updatedAt": datetime.now(timezone.utc),
                "updatedBy": updated_by,
                "updatedIp": updated_ip
            }
            
            # ========== DATABASE UPDATE ==========
            try:
                result = self.collection.update_one(
                    {"_id": flow_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    # WARNING: No changes made (data same as existing)
                    pass  # Not an error, just informational
                
            except PyMongoError as e:
                # ERROR: Database update operation failed
                # Log: LOG.APPROVAL_FLOW.UPDATE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("UPDATE", str(e))
            
            # ========== FETCH UPDATED DOCUMENT ==========
            updated_document = self.collection.find_one({"_id": flow_id})
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.APPROVAL_FLOW.UPDATE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("UPDATE", "SUCCESS", flow_id, updated_by)
            
            # NOTIFICATION: In-App notification required
            # Code: NOTIF.APPROVAL_FLOW.UPDATED.INAPP
            # Channel: In-App
            # TODO: Implement notification service
            # self._notify_approval_flow_updated(updated_document, updated_by)
            
            return updated_document
            
        except ApprovalFlowMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during update operation
            # Log: LOG.APPROVAL_FLOW.UPDATE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== DELETE Operation (TFS: ApprovalFlowMaster.DELETE) ==========
    def delete_approval_flow(
        self,
        flow_id: PyObjectId,
        deleted_by: PyObjectId,
        deleted_ip: str
    ) -> bool:
        """
        Soft delete approval flow record.
        
        TFS Reference: ApprovalFlowMaster.DELETE
        Error Codes:
            - ERR.APPROVAL_FLOW.NOT_FOUND
            - ERR.APPROVAL_FLOW.DELETE.DB_ERROR
        
        Preconditions:
            - _id must exist and not already be deleted
        
        Postconditions:
            - is_deleted=true
            - audit fields updated
        
        Args:
            flow_id: Approval flow ID to delete
            deleted_by: User ID performing the deletion
            deleted_ip: IP address of the deleter
            
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            ApprovalFlowNotFoundError: If flow not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE SOFT DELETE ==========
            # TFS: Set is_deleted = True, update audit fields
            try:
                result = self.collection.update_one(
                    {"_id": flow_id, "isDeleted": False},
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
                    # ERROR: Approval flow not found or already deleted
                    # Log: LOG.APPROVAL_FLOW.DELETE.END.ERROR.NOT_FOUND
                    # TFS: Already deleted → idempotent skip
                    raise ApprovalFlowNotFoundError(str(flow_id))
                
            except PyMongoError as e:
                # ERROR: Database delete operation failed
                # Log: LOG.APPROVAL_FLOW.DELETE.END.ERROR.DB_FAILED
                raise DatabaseOperationError("DELETE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.APPROVAL_FLOW.DELETE.END.SUCCESS
            # TODO: Implement logging
            # self._log_event("DELETE", "SUCCESS", flow_id, deleted_by)
            
            # NOTIFICATION: In-App notification required
            # Code: NOTIF.APPROVAL_FLOW.DELETED.INAPP
            # Channel: In-App
            # TODO: Implement notification service
            # self._notify_approval_flow_deleted(flow_id, deleted_by)
            
            return result.modified_count > 0
            
        except ApprovalFlowMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during delete operation
            # Log: LOG.APPROVAL_FLOW.DELETE.END.ERROR.UNEXPECTED
            raise DatabaseOperationError("DELETE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation (Extended TFS: ApprovalFlowMaster.READ) ==========
    def search_approval_flows(
        self,
        search_params: ApprovalFlowMasterSearchSchema
    ) -> Tuple[List[dict], int]:
        """
        Search and filter approval flows with pagination.
        
        TFS Reference: ApprovalFlowMaster.READ (extended)
        Supports: filtering by role, sorting, pagination
        
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
            
            # Role filter (check if role exists in steps array)
            if search_params.role:
                query["steps.role"] = search_params.role.value
            
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
            
            # Log: LOG.APPROVAL_FLOW.READ.END.SUCCESS
            # TODO: Implement logging
            
            return results, total
            
        except ApprovalFlowMasterError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # ERROR: Unexpected error during search operation
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== UTILITY: Get all approval flows ==========
    def get_all_approval_flows(self, include_deleted: bool = False) -> List[dict]:
        """
        Get all approval flows (for dropdowns, etc.).
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List[dict]: List of all approval flow documents
            
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
        Log approval flow operation event.
        
        Logs:
            - LOG.APPROVAL_FLOW.{operation}.END.{status}
        
        TODO: Implement actual logging to database or external service
        """
        pass
    
    # ========== PLACEHOLDER: Notification Methods ==========
    # TODO: Implement actual notification service integration
    
    def _notify_approval_flow_created(self, document: dict, user_id: PyObjectId):
        """
        Send notification when approval flow is created.
        
        Notification Code: NOTIF.APPROVAL_FLOW.CREATED.INAPP
        Channel: In-App
        TODO: Implement notification service
        """
        pass
    
    def _notify_approval_flow_updated(self, document: dict, user_id: PyObjectId):
        """
        Send notification when approval flow is updated.
        
        Notification Code: NOTIF.APPROVAL_FLOW.UPDATED.INAPP
        Channel: In-App
        TODO: Implement notification service
        """
        pass
    
    def _notify_approval_flow_deleted(self, flow_id: PyObjectId, user_id: PyObjectId):
        """
        Send notification when approval flow is deleted.
        
        Notification Code: NOTIF.APPROVAL_FLOW.DELETED.INAPP
        Channel: In-App
        TODO: Implement notification service
        """
        pass

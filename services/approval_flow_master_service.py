#path: backend/services/approval_flow_master_service.py
"""
Purpose: Business logic for Approval Flow Master operations.
Handles CRUD operations for approval workflow definitions.

Based on TFS: ApprovalFlowMaster.CREATE, READ, UPDATE, DELETE
Error Codes: ERR.APPROVAL_FLOW.*

Updated to support Universal Workflow with dynamic entry points.
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


class InvalidRoleMappingError(ApprovalFlowMasterError):
    """Raised when role to step mapping validation fails."""
    def __init__(self, details: str):
        super().__init__(
            f"Invalid role to step mapping: {details}",
            "ERR.APPROVAL_FLOW.INVALID_ROLE_MAPPING"
        )


class DuplicateWorkflowError(ApprovalFlowMasterError):
    """Raised when attempting to create duplicate universal workflow."""
    def __init__(self):
        super().__init__(
            "A UNIVERSAL workflow already exists. Only one universal workflow is allowed.",
            "ERR.APPROVAL_FLOW.DUPLICATE_UNIVERSAL"
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
    Supports Universal Workflow with dynamic entry points.
    """
    
    def __init__(self):
        """Initialize service with database collection."""
        try:
            self.collection: Collection = get_collection("approval_flow_master")
        except Exception as e:
            # ERROR: Database collection initialization failed
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== VALIDATION HELPER ==========
    def _validate_role_mapping(self, steps: List[dict], role_mapping: dict) -> None:
        """
        Validate that all roles in roleToStepMapping exist in steps.
        
        Args:
            steps: List of step dictionaries
            role_mapping: Role to step mapping dictionary
            
        Raises:
            InvalidRoleMappingError: If validation fails
        """
        # Extract roles from steps
        step_roles = {step["role"] for step in steps}
        
        # Check if all mapped roles exist in steps
        for role in role_mapping.keys():
            if role not in step_roles:
                raise InvalidRoleMappingError(
                    f"Role '{role}' in roleToStepMapping does not exist in steps"
                )
        
        # Check if all mapped step numbers are valid
        max_step = len(steps)
        for role, step_num in role_mapping.items():
            if step_num < 1 or step_num > max_step:
                raise InvalidRoleMappingError(
                    f"Invalid step number {step_num} for role '{role}'. Must be between 1 and {max_step}"
                )
    
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
            - ERR.APPROVAL_FLOW.INVALID_ROLE_MAPPING
            - ERR.APPROVAL_FLOW.DUPLICATE_UNIVERSAL
            - ERR.APPROVAL_FLOW.CREATE.DB_ERROR
        
        Args:
            data: Approval flow creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created approval flow document
            
        Raises:
            DuplicateWorkflowError: If UNIVERSAL workflow already exists
            InvalidRoleMappingError: If role mapping validation fails
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== VALIDATION: Check for existing UNIVERSAL workflow ==========
            if data.workflowType == "UNIVERSAL":
                existing_universal = self.collection.find_one({
                    "workflowType": "UNIVERSAL",
                    "isDeleted": False
                })
                
                if existing_universal:
                    # ERROR: UNIVERSAL workflow already exists
                    raise DuplicateWorkflowError()
            
            # ========== PREPARE DOCUMENT ==========
            now = datetime.now(timezone.utc)
            
            # Convert Pydantic models to dict
            flow_dict = data.model_dump()
            
            # Convert nested Pydantic models and enums to dicts/values
            flow_dict["steps"] = [
                {
                    "role": step.role.value,
                    "order": step.order,
                    "description": step.description
                }
                for step in data.steps
            ]
            
            # ========== VALIDATION: Validate role mapping ==========
            self._validate_role_mapping(flow_dict["steps"], flow_dict["roleToStepMapping"])
            
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
    
    # ========== GET UNIVERSAL WORKFLOW ==========
    def get_universal_workflow(self) -> Optional[dict]:
        """
        Get the universal approval workflow.
        
        Returns:
            dict: Universal workflow document or None if not found
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            result = self.collection.find_one({
                "workflowType": "UNIVERSAL",
                "isDeleted": False
            })
            
            return result
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_UNIVERSAL", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_UNIVERSAL", f"Unexpected error: {str(e)}")
    
    # ========== GET STARTING STEP FOR ROLE ==========
    def get_starting_step_for_role(self, role: str) -> int:
        """
        Get the starting step number for a given initiator role.
        
        Args:
            role: Initiator role (IO, SHO, CI, DSP, IT Core, Admin ASP)
            
        Returns:
            int: Starting step number
            
        Raises:
            ApprovalFlowNotFoundError: If universal workflow not found
            InvalidRoleMappingError: If role not found in mapping
        """
        workflow = self.get_universal_workflow()
        
        if not workflow:
            raise ApprovalFlowNotFoundError("UNIVERSAL")
        
        role_mapping = workflow.get("roleToStepMapping", {})
        
        if role not in role_mapping:
            raise InvalidRoleMappingError(f"Role '{role}' not found in workflow mapping")
        
        return role_mapping[role]
    
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
            - ERR.APPROVAL_FLOW.INVALID_ROLE_MAPPING
            - ERR.APPROVAL_FLOW.UPDATE.DB_ERROR
        
        Args:
            flow_id: Approval flow ID to update
            data: Update data
            updated_by: User ID performing the update
            updated_ip: IP address of the updater
            
        Returns:
            dict: Updated approval flow document or None if not found
            
        Raises:
            ApprovalFlowNotFoundError: If flow not found or deleted
            InvalidRoleMappingError: If role mapping validation fails
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
            
            # ========== PREPARE UPDATE DATA ==========
            update_dict = data.model_dump(exclude_unset=True)
            
            # Convert steps if provided
            if "steps" in update_dict and update_dict["steps"] is not None:
                update_dict["steps"] = [
                    {
                        "role": step.role.value,
                        "order": step.order,
                        "description": step.description
                    }
                    for step in data.steps
                ]
            
            # ========== VALIDATION: Validate role mapping if updated ==========
            if "roleToStepMapping" in update_dict or "steps" in update_dict:
                # Use updated or existing values
                steps = update_dict.get("steps", existing.get("steps", []))
                role_mapping = update_dict.get("roleToStepMapping", existing.get("roleToStepMapping", {}))
                
                self._validate_role_mapping(steps, role_mapping)
            
            # ========== ADD AUDIT FIELDS ==========
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
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
        
        Args:
            flow_id: Approval flow ID to delete
            deleted_by: User ID performing the deletion
            deleted_ip: IP address of the deleter
            
        Returns:
            bool: True if deleted
            
        Raises:
            ApprovalFlowNotFoundError: If flow not found
            DatabaseOperationError: If database operation fails
        """
        try:
            # ========== DATABASE SOFT DELETE ==========
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
                    raise ApprovalFlowNotFoundError(str(flow_id))
                
            except PyMongoError as e:
                # ERROR: Database delete operation failed
                raise DatabaseOperationError("DELETE", str(e))
            
            # ========== POST-OPERATION TASKS ==========
            # Log: LOG.APPROVAL_FLOW.DELETE.END.SUCCESS
            # TODO: Implement logging
            
            # NOTIFICATION: In-App notification required
            # TODO: Implement notification service
            
            return result.modified_count > 0
            
        except ApprovalFlowMasterError:
            raise
        except Exception as e:
            raise DatabaseOperationError("DELETE", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation ==========
    def search_approval_flows(
        self,
        search_params: ApprovalFlowMasterSearchSchema
    ) -> Tuple[List[dict], int]:
        """
        Search and filter approval flows with pagination.
        
        Args:
            search_params: Search and filter criteria
            
        Returns:
            Tuple[List[dict], int]: (list of documents, total count)
        """
        try:
            # ========== BUILD QUERY FILTER ==========
            query = {}
            
            if not search_params.includeDeleted:
                query["isDeleted"] = False
            
            if search_params.workflowType:
                query["workflowType"] = search_params.workflowType
            
            if search_params.role:
                query["steps.role"] = search_params.role.value
            
            # ========== GET TOTAL COUNT ==========
            total = self.collection.count_documents(query)
            
            # ========== BUILD SORT ==========
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            
            # ========== CALCULATE PAGINATION ==========
            skip = (search_params.page - 1) * search_params.pageSize
            
            # ========== EXECUTE QUERY ==========
            cursor = self.collection.find(query).sort(
                search_params.sortBy, sort_order
            ).skip(skip).limit(search_params.pageSize)
            
            results = list(cursor)
            
            return results, total
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH", str(e))
        except Exception as e:
            raise DatabaseOperationError("SEARCH", f"Unexpected error: {str(e)}")
    
    # ========== UTILITY ==========
    def get_all_approval_flows(self, include_deleted: bool = False) -> List[dict]:
        """Get all approval flows."""
        try:
            query = {} if include_deleted else {"isDeleted": False}
            return list(self.collection.find(query).sort("createdAt", DESCENDING))
        except PyMongoError as e:
            raise DatabaseOperationError("GET_ALL", str(e))

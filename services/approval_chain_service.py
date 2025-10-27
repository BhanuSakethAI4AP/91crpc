"""
Purpose: Business logic for Approval Chain operations.
Handles approval tracking, approval processing, and workflow management.

Manages step-by-step approval progress for CrPC request pipeline items.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.approval_chain_models import (
    ApprovalChainCreateSchema,
    ApprovalChainUpdateSchema,
    ApprovalChainSearchSchema,
    ApprovalActionSchema,
)
from utils.validators import PyObjectId


# ========== Custom Exceptions ==========
class ApprovalChainError(Exception):
    """Base exception for Approval Chain operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ApprovalChainNotFoundError(ApprovalChainError):
    """Raised when approval chain is not found."""
    def __init__(self, chain_id: str):
        super().__init__(
            f"Approval chain with ID '{chain_id}' not found",
            "ERR.APPROVAL_CHAIN.NOT_FOUND"
        )


class InvalidStepError(ApprovalChainError):
    """Raised when step validation fails."""
    def __init__(self, details: str):
        super().__init__(
            f"Invalid step: {details}",
            "ERR.APPROVAL_CHAIN.INVALID_STEP"
        )


class UnauthorizedApprovalError(ApprovalChainError):
    """Raised when user is not authorized for current step."""
    def __init__(self, user_role: str, required_role: str):
        super().__init__(
            f"User role '{user_role}' is not authorized. Required role: '{required_role}'",
            "ERR.APPROVAL_CHAIN.UNAUTHORIZED"
        )


class AlreadyProcessedError(ApprovalChainError):
    """Raised when trying to process already completed approval."""
    def __init__(self):
        super().__init__(
            "This approval chain has already been processed",
            "ERR.APPROVAL_CHAIN.ALREADY_PROCESSED"
        )


class MissingRejectReasonError(ApprovalChainError):
    """Raised when reject reason is not provided for rejection."""
    def __init__(self):
        super().__init__(
            "Reject reason is required when rejecting a request",
            "ERR.APPROVAL_CHAIN.MISSING_REJECT_REASON"
        )


class DatabaseOperationError(ApprovalChainError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.APPROVAL_CHAIN.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class ApprovalChainService:
    """
    Service class for Approval Chain operations.
    Manages approval workflow tracking and processing.
    """
    
    def __init__(self):
        """Initialize service with database collections."""
        try:
            self.collection: Collection = get_collection("approval_chain")
            self.workflow_collection: Collection = get_collection("approval_flow_master")
            self.pipeline_collection: Collection = get_collection("crpc_request_pipelines")
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== HELPER: Get Workflow ==========
    def _get_workflow(self, workflow_id: PyObjectId) -> dict:
        """Get workflow by ID."""
        workflow = self.workflow_collection.find_one({
            "_id": workflow_id,
            "isDeleted": False
        })
        
        if not workflow:
            raise ApprovalChainError(
                f"Workflow '{workflow_id}' not found",
                "ERR.APPROVAL_CHAIN.WORKFLOW_NOT_FOUND"
            )
        
        return workflow
    
    # ========== HELPER: Get Universal Workflow ==========
    def _get_universal_workflow(self) -> dict:
        """Get universal workflow."""
        workflow = self.workflow_collection.find_one({
            "workflowType": "UNIVERSAL",
            "isDeleted": False
        })
        
        if not workflow:
            raise ApprovalChainError(
                "Universal workflow not found",
                "ERR.APPROVAL_CHAIN.UNIVERSAL_WORKFLOW_NOT_FOUND"
            )
        
        return workflow
    
    # ========== HELPER: Get Role for Step ==========
    def _get_role_for_step(self, workflow: dict, step: int) -> str:
        """Get the role responsible for a specific step."""
        for workflow_step in workflow.get("steps", []):
            if workflow_step["order"] == step:
                return workflow_step["role"]
        
        raise InvalidStepError(f"Step {step} not found in workflow")
    
    # ========== HELPER: Get Next Step ==========
    def _get_next_step(self, workflow: dict, current_step: int) -> Optional[int]:
        """Get the next step number, or None if this is the last step."""
        max_step = len(workflow.get("steps", []))
        
        if current_step >= max_step:
            return None  # Last step
        
        return current_step + 1
    
    # ========== CREATE Operation ==========
    def create_approval_chain(
        self,
        data: ApprovalChainCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a new approval chain.
        
        Auto-called when a pipeline is created.
        
        Args:
            data: Approval chain creation data
            created_by: User ID creating the record
            created_ip: IP address of the creator
            
        Returns:
            dict: Created approval chain document
            
        Raises:
            DatabaseOperationError: If database operation fails
        """
        try:
            # Validate workflow exists
            workflow = self._get_workflow(data.approvalFlowId)
            
            # Validate step is within workflow range
            max_step = len(workflow.get("steps", []))
            if data.currentStep < 1 or data.currentStep > max_step:
                raise InvalidStepError(
                    f"Step {data.currentStep} is out of range. Valid: 1-{max_step}"
                )
            
            # Prepare document
            now = datetime.now(timezone.utc)
            chain_dict = data.model_dump()
            chain_dict["approvalChainStatus"] = data.approvalChainStatus.value
            
            document = {
                **chain_dict,
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
            
        except ApprovalChainError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("CREATE", str(e))
        except Exception as e:
            raise DatabaseOperationError("CREATE", f"Unexpected error: {str(e)}")
    
    # ========== READ Operation ==========
    def get_approval_chain_by_id(self, chain_id: PyObjectId) -> Optional[dict]:
        """Get approval chain by ID."""
        try:
            result = self.collection.find_one({
                "_id": chain_id,
                "isActive": True
            })
            
            return result
            
        except PyMongoError as e:
            raise DatabaseOperationError("READ", str(e))
        except Exception as e:
            raise DatabaseOperationError("READ", f"Unexpected error: {str(e)}")
    
    # ========== GET BY PIPELINE ID ==========
    def get_by_pipeline_id(self, pipeline_id: PyObjectId) -> Optional[dict]:
        """Get approval chain for a pipeline."""
        try:
            result = self.collection.find_one({
                "crpcRequestPipelineId": pipeline_id,
                "isActive": True
            })
            
            return result
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_PIPELINE", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_BY_PIPELINE", f"Unexpected error: {str(e)}")
    
    # ========== UPDATE Operation ==========
    def update_approval_chain(
        self,
        chain_id: PyObjectId,
        data: ApprovalChainUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """Update approval chain."""
        try:
            # Check if exists
            existing = self.collection.find_one({
                "_id": chain_id,
                "isActive": True
            })
            
            if not existing:
                raise ApprovalChainNotFoundError(str(chain_id))
            
            # Prepare update
            update_dict = data.model_dump(exclude_unset=True)
            
            if "approvalChainStatus" in update_dict:
                update_dict["approvalChainStatus"] = update_dict["approvalChainStatus"].value
            
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            # Update
            self.collection.update_one(
                {"_id": chain_id},
                {"$set": update_dict}
            )
            
            # Return updated document
            return self.collection.find_one({"_id": chain_id})
            
        except ApprovalChainError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("UPDATE", str(e))
        except Exception as e:
            raise DatabaseOperationError("UPDATE", f"Unexpected error: {str(e)}")
    
    # ========== PROCESS APPROVAL ==========
    def process_approval(
        self,
        chain_id: PyObjectId,
        action_data: ApprovalActionSchema,
        user_role: str,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> dict:
        """
        Process an approval or rejection action.
        
        Args:
            chain_id: Approval chain ID
            action_data: Approval action (APPROVE or REJECT)
            user_role: Current user's role
            updated_by: User ID performing the action
            updated_ip: IP address
            
        Returns:
            dict: Updated approval chain
            
        Raises:
            UnauthorizedApprovalError: If user not authorized
            AlreadyProcessedError: If already processed
            MissingRejectReasonError: If rejecting without reason
        """
        try:
            # Get approval chain
            chain = self.collection.find_one({
                "_id": chain_id,
                "isActive": True
            })
            
            if not chain:
                raise ApprovalChainNotFoundError(str(chain_id))
            
            # Check if already processed
            if chain["approvalChainStatus"] in ["AckByITCore", "Reject", "Approved"]:
                raise AlreadyProcessedError()
            
            # Get workflow
            workflow = self._get_workflow(chain["approvalFlowId"])
            
            # Get required role for current step
            required_role = self._get_role_for_step(workflow, chain["currentStep"])
            
            # Validate user authorization
            if user_role != required_role:
                raise UnauthorizedApprovalError(user_role, required_role)
            
            # Process action
            if action_data.action == "APPROVE":
                # Move to next step
                next_step = self._get_next_step(workflow, chain["currentStep"])
                
                if next_step is None:
                    # Last step - mark as complete
                    new_status = "AckByITCore"  # Final acknowledgment
                    new_step = chain["currentStep"]
                else:
                    # Move to next step
                    new_status = f"Approvedby{required_role.replace(' ', '')}"
                    new_step = next_step
                
                update_dict = {
                    "currentStep": new_step,
                    "approvalChainStatus": new_status,
                    "updatedAt": datetime.now(timezone.utc),
                    "updatedBy": updated_by,
                    "updatedIp": updated_ip
                }
                
            elif action_data.action == "REJECT":
                # Validate reject reason provided
                if not action_data.rejectReason:
                    raise MissingRejectReasonError()
                
                update_dict = {
                    "approvalChainStatus": "Reject",
                    "rejectReason": action_data.rejectReason,
                    "updatedAt": datetime.now(timezone.utc),
                    "updatedBy": updated_by,
                    "updatedIp": updated_ip
                }
            
            # Update chain
            self.collection.update_one(
                {"_id": chain_id},
                {"$set": update_dict}
            )
            
            # Return updated chain
            updated_chain = self.collection.find_one({"_id": chain_id})
            
            # TODO: Notify next approver or requester
            # self._send_notification(updated_chain, action_data.action)
            
            return updated_chain
            
        except ApprovalChainError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("PROCESS_APPROVAL", str(e))
        except Exception as e:
            raise DatabaseOperationError("PROCESS_APPROVAL", f"Unexpected error: {str(e)}")
    
    # ========== BULK APPROVE ==========
    def bulk_approve(
        self,
        chain_ids: List[PyObjectId],
        user_role: str,
        updated_by: PyObjectId,
        updated_ip: str,
        comments: Optional[str] = None
    ) -> dict:
        """
        Approve multiple approval chains at once.
        
        Args:
            chain_ids: List of approval chain IDs
            user_role: Current user's role
            updated_by: User ID
            updated_ip: IP address
            comments: Optional comments
            
        Returns:
            dict: Summary of results
        """
        try:
            results = {
                "success": [],
                "failed": []
            }
            
            for chain_id in chain_ids:
                try:
                    action_data = ApprovalActionSchema(
                        action="APPROVE",
                        comments=comments
                    )
                    
                    updated_chain = self.process_approval(
                        chain_id,
                        action_data,
                        user_role,
                        updated_by,
                        updated_ip
                    )
                    
                    results["success"].append({
                        "chainId": str(chain_id),
                        "status": updated_chain["approvalChainStatus"]
                    })
                    
                except ApprovalChainError as e:
                    results["failed"].append({
                        "chainId": str(chain_id),
                        "error": e.error_code,
                        "message": e.message
                    })
            
            return results
            
        except Exception as e:
            raise DatabaseOperationError("BULK_APPROVE", f"Unexpected error: {str(e)}")
    
    # ========== GET PENDING FOR USER ==========
    def get_pending_for_user(self, user_role: str) -> List[dict]:
        """
        Get all approval chains pending for a specific user role.
        
        Args:
            user_role: User's role
            
        Returns:
            List[dict]: List of pending approval chains
        """
        try:
            # Get universal workflow
            workflow = self._get_universal_workflow()
            
            # Find which step number corresponds to this role
            role_step = None
            for step in workflow.get("steps", []):
                if step["role"] == user_role:
                    role_step = step["order"]
                    break
            
            if role_step is None:
                return []  # Role not in workflow
            
            # Find all chains at this step with Pending status
            chains = list(self.collection.find({
                "currentStep": role_step,
                "approvalChainStatus": "Pending",
                "isActive": True
            }))
            
            return chains
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_PENDING", str(e))
        except Exception as e:
            raise DatabaseOperationError("GET_PENDING", f"Unexpected error: {str(e)}")
    
    # ========== SEARCH Operation ==========
    def search_approval_chains(
        self,
        search_params: ApprovalChainSearchSchema
    ) -> Tuple[List[dict], int]:
        """Search and filter approval chains with pagination."""
        try:
            # Build query
            query = {}
            
            if not search_params.includeInactive:
                query["isActive"] = True
            
            if search_params.crpcRequestPipelineId:
                query["crpcRequestPipelineId"] = search_params.crpcRequestPipelineId
            
            if search_params.approvalFlowId:
                query["approvalFlowId"] = search_params.approvalFlowId
            
            if search_params.currentStep:
                query["currentStep"] = search_params.currentStep
            
            if search_params.approvalChainStatus:
                query["approvalChainStatus"] = search_params.approvalChainStatus.value
            
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
    
    # ========== PLACEHOLDER: Notification ==========
    def _send_notification(self, chain: dict, action: str):
        """
        Send notification after approval/rejection.
        
        TODO: Implement notification service
        """
        pass

"""
Purpose: Business logic for CrPC Requests operations.
Handles CRUD operations with automatic pipeline and approval chain generation.

Most complex service - orchestrates multiple collections.
"""

from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Optional, Tuple, List, Dict, Any
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import get_collection
from models.crpc_requests_models import (
    CrpcRequestCreateSchema,
    CrpcRequestUpdateSchema,
    CrpcRequestSearchSchema,
    CloseRequestSchema,
)
from models.crpc_request_pipelines_models import CrpcRequestPipelineCreateSchema
from models.approval_chain_models import ApprovalChainCreateSchema
from services.crpc_request_pipelines_service import CrpcRequestPipelineService
from services.approval_chain_service import ApprovalChainService
from services.approval_flow_master_service import ApprovalFlowMasterService
from utils.validators import PyObjectId
from constants.value_sets import CrpcRequestStatus, LineItemRequestStatus


# ========== Custom Exceptions ==========
class CrpcRequestError(Exception):
    """Base exception for CrPC Request operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class RequestNotFoundError(CrpcRequestError):
    """Raised when request is not found."""
    def __init__(self, request_id: str):
        super().__init__(
            f"CrPC Request with ID '{request_id}' not found",
            "ERR.CRPC_REQUEST.NOT_FOUND"
        )


class PipelineGenerationError(CrpcRequestError):
    """Raised when pipeline generation fails."""
    def __init__(self, details: str):
        super().__init__(
            f"Failed to generate pipelines: {details}",
            "ERR.CRPC_REQUEST.PIPELINE_GENERATION_FAILED"
        )


class InvalidServiceListError(CrpcRequestError):
    """Raised when service list is invalid."""
    def __init__(self, details: str):
        super().__init__(
            f"Invalid service list: {details}",
            "ERR.CRPC_REQUEST.INVALID_SERVICE_LIST"
        )


class UnauthorizedClosureError(CrpcRequestError):
    """Raised when non-SHO tries to close request."""
    def __init__(self):
        super().__init__(
            "Only SHO can close requests",
            "ERR.CRPC_REQUEST.UNAUTHORIZED_CLOSURE"
        )


class DatabaseOperationError(CrpcRequestError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.CRPC_REQUEST.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class CrpcRequestService:
    """
    Service class for CrPC Request operations.
    Orchestrates request creation with pipelines and approval chains.
    """
    
    def __init__(self):
        """Initialize service with database collections and sub-services."""
        try:
            self.collection: Collection = get_collection("crpc_requests")
            self.service_collection: Collection = get_collection("service_master")
            
            # Initialize sub-services
            self.pipeline_service = CrpcRequestPipelineService()
            self.approval_chain_service = ApprovalChainService()
            self.workflow_service = ApprovalFlowMasterService()
            
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== VALIDATION: Check Services Exist ==========
    def _validate_service_list(self, service_list: List[dict]) -> None:
        """
        Validate that all services in serviceList exist and are active.
        
        Args:
            service_list: List of service items
            
        Raises:
            InvalidServiceListError: If any service is invalid
        """
        for item in service_list:
            service_id = item.get("serviceId")
            
            # Check if service exists
            service = self.service_collection.find_one({
                "_id": service_id,
                "isDeleted": False
            })
            
            if not service:
                raise InvalidServiceListError(
                    f"Service with ID '{service_id}' not found or is deleted (Line {item.get('lineNo')})"
                )
            
            print(f"✓ Service validated: {service.get('serviceName')} for line {item.get('lineNo')}")
    
    # ========== HELPER: Calculate Request Status ==========
    def _calculate_request_status(self, pipelines: List[dict]) -> CrpcRequestStatus:
        """
        Calculate overall request status based on pipeline statuses.
        
        Logic:
        - Any pipeline "Reject" → Request "Reject"
        - All pipelines "AckByITCore" → Request "sent"
        - All pipelines "Approved" → Request "Approved"
        - Mix/Pending → Request "OnApprovalQueue"
        """
        if not pipelines:
            return CrpcRequestStatus.ON_APPROVAL_QUEUE
        
        statuses = [p.get("lineItemRequestStatus") for p in pipelines]
        
        # Rule 1: Any rejection = Request rejected
        if "Reject" in statuses:
            return CrpcRequestStatus.REJECT
        
        # Rule 2: All acknowledged = Request sent
        if all(s == "AckByITCore" for s in statuses):
            return CrpcRequestStatus.SENT
        
        # Rule 3: All approved (but not yet acknowledged) = Request approved
        if all(s == "Approved" for s in statuses):
            return CrpcRequestStatus.APPROVED
        
        # Rule 4: Default = On approval queue
        return CrpcRequestStatus.ON_APPROVAL_QUEUE
    
    # ========== HELPER: Sync Request Status ==========
    def _sync_request_status(
        self, 
        request_id: PyObjectId,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> CrpcRequestStatus:
        """Synchronize request status based on current pipeline statuses."""
        try:
            pipelines = self.pipeline_service.get_by_request_id(request_id)
            new_status = self._calculate_request_status(pipelines)
            
            self.collection.update_one(
                {"_id": request_id},
                {
                    "$set": {
                        "CrPCRequestStatus": new_status.value,
                        "updatedAt": datetime.now(timezone.utc),
                        "updatedBy": updated_by,
                        "updatedIp": updated_ip
                    }
                }
            )
            
            return new_status
            
        except Exception as e:
            print(f"Warning: Failed to sync request status: {str(e)}")
            return CrpcRequestStatus.ON_APPROVAL_QUEUE
    
    # ========== HELPER: Get User Role ==========
    def _get_user_role(self, user_id: PyObjectId) -> str:
        """
        Get user's role from core service.
        TODO: Implement actual user service integration
        """
        return "SHO"  # Dummy for now
    
    # ========== HELPER: Generate Pipelines ==========
    def _generate_pipelines_and_chains(
        self,
        request_id: PyObjectId,
        service_list: List[dict],
        initiator_role: str,
        created_by: PyObjectId,
        created_ip: str
    ) -> List[PyObjectId]:
        """Generate pipelines and approval chains for each service."""
        try:
            created_pipeline_ids = []
            
            # Get universal workflow
            workflow = self.workflow_service.get_universal_workflow()
            if not workflow:
                raise PipelineGenerationError("Universal workflow not found")
            
            # Get starting step for this role
            starting_step = workflow["roleToStepMapping"].get(initiator_role, 1)
            
            # Process each service item
            for service_item in service_list:
                try:
                    # Step 1: Detect operator
                    operator_id = self.pipeline_service.detect_operator_for_service(
                        service_item["serviceId"],
                        service_item["keyFieldValue"]
                    )
                    
                    # Step 2: Create pipeline
                    pipeline_data = CrpcRequestPipelineCreateSchema(
                        crpcRequestId=request_id,
                        lineItem=service_item["lineNo"],
                        operatorId=operator_id,
                        serviceId=service_item["serviceId"],
                        keyFieldValue=service_item["keyFieldValue"],
                        requiredData=service_item["requiredData"],
                        lineItemRequestStatus=LineItemRequestStatus.ON_APPROVAL_QUEUE
                    )
                    
                    pipeline = self.pipeline_service.create_pipeline(
                        pipeline_data,
                        created_by,
                        created_ip
                    )
                    
                    created_pipeline_ids.append(pipeline["_id"])
                    print(f"✓ Pipeline created for line {service_item['lineNo']}")
                    
                    # Step 3: Create approval chain
                    chain_data = ApprovalChainCreateSchema(
                        crpcRequestPipelineId=pipeline["_id"],
                        approvalFlowId=workflow["_id"],
                        currentStep=starting_step,
                        approvalChainStatus="Pending"
                    )
                    
                    self.approval_chain_service.create_approval_chain(
                        chain_data,
                        created_by,
                        created_ip
                    )
                    print(f"✓ Approval chain created for line {service_item['lineNo']}")
                    
                except Exception as e:
                    print(f"✗ Failed for line {service_item['lineNo']}: {str(e)}")
                    raise PipelineGenerationError(
                        f"Failed for line {service_item['lineNo']}: {str(e)}"
                    )
            
            if not created_pipeline_ids:
                raise PipelineGenerationError("No pipelines were created")
            
            return created_pipeline_ids
            
        except PipelineGenerationError:
            raise
        except Exception as e:
            raise PipelineGenerationError(f"Unexpected error: {str(e)}")
    
    # ========== CREATE Operation ==========
    def create_request(
        self,
        data: CrpcRequestCreateSchema,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """Create a new CrPC request with automatic pipeline generation."""
        try:
            print(f"\n{'='*60}")
            print(f"📝 Creating CrPC Request")
            print(f"{'='*60}")
            
            # Step 1: Validate services
            print("\n🔍 Step 1: Validating services...")
            request_dict = data.model_dump()
            self._validate_service_list(request_dict["serviceList"])
            print("✓ All services validated")
            
            # Get initiator role
            initiator_role = self._get_user_role(created_by)
            print(f"✓ Initiator role: {initiator_role}")
            
            # Step 2: Create main request
            print("\n📄 Step 2: Creating main request...")
            now = datetime.now(timezone.utc)
            
            request_dict["fir"] = [fir.model_dump() for fir in data.fir]
            request_dict["serviceList"] = [item.model_dump() for item in data.serviceList]
            request_dict["attachmentsNeededForRequest"] = [
                att.model_dump() for att in data.attachmentsNeededForRequest
            ]
            
            # ========== FIX: Convert date to datetime for MongoDB ==========
            if isinstance(request_dict.get("requestDate"), date) and not isinstance(request_dict.get("requestDate"), datetime):
                request_dict["requestDate"] = datetime.combine(
                    request_dict["requestDate"], 
                    datetime.min.time()
                ).replace(tzinfo=timezone.utc)
                print(f"✓ Converted requestDate to datetime: {request_dict['requestDate']}")
            
            document = {
                **request_dict,
                "approvedBy": None,
                "CrPCRequestStatus": CrpcRequestStatus.ON_APPROVAL_QUEUE.value,
                "isActive": True,
                "createdAt": now,
                "createdBy": created_by,
                "createdIp": created_ip,
                "updatedAt": now,
                "updatedBy": created_by,
                "updatedIp": created_ip,
            }
            
            try:
                result = self.collection.insert_one(document)
                request_id = result.inserted_id
                document["_id"] = request_id
                print(f"✓ Request created: {request_id}")
                
            except PyMongoError as e:
                print(f"✗ Database insert failed: {str(e)}")
                raise DatabaseOperationError("CREATE", f"Insert failed: {str(e)}")
            
            # Step 3: Generate pipelines
            print(f"\n🔄 Step 3: Generating pipelines...")
            try:
                pipeline_ids = self._generate_pipelines_and_chains(
                    request_id,
                    request_dict["serviceList"],
                    initiator_role,
                    created_by,
                    created_ip
                )
                
                print(f"✓ Created {len(pipeline_ids)} pipelines")
                
            except PipelineGenerationError as e:
                print(f"✗ Pipeline generation failed, rolling back...")
                try:
                    self.collection.delete_one({"_id": request_id})
                    print(f"✓ Request rolled back")
                except Exception as rollback_error:
                    print(f"✗ Rollback failed: {str(rollback_error)}")
                raise
            
            # Step 4: Sync status
            print(f"\n📊 Step 4: Syncing status...")
            final_status = self._sync_request_status(request_id, created_by, created_ip)
            document["CrPCRequestStatus"] = final_status.value
            print(f"✓ Status: {final_status.value}")
            
            print(f"\n{'='*60}")
            print(f"✅ Request Created Successfully")
            print(f"   ID: {request_id}")
            print(f"   Pipelines: {len(pipeline_ids)}")
            print(f"{'='*60}\n")
            
            return document
            
        except InvalidServiceListError:
            raise
        except PipelineGenerationError:
            raise
        except DatabaseOperationError:
            raise
        except Exception as e:
            print(f"\n✗ Unexpected error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise DatabaseOperationError("CREATE", f"Unexpected: {str(e)}")
    
    # ========== READ Operation ==========
    def get_request_by_id(self, request_id: PyObjectId) -> Optional[dict]:
        """Get CrPC request by ID."""
        try:
            return self.collection.find_one({"_id": request_id, "isActive": True})
        except PyMongoError as e:
            raise DatabaseOperationError("READ", str(e))
    
    # ========== GET WITH PIPELINES ==========
    def get_request_with_pipelines(self, request_id: PyObjectId) -> Optional[dict]:
        """Get request with all pipeline details."""
        try:
            request = self.get_request_by_id(request_id)
            if not request:
                return None
            
            pipelines = self.pipeline_service.get_pipelines_with_details(request_id)
            request["pipelines"] = pipelines
            
            return request
        except PyMongoError as e:
            raise DatabaseOperationError("GET_WITH_PIPELINES", str(e))
    
    # ========== UPDATE Operation ==========
    def update_request(
        self,
        request_id: PyObjectId,
        data: CrpcRequestUpdateSchema,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> Optional[dict]:
        """Update CrPC request."""
        try:
            existing = self.collection.find_one({"_id": request_id, "isActive": True})
            if not existing:
                raise RequestNotFoundError(str(request_id))
            
            update_dict = data.model_dump(exclude_unset=True)
            
            if "attachmentsNeededForRequest" in update_dict:
                update_dict["attachmentsNeededForRequest"] = [
                    att.model_dump() for att in data.attachmentsNeededForRequest
                ] if data.attachmentsNeededForRequest else []
            
            update_dict["updatedAt"] = datetime.now(timezone.utc)
            update_dict["updatedBy"] = updated_by
            update_dict["updatedIp"] = updated_ip
            
            self.collection.update_one({"_id": request_id}, {"$set": update_dict})
            return self.collection.find_one({"_id": request_id})
            
        except CrpcRequestError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("UPDATE", str(e))
    
    # ========== CLOSE Request ==========
    def close_request(
        self,
        request_id: PyObjectId,
        closure_data: CloseRequestSchema,
        user_role: str,
        closed_by: PyObjectId,
        closed_ip: str
    ) -> dict:
        """Close a CrPC request (SHO only)."""
        try:
            if user_role != "SHO":
                raise UnauthorizedClosureError()
            
            existing = self.collection.find_one({"_id": request_id, "isActive": True})
            if not existing:
                raise RequestNotFoundError(str(request_id))
            
            update_dict = {
                "CrPCRequestStatus": CrpcRequestStatus.CLOSED.value,
                "isActive": False,
                "closureNotes": closure_data.closureNotes,
                "closedAt": datetime.now(timezone.utc),
                "closedBy": closed_by,
                "updatedAt": datetime.now(timezone.utc),
                "updatedBy": closed_by,
                "updatedIp": closed_ip
            }
            
            self.collection.update_one({"_id": request_id}, {"$set": update_dict})
            return self.collection.find_one({"_id": request_id})
            
        except CrpcRequestError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("CLOSE", str(e))
    
    # ========== SEARCH Operation ==========
    def search_requests(
        self,
        search_params: CrpcRequestSearchSchema
    ) -> Tuple[List[dict], int]:
        """Search and filter CrPC requests."""
        try:
            query = {}
            
            if not search_params.includeInactive:
                query["isActive"] = True
            if search_params.unitId:
                query["unitId"] = search_params.unitId
            if search_params.requestedBy:
                query["requestedBy"] = search_params.requestedBy
            if search_params.firNo:
                query["fir.firNo"] = search_params.firNo
            if search_params.CrPCRequestStatus:
                query["CrPCRequestStatus"] = search_params.CrPCRequestStatus.value
            if search_params.requestDateFrom or search_params.requestDateTo:
                query["requestDate"] = {}
                if search_params.requestDateFrom:
                    query["requestDate"]["$gte"] = datetime.combine(
                        search_params.requestDateFrom, datetime.min.time()
                    ).replace(tzinfo=timezone.utc)
                if search_params.requestDateTo:
                    query["requestDate"]["$lte"] = datetime.combine(
                        search_params.requestDateTo, datetime.max.time()
                    ).replace(tzinfo=timezone.utc)
            if search_params.ackNo:
                query["ackNo"] = {"$regex": search_params.ackNo, "$options": "i"}
            
            total = self.collection.count_documents(query)
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            skip = (search_params.page - 1) * search_params.pageSize
            
            cursor = self.collection.find(query).sort(
                search_params.sortBy, sort_order
            ).skip(skip).limit(search_params.pageSize)
            
            return list(cursor), total
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH", str(e))
    
    # ========== GET BY FIR ==========
    def get_by_fir_number(self, fir_no: int) -> List[dict]:
        """Get all requests for a FIR number."""
        try:
            return list(self.collection.find({
                "fir.firNo": fir_no,
                "isActive": True
            }).sort("createdAt", DESCENDING))
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_FIR", str(e))
    
    # ========== GET BY UNIT ==========
    def get_by_unit(self, unit_id: PyObjectId) -> List[dict]:
        """Get all requests for a unit."""
        try:
            return list(self.collection.find({
                "unitId": unit_id,
                "isActive": True
            }).sort("createdAt", DESCENDING))
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_UNIT", str(e))

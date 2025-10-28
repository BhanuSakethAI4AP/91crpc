"""
Purpose: Business logic for Consolidated CrPC Requests.
Core consolidation functionality - format generation to be implemented later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
import os
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from database import get_collection
from models.consolidated_crpc_requests_models import (
    ConsolidatedCrpcRequestCreateSchema,
    ConsolidatedSearchSchema,
)
from utils.validators import PyObjectId
from constants.value_sets import ConsolidatedRequestStatus, DispatchMode


# ========== Custom Exceptions ==========
class ConsolidatedError(Exception):
    """Base exception."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class NotFoundError(ConsolidatedError):
    def __init__(self, record_id: str):
        super().__init__(f"Record '{record_id}' not found", "ERR.CONSOLIDATED.NOT_FOUND")


class NoPipelinesError(ConsolidatedError):
    def __init__(self):
        super().__init__("No approved pipelines available", "ERR.CONSOLIDATED.NO_PIPELINES")


class DatabaseOperationError(ConsolidatedError):
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.CONSOLIDATED.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class ConsolidatedCrpcRequestsService:
    """Service for consolidated CrPC requests."""
    
    def __init__(self):
        """Initialize with database collections."""
        try:
            self.collection: Collection = get_collection("consolidated_crpc_requests")
            self.pipeline_collection: Collection = get_collection("crpc_request_pipelines")
            self.request_collection: Collection = get_collection("crpc_requests")
            self.service_collection: Collection = get_collection("service_master")
            self.operator_collection: Collection = get_collection("operators_list")
            self.operator_service_collection: Collection = get_collection("operator_service_list")
            
            self.upload_dir = "uploads/consolidated"
            os.makedirs(self.upload_dir, exist_ok=True)
            
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== FIND CONSOLIDATABLE PIPELINES ==========
    def find_consolidatable_pipelines(
        self,
        service_id: Optional[PyObjectId] = None,
        operator_id: Optional[PyObjectId] = None
    ) -> Dict[str, List[dict]]:
        """
        Find approved pipelines that can be consolidated.
        Groups by (serviceId, operatorId).
        """
        try:
            query = {
                "lineItemRequestStatus": "Approved",
                "isActive": True
            }
            
            if service_id:
                query["serviceId"] = service_id
            if operator_id:
                query["operatorId"] = operator_id
            
            pipelines = list(self.pipeline_collection.find(query))
            
            if not pipelines:
                return {}
            
            # Filter by canBeConsolidated
            consolidatable = []
            for pipeline in pipelines:
                service = self.service_collection.find_one({"_id": pipeline["serviceId"]})
                if service and service.get("canBeConsolidated", False):
                    consolidatable.append(pipeline)
            
            # Group by (serviceId, operatorId)
            grouped = {}
            for pipeline in consolidatable:
                key = f"{pipeline['serviceId']}_{pipeline['operatorId']}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(pipeline)
            
            return grouped
            
        except PyMongoError as e:
            raise DatabaseOperationError("FIND_PIPELINES", str(e))
    
    # ========== GET AVAILABLE CONSOLIDATIONS ==========
    def get_available_consolidations(self) -> List[Dict[str, Any]]:
        """
        Get list of service-operator combinations ready for consolidation.
        
        Returns summary with count of pending pipelines for each combination.
        """
        try:
            grouped = self.find_consolidatable_pipelines()
            
            available = []
            for key, pipelines in grouped.items():
                service_id, operator_id = key.split("_")
                
                service = self.service_collection.find_one({"_id": PyObjectId(service_id)})
                operator = self.operator_collection.find_one({"_id": PyObjectId(operator_id)})
                
                available.append({
                    "serviceId": service_id,
                    "serviceName": service.get("serviceName") if service else "Unknown",
                    "operatorId": operator_id,
                    "operatorName": operator.get("operatorName") if operator else "Unknown",
                    "pipelineCount": len(pipelines),
                    "oldestRequestDate": min(
                        p.get("createdAt", datetime.now(timezone.utc)) 
                        for p in pipelines
                    ) if pipelines else None
                })
            
            return available
            
        except Exception as e:
            raise DatabaseOperationError("GET_AVAILABLE", str(e))
    
    # ========== GENERATE OUTPUT FILE (PLACEHOLDER) ==========
    def _generate_output_file(
        self,
        pipelines: List[dict],
        service_id: PyObjectId,
        operator_id: PyObjectId,
        service_name: str,
        operator_name: str
    ) -> str:
        """
        Generate output file based on operator format configuration.
        
        TODO: Implement format-specific generation:
        - Excel: Dynamic column mapping
        - Word: Template-based generation
        - PDF: Template conversion
        - AI: Custom format conversion
        
        For now: Creates placeholder file.
        """
        try:
            print(f"📄 Generating output file for {operator_name} - {service_name}")
            
            # TODO: Get format config from operator_service_list
            # format_config = self._get_format_config(service_id, operator_id)
            # format_type = format_config.get("formatType", "excel")
            
            # TODO: Route to appropriate generator
            # if format_type == "excel":
            #     return self._generate_excel(pipelines, format_config)
            # elif format_type == "docx":
            #     return self._generate_docx(pipelines, format_config)
            # elif format_type == "ai_custom":
            #     return self._generate_with_ai(pipelines, format_config)
            
            # PLACEHOLDER: Simple text file for now
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{operator_name}_{service_name}_{timestamp}.txt"
            filepath = os.path.join(self.upload_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(f"Consolidated Request\n")
                f.write(f"Operator: {operator_name}\n")
                f.write(f"Service: {service_name}\n")
                f.write(f"Total Pipelines: {len(pipelines)}\n\n")
                
                for idx, pipeline in enumerate(pipelines, 1):
                    f.write(f"{idx}. Pipeline ID: {pipeline['_id']}\n")
                    f.write(f"   Key Value: {pipeline.get('keyFieldValue')}\n")
                    f.write(f"   From: {pipeline.get('requiredData', {}).get('fromDate')}\n")
                    f.write(f"   To: {pipeline.get('requiredData', {}).get('toDate')}\n\n")
            
            print(f"✓ Placeholder file created: {filepath}")
            print(f"  NOTE: Format-specific generation to be implemented")
            
            return filepath
            
        except Exception as e:
            import traceback
            print(f"Error generating file: {traceback.format_exc()}")
            raise ConsolidatedError(f"File generation failed: {str(e)}", "ERR.FILE_GENERATION")
    
    # ========== CREATE CONSOLIDATION ==========
    def create_consolidation(
        self,
        service_id: PyObjectId,
        operator_id: PyObjectId,
        mode: DispatchMode,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """Create consolidated request."""
        try:
            print(f"\n{'='*60}")
            print(f"📦 Creating Consolidated Request")
            print(f"{'='*60}")
            
            # Step 1: Find pipelines
            print(f"\n🔍 Finding consolidatable pipelines...")
            grouped = self.find_consolidatable_pipelines(service_id, operator_id)
            key = f"{service_id}_{operator_id}"
            
            if key not in grouped or not grouped[key]:
                raise NoPipelinesError()
            
            pipelines = grouped[key]
            print(f"✓ Found {len(pipelines)} pipelines")
            
            # Get names
            service = self.service_collection.find_one({"_id": service_id})
            operator = self.operator_collection.find_one({"_id": operator_id})
            service_name = service.get("serviceName", "Unknown")
            operator_name = operator.get("operatorName", "Unknown")
            
            # Step 2: Generate output file
            print(f"\n📄 Generating output file...")
            output_filepath = self._generate_output_file(
                pipelines, service_id, operator_id, service_name, operator_name
            )
            
            # Step 3: Create record
            print(f"\n💾 Creating consolidated record...")
            now = datetime.now(timezone.utc)
            
            document = {
                "mode": mode.value,
                "serviceId": service_id,
                "operatorId": operator_id,
                "crpcRequestPipelineIds": [p["_id"] for p in pipelines],
                "attachmentsForSendingMail": [],
                "letterFilePaths": [{
                    "attachmentName": os.path.basename(output_filepath),
                    "formatFilePath": output_filepath
                }],
                "consolidatedCrpcRequestStatus": ConsolidatedRequestStatus.NOT_DOWNLOADED.value,
                "downloadedAt": None,
                "totalRequests": len(pipelines),
                "isActive": True,
                "createdAt": now,
                "createdBy": created_by,
                "createdIp": created_ip,
                "updatedAt": now,
                "updatedBy": created_by,
                "updatedIp": created_ip,
            }
            
            result = self.collection.insert_one(document)
            document["_id"] = result.inserted_id
            print(f"✓ Created: {result.inserted_id}")
            
            # Step 4: Update pipeline status
            print(f"\n🔄 Updating pipeline statuses...")
            self.pipeline_collection.update_many(
                {"_id": {"$in": [p["_id"] for p in pipelines]}},
                {"$set": {
                    "lineItemRequestStatus": "Consolidated",
                    "updatedAt": now,
                    "updatedBy": created_by,
                    "updatedIp": created_ip
                }}
            )
            print(f"✓ Updated {len(pipelines)} pipelines")
            
            print(f"\n{'='*60}")
            print(f"✅ Consolidation Complete")
            print(f"{'='*60}\n")
            
            return document
            
        except ConsolidatedError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("CREATE", str(e))
        except Exception as e:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            raise DatabaseOperationError("CREATE", f"Unexpected: {str(e)}")
    
    # ========== GET BY ID ==========
    def get_by_id(self, consolidated_id: PyObjectId) -> Optional[dict]:
        """Get consolidated request by ID."""
        try:
            return self.collection.find_one({"_id": consolidated_id, "isActive": True})
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_ID", str(e))
    
    # ========== MARK AS DOWNLOADED ==========
    def mark_as_downloaded(
        self,
        consolidated_id: PyObjectId,
        downloaded_by: PyObjectId,
        downloaded_ip: str
    ) -> dict:
        """Mark as downloaded."""
        try:
            now = datetime.now(timezone.utc)
            
            self.collection.update_one(
                {"_id": consolidated_id},
                {"$set": {
                    "consolidatedCrpcRequestStatus": ConsolidatedRequestStatus.DOWNLOADED.value,
                    "downloadedAt": now,
                    "updatedAt": now,
                    "updatedBy": downloaded_by,
                    "updatedIp": downloaded_ip
                }}
            )
            
            return self.collection.find_one({"_id": consolidated_id})
            
        except PyMongoError as e:
            raise DatabaseOperationError("MARK_DOWNLOADED", str(e))
    
    # ========== SEARCH ==========
    def search(self, search_params: ConsolidatedSearchSchema) -> Tuple[List[dict], int]:
        """Search consolidated requests."""
        try:
            query = {}
            
            if not search_params.includeInactive:
                query["isActive"] = True
            if search_params.serviceId:
                query["serviceId"] = search_params.serviceId
            if search_params.operatorId:
                query["operatorId"] = search_params.operatorId
            if search_params.status:
                query["consolidatedCrpcRequestStatus"] = search_params.status.value
            if search_params.createdDateFrom or search_params.createdDateTo:
                query["createdAt"] = {}
                if search_params.createdDateFrom:
                    query["createdAt"]["$gte"] = search_params.createdDateFrom
                if search_params.createdDateTo:
                    query["createdAt"]["$lte"] = search_params.createdDateTo
            
            total = self.collection.count_documents(query)
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            skip = (search_params.page - 1) * search_params.pageSize
            
            cursor = self.collection.find(query).sort(
                search_params.sortBy, sort_order
            ).skip(skip).limit(search_params.pageSize)
            
            return list(cursor), total
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH", str(e))
    
    # ========== DELETE (SOFT) ==========
    def delete_consolidation(
        self,
        consolidated_id: PyObjectId,
        deleted_by: PyObjectId,
        deleted_ip: str
    ) -> bool:
        """Soft delete consolidated request."""
        try:
            result = self.collection.update_one(
                {"_id": consolidated_id, "isActive": True},
                {"$set": {
                    "isActive": False,
                    "updatedAt": datetime.now(timezone.utc),
                    "updatedBy": deleted_by,
                    "updatedIp": deleted_ip
                }}
            )
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            raise DatabaseOperationError("DELETE", str(e))

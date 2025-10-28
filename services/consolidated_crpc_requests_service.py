"""
Purpose: Business logic for Consolidated CrPC Requests.
UPDATED: Operator-centric consolidation (groups by operator only, not by service).
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
    def __init__(self, operator_id: str):
        super().__init__(
            f"No approved pipelines available for operator '{operator_id}'",
            "ERR.CONSOLIDATED.NO_PIPELINES"
        )


class InvalidOperatorError(ConsolidatedError):
    def __init__(self, operator_id: str):
        super().__init__(
            f"Operator '{operator_id}' not found or invalid",
            "ERR.CONSOLIDATED.INVALID_OPERATOR"
        )


class DatabaseOperationError(ConsolidatedError):
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.CONSOLIDATED.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class ConsolidatedCrpcRequestsService:
    """Service for consolidated CrPC requests (Operator-Centric)."""
    
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
    
    # ========== FIND CONSOLIDATABLE PIPELINES (OPERATOR-CENTRIC) ==========
    def find_consolidatable_pipelines(
        self,
        operator_id: Optional[PyObjectId] = None
    ) -> Dict[str, List[dict]]:
        """
        Find approved pipelines that can be consolidated.
        
        IMPORTANT: Groups by OPERATOR only (not by service).
        Filters by service.canBeConsolidated = true.
        
        Args:
            operator_id: Optional operator filter
            
        Returns:
            Dict[str, List[dict]]: Grouped by operator_id
                Example: {
                    "operator_id_1": [pipeline1, pipeline2, pipeline3],  # Mixed services
                    "operator_id_2": [pipeline4, pipeline5]
                }
        """
        try:
            query = {
                "lineItemRequestStatus": "Approved",
                "isActive": True
            }
            
            if operator_id:
                query["operatorId"] = operator_id
            
            pipelines = list(self.pipeline_collection.find(query))
            
            if not pipelines:
                return {}
            
            # Filter by canBeConsolidated
            print(f"\n🔍 Filtering by canBeConsolidated flag...")
            consolidatable = []
            non_consolidatable = []
            
            for pipeline in pipelines:
                service = self.service_collection.find_one({"_id": pipeline["serviceId"]})
                if service and service.get("canBeConsolidated", False):
                    consolidatable.append(pipeline)
                else:
                    non_consolidatable.append(pipeline)
                    print(f"  ⚠️  Skipping pipeline {pipeline['_id']} - Service '{service.get('serviceName')}' canBeConsolidated=false")
            
            print(f"✓ Consolidatable: {len(consolidatable)}")
            print(f"✗ Non-consolidatable: {len(non_consolidatable)}")
            
            # Group by OPERATOR only
            grouped = {}
            for pipeline in consolidatable:
                operator_id_str = str(pipeline['operatorId'])
                if operator_id_str not in grouped:
                    grouped[operator_id_str] = []
                grouped[operator_id_str].append(pipeline)
            
            return grouped
            
        except PyMongoError as e:
            raise DatabaseOperationError("FIND_PIPELINES", str(e))
    
    # ========== GET AVAILABLE CONSOLIDATIONS ==========
    def get_available_consolidations(self) -> List[Dict[str, Any]]:
        """
        Get list of operators ready for consolidation.
        
        Returns summary with count of pending pipelines PER OPERATOR.
        Includes breakdown by service types within each operator.
        """
        try:
            grouped = self.find_consolidatable_pipelines()
            
            available = []
            for operator_id_str, pipelines in grouped.items():
                operator = self.operator_collection.find_one({"_id": PyObjectId(operator_id_str)})
                
                # Build service breakdown
                service_breakdown = {}
                for pipeline in pipelines:
                    service_id_str = str(pipeline["serviceId"])
                    if service_id_str not in service_breakdown:
                        service = self.service_collection.find_one({"_id": pipeline["serviceId"]})
                        service_breakdown[service_id_str] = {
                            "serviceId": service_id_str,
                            "serviceName": service.get("serviceName") if service else "Unknown",
                            "count": 0
                        }
                    service_breakdown[service_id_str]["count"] += 1
                
                available.append({
                    "operatorId": operator_id_str,
                    "operatorName": operator.get("operatorName") if operator else "Unknown",
                    "pipelineCount": len(pipelines),
                    "serviceBreakdown": list(service_breakdown.values()),
                    "oldestRequestDate": min(
                        p.get("createdAt", datetime.now(timezone.utc)) 
                        for p in pipelines
                    ) if pipelines else None,
                    "totalPipelinesValue": len(pipelines)  # Backward compatibility
                })
            
            return available
            
        except Exception as e:
            raise DatabaseOperationError("GET_AVAILABLE", str(e))
    
    # ========== GET FORMAT CONFIG ==========
    def _get_format_config(
        self,
        operator_id: PyObjectId,
        pipelines: List[dict]
    ) -> Dict[str, Any]:
        """
        Get format configuration for operator consolidation.
        
        Resolution Logic:
        1. Get operator config from operator_service_list
        2. For each service in pipelines:
           - Check if serviceSpecificFormat exists
           - Otherwise use globalFormat
        3. Return combined format config
        
        Args:
            operator_id: Operator ID
            pipelines: List of pipelines (may have mixed services)
            
        Returns:
            dict: Format configuration
        """
        try:
            # Get operator config
            operator_config = self.operator_service_collection.find_one({
                "operatorId": operator_id,
                "isDeleted": False
            })
            
            if not operator_config:
                print(f"⚠️  No format config found for operator {operator_id}")
                return {}
            
            # Get unique services in pipelines
            service_ids = list(set(str(p["serviceId"]) for p in pipelines))
            
            # Build format config
            format_config = {
                "operatorId": operator_id,
                "globalFormat": operator_config.get("globalFormat"),
                "serviceFormats": {}
            }
            
            # Get format for each service
            for service_id_str in service_ids:
                service_id = PyObjectId(service_id_str)
                
                # Find service in operator's services array
                service_config = None
                for svc in operator_config.get("services", []):
                    if svc.get("serviceId") == service_id:
                        service_config = svc
                        break
                
                if service_config:
                    # Determine format source
                    if service_config.get("serviceSpecificFormat"):
                        format_config["serviceFormats"][service_id_str] = {
                            "source": "service-specific",
                            "format": service_config["serviceSpecificFormat"],
                            "requiredData": service_config.get("requiredData", {})
                        }
                    elif format_config["globalFormat"]:
                        format_config["serviceFormats"][service_id_str] = {
                            "source": "global",
                            "format": format_config["globalFormat"],
                            "requiredData": service_config.get("requiredData", {})
                        }
            
            return format_config
            
        except Exception as e:
            print(f"Error getting format config: {str(e)}")
            return {}
    
    # ========== GENERATE OUTPUT FILE (PLACEHOLDER) ==========
    def _generate_output_file(
        self,
        pipelines: List[dict],
        operator_id: PyObjectId,
        operator_name: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Generate output file based on operator format configuration.
        
        IMPORTANT: Single file for ALL services from the operator.
        
        TODO: Implement format-specific generation:
        - Excel: Dynamic column mapping with multiple sheets (one per service)
        - Word: Template-based generation
        - PDF: Template conversion
        - AI: Custom format conversion
        
        Args:
            pipelines: List of pipelines (can be mixed services)
            operator_id: Operator ID
            operator_name: Operator name
            
        Returns:
            Tuple[str, List[dict]]: (filepath, attachments list)
        """
        try:
            print(f"📄 Generating output file for {operator_name}")
            
            # Get format config
            format_config = self._get_format_config(operator_id, pipelines)
            
            # Group pipelines by service
            by_service = {}
            for pipeline in pipelines:
                service_id_str = str(pipeline["serviceId"])
                if service_id_str not in by_service:
                    service = self.service_collection.find_one({"_id": pipeline["serviceId"]})
                    by_service[service_id_str] = {
                        "serviceName": service.get("serviceName") if service else "Unknown",
                        "pipelines": []
                    }
                by_service[service_id_str]["pipelines"].append(pipeline)
            
            print(f"  Services in consolidation: {list(by_service.keys())}")
            
            # TODO: Get format config and route to appropriate generator
            # if format_config.get("formatType") == "excel":
            #     return self._generate_excel(pipelines, by_service, format_config)
            # elif format_config.get("formatType") == "docx":
            #     return self._generate_docx(pipelines, by_service, format_config)
            # elif format_config.get("formatType") == "ai_custom":
            #     return self._generate_with_ai(pipelines, by_service, format_config)
            
            # PLACEHOLDER: Simple text file for now
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{operator_name}_AllServices_{timestamp}.txt"
            filepath = os.path.join(self.upload_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(f"{'='*60}\n")
                f.write(f"CONSOLIDATED REQUEST - ALL SERVICES\n")
                f.write(f"{'='*60}\n\n")
                f.write(f"Operator: {operator_name}\n")
                f.write(f"Total Pipelines: {len(pipelines)}\n")
                f.write(f"Services: {len(by_service)}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Write each service section
                for service_id_str, service_data in by_service.items():
                    f.write(f"\n{'='*60}\n")
                    f.write(f"SERVICE: {service_data['serviceName']}\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(f"Total Requests: {len(service_data['pipelines'])}\n\n")
                    
                    for idx, pipeline in enumerate(service_data['pipelines'], 1):
                        f.write(f"{idx}. Pipeline ID: {pipeline['_id']}\n")
                        f.write(f"   Key Value: {pipeline.get('keyFieldValue')}\n")
                        
                        required_data = pipeline.get('requiredData', {})
                        if required_data:
                            if 'fromDate' in required_data:
                                f.write(f"   From: {required_data.get('fromDate')}\n")
                            if 'toDate' in required_data:
                                f.write(f"   To: {required_data.get('toDate')}\n")
                        
                        f.write(f"\n")
            
            print(f"✓ Placeholder file created: {filepath}")
           
            
            # Get attachments from operator config
            attachments = []
            if format_config.get("globalFormat"):
                attachments = format_config["globalFormat"].get("listOfAttachments", [])
            
            return filepath, attachments
            
        except Exception as e:
            import traceback
            print(f"Error generating file: {traceback.format_exc()}")
            raise ConsolidatedError(f"File generation failed: {str(e)}", "ERR.FILE_GENERATION")
    
    # ========== CREATE CONSOLIDATION (OPERATOR-CENTRIC) ==========
    def create_consolidation(
        self,
        operator_id: PyObjectId,
        mode: DispatchMode,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create consolidated request for an operator.
        
        IMPORTANT: Consolidates ALL services for the operator in ONE file.
        
        Args:
            operator_id: Operator ID (PRIMARY grouping)
            mode: Dispatch mode
            created_by: User creating the consolidation
            created_ip: IP address
            
        Returns:
            dict: Created consolidation document
        """
        try:
            print(f"\n{'='*60}")
            print(f"📦 Creating Consolidated Request (Operator-Centric)")
            print(f"{'='*60}")
            
            # Validate operator exists
            operator = self.operator_collection.find_one({"_id": operator_id, "isDeleted": False})
            if not operator:
                raise InvalidOperatorError(str(operator_id))
            
            operator_name = operator.get("operatorName", "Unknown")
            print(f"Operator: {operator_name}")
            
            # Step 1: Find pipelines (by operator only)
            print(f"\n🔍 Finding consolidatable pipelines...")
            grouped = self.find_consolidatable_pipelines(operator_id)
            operator_id_str = str(operator_id)
            
            if operator_id_str not in grouped or not grouped[operator_id_str]:
                raise NoPipelinesError(str(operator_id))
            
            pipelines = grouped[operator_id_str]
            
            # Count services
            service_ids = set(str(p["serviceId"]) for p in pipelines)
            print(f"✓ Found {len(pipelines)} pipelines across {len(service_ids)} services")
            
            # Show service breakdown
            for service_id_str in service_ids:
                service = self.service_collection.find_one({"_id": PyObjectId(service_id_str)})
                service_name = service.get("serviceName") if service else "Unknown"
                count = sum(1 for p in pipelines if str(p["serviceId"]) == service_id_str)
                print(f"   - {service_name}: {count} pipelines")
            
            # Step 2: Generate output file (single file for all services)
         
            output_filepath, attachments = self._generate_output_file(
                pipelines, operator_id, operator_name
            )
            
            # Step 3: Create record
           
            now = datetime.now(timezone.utc)
            
            document = {
                "mode": mode.value,
                # serviceId removed - operator-centric
                "operatorId": operator_id,
                "crpcRequestPipelineIds": [p["_id"] for p in pipelines],
                "attachmentsForSendingMail": attachments,
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
                    "consolidatedRequestId": result.inserted_id,  # Link back
                    "updatedAt": now,
                    "updatedBy": created_by,
                    "updatedIp": created_ip
                }}
            )
            print(f"✓ Updated {len(pipelines)} pipelines")
            
            print(f"\n{'='*60}")
            print(f"✅ Consolidation Complete")
            print(f"   Operator: {operator_name}")
            print(f"   Services: {len(service_ids)}")
            print(f"   Pipelines: {len(pipelines)}")
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
        """
        Mark consolidation as downloaded.
        
        Only updates status on first download (idempotent).
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Only update if not already downloaded
            result = self.collection.update_one(
                {
                    "_id": consolidated_id,
                    "consolidatedCrpcRequestStatus": ConsolidatedRequestStatus.NOT_DOWNLOADED.value
                },
                {"$set": {
                    "consolidatedCrpcRequestStatus": ConsolidatedRequestStatus.DOWNLOADED.value,
                    "downloadedAt": now,
                    "updatedAt": now,
                    "updatedBy": downloaded_by,
                    "updatedIp": downloaded_ip
                }}
            )
            
            if result.modified_count == 0:
                print(f"⚠️  Consolidation {consolidated_id} already downloaded")
            else:
                print(f"✓ Marked as downloaded: {consolidated_id}")
            
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
            
            # Operator filter (PRIMARY)
            if search_params.operatorId:
                query["operatorId"] = search_params.operatorId
            
            # Status filter
            if search_params.status:
                query["consolidatedCrpcRequestStatus"] = search_params.status.value
            
            # Mode filter
            if search_params.mode:
                query["mode"] = search_params.mode.value
            
            # Date range
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
        """
        Soft delete consolidated request.
        
        Also reverts pipeline statuses back to "Approved".
        """
        try:
            # Get consolidation
            consolidation = self.get_by_id(consolidated_id)
            if not consolidation:
                raise NotFoundError(str(consolidated_id))
            
            # Soft delete consolidation
            result = self.collection.update_one(
                {"_id": consolidated_id, "isActive": True},
                {"$set": {
                    "isActive": False,
                    "updatedAt": datetime.now(timezone.utc),
                    "updatedBy": deleted_by,
                    "updatedIp": deleted_ip
                }}
            )
            
            if result.modified_count > 0:
                # Revert pipelines back to "Approved"
                self.pipeline_collection.update_many(
                    {"_id": {"$in": consolidation.get("crpcRequestPipelineIds", [])}},
                    {"$set": {
                        "lineItemRequestStatus": "Approved",
                        "consolidatedRequestId": None,
                        "updatedAt": datetime.now(timezone.utc),
                        "updatedBy": deleted_by,
                        "updatedIp": deleted_ip
                    }}
                )
                print(f"✓ Deleted consolidation and reverted pipelines")
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            raise DatabaseOperationError("DELETE", str(e))

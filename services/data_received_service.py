"""
Purpose: Business logic for Data Received operations.
Uses DataReceivedFilesService for file operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from database import get_collection
from models.data_received_models import (
    DataReceivedCreateSchema,
    DataReceivedSearchSchema,
    ResolveConflictSchema,
)
from services.data_received_files_service import DataReceivedFilesService
from utils.validators import PyObjectId
from constants.value_sets import ProcessingStatus, MatchingStatus


# ========== Custom Exceptions ==========
class DataReceivedError(Exception):
    """Base exception for Data Received operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DataReceivedNotFoundError(DataReceivedError):
    """Raised when data received record is not found."""
    def __init__(self, data_id: str):
        super().__init__(
            f"Data received with ID '{data_id}' not found",
            "ERR.DATA_RECEIVED.NOT_FOUND"
        )


class DatabaseOperationError(DataReceivedError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.DATA_RECEIVED.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class DataReceivedService:
    """Service for Data Received operations."""
    
    def __init__(self):
        """Initialize service with collections and file service."""
        try:
            self.collection: Collection = get_collection("data_received")
            self.pipeline_collection: Collection = get_collection("crpc_request_pipelines")
            self.request_collection: Collection = get_collection("crpc_requests")
            self.file_service = DataReceivedFilesService()
            
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== AUTO-MATCH FILES ==========
    def _auto_match_files(
        self,
        data_received_id: PyObjectId,
        operator_id: PyObjectId,
        file_records: List[dict],
        created_by: PyObjectId,
        created_ip: str
    ) -> Dict[str, Any]:
        """Auto-match files to pipelines using DataReceivedFilesService."""
        results = {
            "auto_matched": [],
            "conflicts": [],
            "unmatched": []
        }
        
        for file_record in file_records:
            try:
                # Use file service to extract key
                key_value = self.file_service.extract_key_from_filename(file_record["fileName"])
                file_record["extractedKeyFieldValue"] = key_value
                
                if not key_value:
                    file_record["matchingStatus"] = MatchingStatus.UNMATCHED.value
                    file_record["matchedPipelineId"] = None
                    file_record["conflictPipelineIds"] = []
                    results["unmatched"].append(file_record)
                    continue
                
                # Use file service to find pipelines
                pipelines = self.file_service.find_matching_pipelines(operator_id, key_value)
                
                if len(pipelines) == 0:
                    file_record["matchingStatus"] = MatchingStatus.UNMATCHED.value
                    file_record["matchedPipelineId"] = None
                    file_record["conflictPipelineIds"] = []
                    results["unmatched"].append(file_record)
                    
                elif len(pipelines) == 1:
                    file_record["matchingStatus"] = MatchingStatus.AUTO_MATCHED.value
                    file_record["matchedPipelineId"] = pipelines[0]["_id"]
                    file_record["conflictPipelineIds"] = []
                    results["auto_matched"].append(file_record)
                    
                    # Update pipeline status
                    self.pipeline_collection.update_one(
                        {"_id": pipelines[0]["_id"]},
                        {
                            "$set": {
                                "lineItemRequestStatus": "DataReceived",
                                "updatedAt": datetime.now(timezone.utc),
                                "updatedBy": created_by,
                                "updatedIp": created_ip
                            }
                        }
                    )
                    
                else:
                    file_record["matchingStatus"] = MatchingStatus.CONFLICT.value
                    file_record["matchedPipelineId"] = None
                    file_record["conflictPipelineIds"] = [p["_id"] for p in pipelines]
                    results["conflicts"].append(file_record)
                
            except Exception as e:
                print(f"Error matching file {file_record['fileName']}: {str(e)}")
                file_record["matchingStatus"] = MatchingStatus.UNMATCHED.value
                results["unmatched"].append(file_record)
        
        return results
    
    # ========== CREATE DATA RECEIVED ==========
    def create_data_received(
        self,
        data: DataReceivedCreateSchema,
        files: List[Dict[str, Any]],
        created_by: PyObjectId,
        created_ip: str
    ) -> Tuple[dict, Dict[str, Any]]:
        """Create data received record with auto-matching."""
        try:
            print(f"\n{'='*60}")
            print(f"📥 Processing Received Data")
            print(f"{'='*60}")
            
            # Step 1: Create data_received record
            print(f"\n📄 Step 1: Creating data_received record...")
            now = datetime.now(timezone.utc)
            
            data_dict = data.model_dump()
            if data.emailMetaData:
                data_dict["emailMetaData"] = data.emailMetaData.model_dump()
            
            document = {
                **data_dict,
                "processingStatus": ProcessingStatus.PENDING.value,
                "autoMatchedCount": 0,
                "conflictCount": 0,
                "unmatchedCount": 0,
                "isActive": True,
                "createdAt": now,
                "createdBy": created_by,
                "createdIp": created_ip,
                "updatedAt": now,
                "updatedBy": created_by,
                "updatedIp": created_ip,
            }
            
            result = self.collection.insert_one(document)
            data_received_id = result.inserted_id
            document["_id"] = data_received_id
            print(f"✓ Data received record created: {data_received_id}")
            
            # Step 2: Prepare file records
            print(f"\n📁 Step 2: Preparing file records...")
            file_records = []
            for file_info in files:
                file_record = {
                    "dataReceivedId": data_received_id,
                    "fileName": file_info["fileName"],
                    "fileType": file_info["fileType"],
                    "filePath": file_info["filePath"],
                    "fileSize": file_info["fileSize"],
                    "uploadedAt": file_info.get("uploadedAt", now),
                }
                file_records.append(file_record)
            
            # Step 3: Auto-match files
            print(f"\n🔄 Step 3: Auto-matching files...")
            matching_results = self._auto_match_files(
                data_received_id,
                data.operatorId,
                file_records,
                created_by,
                created_ip
            )
            
            # Step 4: Create file records using file service
            print(f"\n💾 Step 4: Creating file records...")
            for file_record in file_records:
                self.file_service.create_file(file_record, created_by, created_ip)
            
            print(f"✓ Auto-matched: {len(matching_results['auto_matched'])}")
            print(f"⚠️  Conflicts: {len(matching_results['conflicts'])}")
            print(f"❌ Unmatched: {len(matching_results['unmatched'])}")
            
            # Step 5: Update counts and status
            print(f"\n📊 Step 5: Updating processing status...")
            auto_matched_count = len(matching_results['auto_matched'])
            conflict_count = len(matching_results['conflicts'])
            unmatched_count = len(matching_results['unmatched'])
            
            if conflict_count > 0:
                processing_status = ProcessingStatus.HAS_CONFLICTS.value
            elif auto_matched_count == len(file_records):
                processing_status = ProcessingStatus.COMPLETED.value
            else:
                processing_status = ProcessingStatus.AUTO_MATCHED.value
            
            self.collection.update_one(
                {"_id": data_received_id},
                {
                    "$set": {
                        "processingStatus": processing_status,
                        "autoMatchedCount": auto_matched_count,
                        "conflictCount": conflict_count,
                        "unmatchedCount": unmatched_count,
                        "updatedAt": datetime.now(timezone.utc),
                    }
                }
            )
            
            document.update({
                "processingStatus": processing_status,
                "autoMatchedCount": auto_matched_count,
                "conflictCount": conflict_count,
                "unmatchedCount": unmatched_count
            })
            
            print(f"✓ Processing status: {processing_status}")
            print(f"\n{'='*60}")
            print(f"✅ Data Received Processing Complete")
            print(f"{'='*60}\n")
            
            return document, matching_results
            
        except PyMongoError as e:
            raise DatabaseOperationError("CREATE", str(e))
        except Exception as e:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            raise DatabaseOperationError("CREATE", f"Unexpected: {str(e)}")
    
    # ========== GET BY ID ==========
    def get_by_id(self, data_received_id: PyObjectId) -> Optional[dict]:
        """Get data received by ID."""
        try:
            return self.collection.find_one({"_id": data_received_id, "isActive": True})
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_ID", str(e))
    
    # ========== GET FILES ==========
    def get_files(self, data_received_id: PyObjectId) -> List[dict]:
        """Get all files for batch - delegates to file service."""
        return self.file_service.get_by_data_received_id(data_received_id)
    
    # ========== GET CONFLICTS ==========
    def get_conflicts(self, data_received_id: PyObjectId) -> List[dict]:
        """Get conflicted files with pipeline details."""
        files = self.file_service.get_by_status(
            MatchingStatus.CONFLICT,
            data_received_id=data_received_id
        )
        
        # Enrich with pipeline details
        for file in files:
            file["potentialMatches"] = []
            for pipeline_id in file.get("conflictPipelineIds", []):
                pipeline = self.pipeline_collection.find_one({"_id": pipeline_id})
                if pipeline:
                    request = self.request_collection.find_one({"_id": pipeline["crpcRequestId"]})
                    file["potentialMatches"].append({
                        "pipelineId": str(pipeline_id),
                        "requestId": str(pipeline["crpcRequestId"]),
                        "firNo": request["fir"][0]["firNo"] if request and request.get("fir") else None,
                        "requestDate": request.get("requestDate") if request else None,
                        "keyFieldValue": pipeline.get("keyFieldValue")
                    })
        
        return files
    
    # ========== GET UNMATCHED ==========
    def get_unmatched(self, data_received_id: PyObjectId) -> List[dict]:
        """Get unmatched files."""
        return self.file_service.get_by_status(
            MatchingStatus.UNMATCHED,
            data_received_id=data_received_id
        )
    
    # ========== RESOLVE CONFLICT ==========
    def resolve_conflict(
        self,
        conflict_data: ResolveConflictSchema,
        resolved_by: PyObjectId,
        resolved_ip: str
    ) -> dict:
        """Resolve conflict - delegates to file service."""
        result = self.file_service.manual_map_file(
            conflict_data.fileId,
            conflict_data.selectedPipelineId,
            resolved_by,
            resolved_ip
        )
        
        # Recalculate parent counts
        file = self.file_service.get_by_id(conflict_data.fileId)
        if file:
            self._recalculate_counts(file["dataReceivedId"])
        
        return result
    
    # ========== RECALCULATE COUNTS ==========
    def _recalculate_counts(self, data_received_id: PyObjectId) -> None:
        """Recalculate counts for data_received record."""
        try:
            files = self.file_service.get_by_data_received_id(data_received_id)
            
            auto_matched = sum(1 for f in files if f["matchingStatus"] == MatchingStatus.AUTO_MATCHED.value)
            conflicts = sum(1 for f in files if f["matchingStatus"] == MatchingStatus.CONFLICT.value)
            unmatched = sum(1 for f in files if f["matchingStatus"] == MatchingStatus.UNMATCHED.value)
            manually_mapped = sum(1 for f in files if f["matchingStatus"] == MatchingStatus.MANUALLY_MAPPED.value)
            
            if conflicts > 0:
                status = ProcessingStatus.HAS_CONFLICTS.value
            elif unmatched > 0:
                status = ProcessingStatus.AUTO_MATCHED.value
            else:
                status = ProcessingStatus.COMPLETED.value
            
            self.collection.update_one(
                {"_id": data_received_id},
                {
                    "$set": {
                        "autoMatchedCount": auto_matched + manually_mapped,
                        "conflictCount": conflicts,
                        "unmatchedCount": unmatched,
                        "processingStatus": status,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
        except Exception as e:
            print(f"Warning: Failed to recalculate counts: {str(e)}")
    
    # ========== SEARCH ==========
    def search(
        self,
        search_params: DataReceivedSearchSchema
    ) -> Tuple[List[dict], int]:
        """Search data received records."""
        try:
            query = {}
            
            if not search_params.includeInactive:
                query["isActive"] = True
            if search_params.operatorId:
                query["operatorId"] = search_params.operatorId
            if search_params.processingStatus:
                query["processingStatus"] = search_params.processingStatus.value
            if search_params.receivedDateFrom or search_params.receivedDateTo:
                query["receivedAt"] = {}
                if search_params.receivedDateFrom:
                    query["receivedAt"]["$gte"] = search_params.receivedDateFrom
                if search_params.receivedDateTo:
                    query["receivedAt"]["$lte"] = search_params.receivedDateTo
            
            total = self.collection.count_documents(query)
            sort_order = ASCENDING if search_params.sortOrder == "asc" else DESCENDING
            skip = (search_params.page - 1) * search_params.pageSize
            
            cursor = self.collection.find(query).sort(
                search_params.sortBy, sort_order
            ).skip(skip).limit(search_params.pageSize)
            
            return list(cursor), total
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH", str(e))

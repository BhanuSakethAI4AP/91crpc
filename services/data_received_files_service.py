"""
Purpose: Business logic for Data Received Files operations.
Handles individual file operations independently.

Used by data_received_service.py for file management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import re
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from database import get_collection
from utils.validators import PyObjectId
from constants.value_sets import MatchingStatus


# ========== Custom Exceptions ==========
class FileError(Exception):
    """Base exception for file operations."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class FileNotFoundError(FileError):
    """Raised when file is not found."""
    def __init__(self, file_id: str):
        super().__init__(
            f"File with ID '{file_id}' not found",
            "ERR.FILE.NOT_FOUND"
        )


class DatabaseOperationError(FileError):
    """Raised when database operation fails."""
    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Database operation '{operation}' failed: {details}",
            f"ERR.FILE.{operation.upper()}.DB_ERROR"
        )


# ========== Service Class ==========
class DataReceivedFilesService:
    """Service for individual file operations."""
    
    def __init__(self):
        """Initialize with database collections."""
        try:
            self.collection: Collection = get_collection("data_received_files")
            self.pipeline_collection: Collection = get_collection("crpc_request_pipelines")
            self.request_collection: Collection = get_collection("crpc_requests")
            
        except Exception as e:
            raise DatabaseOperationError("INIT", str(e))
    
    # ========== PATTERN EXTRACTION ==========
    def extract_key_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract key field value from filename.
        
        PUBLIC method - can be used by data_received_service.
        """
        patterns = [
            r'(\d{10})',                    # Phone number
            r'([A-Z]{4}0[A-Z0-9]{6})',      # IFSC code
            r'(\d{15})',                    # IMEI
            r'([\w\.-]+@[\w\.-]+\.\w+)',    # Email
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    # ========== FIND MATCHING PIPELINES ==========
    def find_matching_pipelines(
        self,
        operator_id: PyObjectId,
        key_field_value: str
    ) -> List[dict]:
        """
        Find pipelines matching operator and key value.
        
        PUBLIC method - can be used by data_received_service.
        """
        try:
            query = {
                "operatorId": operator_id,
                "keyFieldValue": key_field_value,
                "lineItemRequestStatus": "Approved",
                "isActive": True
            }
            
            return list(self.pipeline_collection.find(query))
            
        except PyMongoError as e:
            raise DatabaseOperationError("FIND_PIPELINES", str(e))
    
    # ========== CREATE FILE ==========
    def create_file(
        self,
        file_data: dict,
        created_by: PyObjectId,
        created_ip: str
    ) -> dict:
        """
        Create a file record.
        
        PUBLIC method - used by data_received_service during upload.
        """
        try:
            now = datetime.now(timezone.utc)
            
            document = {
                **file_data,
                "matchingStatus": MatchingStatus.UNMATCHED.value,
                "matchedPipelineId": None,
                "conflictPipelineIds": [],
                "manuallyMappedBy": None,
                "manuallyMappedAt": None,
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
            
            return document
            
        except PyMongoError as e:
            raise DatabaseOperationError("CREATE", str(e))
    
    # ========== UPDATE FILE STATUS ==========
    def update_file_status(
        self,
        file_id: PyObjectId,
        status: MatchingStatus,
        matched_pipeline_id: Optional[PyObjectId] = None,
        conflict_pipeline_ids: Optional[List[PyObjectId]] = None,
        updated_by: Optional[PyObjectId] = None,
        updated_ip: Optional[str] = None
    ) -> dict:
        """
        Update file matching status.
        
        PUBLIC method - used by data_received_service during auto-matching.
        """
        try:
            now = datetime.now(timezone.utc)
            
            update_data = {
                "matchingStatus": status.value,
                "updatedAt": now
            }
            
            if matched_pipeline_id is not None:
                update_data["matchedPipelineId"] = matched_pipeline_id
            
            if conflict_pipeline_ids is not None:
                update_data["conflictPipelineIds"] = conflict_pipeline_ids
            
            if updated_by:
                update_data["updatedBy"] = updated_by
            if updated_ip:
                update_data["updatedIp"] = updated_ip
            
            self.collection.update_one(
                {"_id": file_id},
                {"$set": update_data}
            )
            
            return self.collection.find_one({"_id": file_id})
            
        except PyMongoError as e:
            raise DatabaseOperationError("UPDATE_STATUS", str(e))
    
    # ========== GET BY ID ==========
    def get_by_id(self, file_id: PyObjectId) -> Optional[dict]:
        """Get file by ID."""
        try:
            return self.collection.find_one({
                "_id": file_id,
                "isActive": True
            })
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_ID", str(e))
    
    # ========== GET BY DATA RECEIVED ID ==========
    def get_by_data_received_id(self, data_received_id: PyObjectId) -> List[dict]:
        """Get all files for a data_received batch."""
        try:
            return list(self.collection.find({
                "dataReceivedId": data_received_id,
                "isActive": True
            }).sort("fileName", ASCENDING))
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_DATA_RECEIVED_ID", str(e))
    
    # ========== GET BY STATUS ==========
    def get_by_status(
        self,
        status: MatchingStatus,
        data_received_id: Optional[PyObjectId] = None,
        limit: int = 50
    ) -> List[dict]:
        """Get files by matching status."""
        try:
            query = {
                "matchingStatus": status.value,
                "isActive": True
            }
            
            if data_received_id:
                query["dataReceivedId"] = data_received_id
            
            return list(self.collection.find(query).sort("uploadedAt", DESCENDING).limit(limit))
            
        except PyMongoError as e:
            raise DatabaseOperationError("GET_BY_STATUS", str(e))
    
    # ========== MANUAL MAP ==========
    def manual_map_file(
        self,
        file_id: PyObjectId,
        pipeline_id: PyObjectId,
        mapped_by: PyObjectId,
        mapped_ip: str
    ) -> dict:
        """Manually map file to pipeline."""
        try:
            file = self.collection.find_one({"_id": file_id, "isActive": True})
            if not file:
                raise FileNotFoundError(str(file_id))
            
            # Verify pipeline exists
            pipeline = self.pipeline_collection.find_one({
                "_id": pipeline_id,
                "lineItemRequestStatus": "Approved",
                "isActive": True
            })
            
            if not pipeline:
                raise ValueError("Pipeline not found or not in Approved status")
            
            # Update file
            now = datetime.now(timezone.utc)
            self.collection.update_one(
                {"_id": file_id},
                {
                    "$set": {
                        "matchingStatus": MatchingStatus.MANUALLY_MAPPED.value,
                        "matchedPipelineId": pipeline_id,
                        "conflictPipelineIds": [],
                        "manuallyMappedBy": mapped_by,
                        "manuallyMappedAt": now,
                        "updatedAt": now,
                        "updatedBy": mapped_by,
                        "updatedIp": mapped_ip
                    }
                }
            )
            
            # Update pipeline status
            self.pipeline_collection.update_one(
                {"_id": pipeline_id},
                {
                    "$set": {
                        "lineItemRequestStatus": "DataReceived",
                        "updatedAt": now,
                        "updatedBy": mapped_by,
                        "updatedIp": mapped_ip
                    }
                }
            )
            
            return self.collection.find_one({"_id": file_id})
            
        except FileError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("MANUAL_MAP", str(e))
    
    # ========== SEARCH PIPELINES FOR MAPPING ==========
    def search_pipelines_for_mapping(
        self,
        operator_id: Optional[PyObjectId] = None,
        key_field_value: Optional[str] = None,
        service_id: Optional[PyObjectId] = None,
        fir_no: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search pipelines available for manual mapping."""
        try:
            pipeline_query = {
                "lineItemRequestStatus": "Approved",
                "isActive": True
            }
            
            if operator_id:
                pipeline_query["operatorId"] = operator_id
            if key_field_value:
                pipeline_query["keyFieldValue"] = key_field_value
            if service_id:
                pipeline_query["serviceId"] = service_id
            
            pipelines = list(self.pipeline_collection.find(pipeline_query).limit(50))
            
            results = []
            for pipeline in pipelines:
                request = self.request_collection.find_one({"_id": pipeline["crpcRequestId"]})
                
                if fir_no and request:
                    fir_numbers = [fir["firNo"] for fir in request.get("fir", [])]
                    if fir_no not in fir_numbers:
                        continue
                
                results.append({
                    "pipelineId": str(pipeline["_id"]),
                    "requestId": str(pipeline["crpcRequestId"]),
                    "operatorId": str(pipeline["operatorId"]),
                    "serviceId": str(pipeline["serviceId"]),
                    "keyFieldValue": pipeline["keyFieldValue"],
                    "firNo": request["fir"][0]["firNo"] if request and request.get("fir") else None,
                    "requestDate": request.get("requestDate") if request else None
                })
            
            return results
            
        except PyMongoError as e:
            raise DatabaseOperationError("SEARCH_PIPELINES", str(e))
    
    # ========== RETRY AUTO-MATCH ==========
    def retry_auto_match(
        self,
        file_id: PyObjectId,
        operator_id: PyObjectId,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> dict:
        """Retry auto-matching for unmatched file."""
        try:
            file = self.collection.find_one({"_id": file_id, "isActive": True})
            if not file:
                raise FileNotFoundError(str(file_id))
            
            if file["matchingStatus"] != MatchingStatus.UNMATCHED.value:
                raise ValueError("Can only retry auto-match for Unmatched files")
            
            key_value = file.get("extractedKeyFieldValue")
            if not key_value:
                raise ValueError("No key value extracted from filename")
            
            pipelines = self.find_matching_pipelines(operator_id, key_value)
            
            now = datetime.now(timezone.utc)
            
            if len(pipelines) == 0:
                return file
            elif len(pipelines) == 1:
                self.update_file_status(
                    file_id,
                    MatchingStatus.AUTO_MATCHED,
                    matched_pipeline_id=pipelines[0]["_id"],
                    updated_by=updated_by,
                    updated_ip=updated_ip
                )
                # Update pipeline
                self.pipeline_collection.update_one(
                    {"_id": pipelines[0]["_id"]},
                    {"$set": {"lineItemRequestStatus": "DataReceived", "updatedAt": now}}
                )
            else:
                self.update_file_status(
                    file_id,
                    MatchingStatus.CONFLICT,
                    conflict_pipeline_ids=[p["_id"] for p in pipelines],
                    updated_by=updated_by,
                    updated_ip=updated_ip
                )
            
            return self.collection.find_one({"_id": file_id})
            
        except FileError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("RETRY_MATCH", str(e))
    
    # ========== UNMAP FILE ==========
    def unmap_file(
        self,
        file_id: PyObjectId,
        updated_by: PyObjectId,
        updated_ip: str
    ) -> dict:
        """Unmap file from pipeline."""
        try:
            file = self.collection.find_one({"_id": file_id, "isActive": True})
            if not file:
                raise FileNotFoundError(str(file_id))
            
            if not file.get("matchedPipelineId"):
                raise ValueError("File is not mapped to any pipeline")
            
            now = datetime.now(timezone.utc)
            self.collection.update_one(
                {"_id": file_id},
                {
                    "$set": {
                        "matchingStatus": MatchingStatus.UNMATCHED.value,
                        "matchedPipelineId": None,
                        "manuallyMappedBy": None,
                        "manuallyMappedAt": None,
                        "updatedAt": now,
                        "updatedBy": updated_by,
                        "updatedIp": updated_ip
                    }
                }
            )
            
            return self.collection.find_one({"_id": file_id})
            
        except FileError:
            raise
        except PyMongoError as e:
            raise DatabaseOperationError("UNMAP", str(e))

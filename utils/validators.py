# 📁 utils/validators.py
from bson import ObjectId
from typing import Any
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """Custom Pydantic-compatible ObjectId type for MongoDB."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> core_schema.CoreSchema:
        """Define how Pydantic should validate this type."""
        return core_schema.union_schema(
            [
                # Validate from ObjectId instances
                core_schema.is_instance_schema(ObjectId),
                # Validate from strings
                core_schema.no_info_plain_validator_function(cls.validate),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
                when_used='json'
            ),
        )

    @classmethod
    def validate(cls, v: Any) -> ObjectId:
        """Validate and convert input to ObjectId."""
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return ObjectId(v)
            raise ValueError(f"Invalid ObjectId: {v}")
        raise TypeError(f"ObjectId expected, got {type(v).__name__}")

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """Define JSON schema for OpenAPI documentation."""
        return {
            'type': 'string',
            'pattern': '^[0-9a-fA-F]{24}$',
            'examples': ['507f1f77bcf86cd799439011']
        }


# For backward compatibility
class PyObjectIdValidator:
    """Legacy validator class with validate method."""
    
    @classmethod
    def validate(cls, v: Any) -> ObjectId:
        return PyObjectId.validate(v)

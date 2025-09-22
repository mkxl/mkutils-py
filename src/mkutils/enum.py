from enum import Enum as StdEnum
from typing import Any, Self, Union

import pydantic_core.core_schema
from pydantic import GetCoreSchemaHandler
from pydantic_core.core_schema import CoreSchema


# NOTE:
# - this class serializes as a string and deserializes from a string using
#   [enum_variant.string_repr() == str(enum_variant.value)]; this makes it compatible with typer which uses
#   [str(enum_variant.value)] to (1) render the enum variant in the [--help] documentation and (2) to deserialize cli
#   arguments back into the enum variant using a [str(enum_variant.value) -> enum_variant] dict (see
#   [generate_enum_convertor()] in [https://github.com/fastapi/typer/blob/master/typer/main.py])
class Enum(StdEnum):
    def string_repr(self) -> str:
        return str(self.value)

    @staticmethod
    def _validation_error(obj: Any) -> ValueError:
        return ValueError(f"no matching enum variant for {obj=!r}")

    @classmethod
    def _validate_from_str(cls, string_repr: str) -> Self:
        matching_enum_variant_iter = (enum_variant for enum_variant in cls if enum_variant.string_repr() == string_repr)

        match next(matching_enum_variant_iter, None):
            case None:
                raise cls._validation_error(string_repr)
            case matching_enum_variant:
                return matching_enum_variant

    @classmethod
    def _validator_fn(cls, obj: Union[str, Self]) -> Self:
        if isinstance(obj, cls):
            return obj

        if isinstance(obj, str):
            return cls._validate_from_str(obj)

        raise cls._validation_error(obj)

    # pylint: disable=line-too-long
    # NOTE:
    # - [__get_pydantic_core_schema__()] mentioned here with argument type annotations:
    #   - [https://docs.pydantic.dev/latest/concepts/types/#customizing-validation-with-__get_pydantic_core_schema__]
    #   - [https://docs.pydantic.dev/latest/concepts/serialization/#serializing-subclasses]
    # - [plain_serializer_function_ser_schema()] info:
    #   [https://docs.pydantic.dev/latest/api/pydantic_core_schema/#pydantic_core.core_schema.plain_serializer_function_ser_schema]
    # - [no_info_plain_validator_function()] argument type annotations:
    #   [https://docs.pydantic.dev/latest/api/pydantic_core_schema/#pydantic_core.core_schema.no_info_plain_validator_function]
    # - [NoInfoValidatorFunction, SerSchema] definitions:
    #   [https://github.com/pydantic/pydantic-core/blob/main/python/pydantic_core/core_schema.py]
    @classmethod
    def __get_pydantic_core_schema__(cls, _source: type[Any], _handler: GetCoreSchemaHandler) -> CoreSchema:
        expected = [enum_variant.string_repr() for enum_variant in cls]
        json_schema_input_schema = pydantic_core.core_schema.literal_schema(expected)
        serialization = pydantic_core.core_schema.plain_serializer_function_ser_schema(function=cls.string_repr)
        schema = pydantic_core.core_schema.no_info_plain_validator_function(
            function=cls._validator_fn, json_schema_input_schema=json_schema_input_schema, serialization=serialization
        )

        return schema

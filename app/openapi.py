"""Совместимость описания UploadFile с файловыми полями Swagger UI."""

from typing import Any

from fastapi import FastAPI


def _add_binary_format(value: Any) -> None:
    if isinstance(value, dict):
        if (value.get("type") == "string"
                and value.get("contentMediaType") == "application/octet-stream"):
            # FastAPI использует contentMediaType, а Swagger также нужен format.
            value["format"] = "binary"
        for child in value.values():
            _add_binary_format(child)
    elif isinstance(value, list):
        for child in value:
            _add_binary_format(child)


def configure_upload_schema(app: FastAPI) -> None:
    # Сохраняем штатный генератор и его кэширование, меняем только описание.
    generate_openapi = app.openapi

    def openapi_with_file_inputs() -> dict[str, Any]:
        schema = generate_openapi()
        _add_binary_format(schema)
        return schema

    app.openapi = openapi_with_file_inputs

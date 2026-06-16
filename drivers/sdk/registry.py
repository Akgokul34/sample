from typing import Dict, Type
from drivers.sdk.base import BaseDriver

_REGISTRY: Dict[str, Type[BaseDriver]] = {}

def register(vendor_key: str):
    def wrapper(cls: Type[BaseDriver]):
        _REGISTRY[vendor_key] = cls
        return cls
    return wrapper

def get_driver(vendor_key: str) -> Type[BaseDriver]:
    if vendor_key not in _REGISTRY:
        raise ValueError(f"No driver registered for vendor: {vendor_key}")
    return _REGISTRY[vendor_key]

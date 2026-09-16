"""
schemas.py - Pydantic request and response models for FastAPI API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OpModel(BaseModel):
    op_type: str = Field(..., description="'READ', 'WRITE', or 'SLEEP'")
    key: Optional[str] = None
    value: Optional[Any] = None
    duration: float = 0.0


class SubmitTxnRequest(BaseModel):
    operations: List[OpModel]
    txn_id: Optional[str] = None
    isolation_level: str = "SERIALIZABLE"
    max_retries: int = 3


class BatchTxnRequest(BaseModel):
    transactions: List[SubmitTxnRequest]


class ConfigRequest(BaseModel):
    protocol: Optional[str] = None  # "2PL", "TO", "OCC", "MVCC"
    deadlock_mode: Optional[str] = None  # "detection", "prevention"
    prevention_scheme: Optional[str] = None  # "wound_wait", "wait_die"
    victim_policy: Optional[str] = None  # "youngest", "fewest_locks"


class ResetRequest(BaseModel):
    initial_storage: Optional[Dict[str, Any]] = None


class SerializabilityRequest(BaseModel):
    schedule: str = Field(..., example="r1[x] w2[x] r1[y] w1[x] c1 c2")


class IsolationScenarioRequest(BaseModel):
    scenario: str = Field(..., example="dirty_read")  # "dirty_read", "non_repeatable_read", "lost_update", "phantom_read"
    isolation_level: str = Field("READ_COMMITTED", example="READ_COMMITTED")


class BenchmarkRequest(BaseModel):
    num_txns: int = 40
    contention: str = "high"
    write_ratio: float = 0.5

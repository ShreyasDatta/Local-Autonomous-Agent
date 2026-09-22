"""
E:\AI_Hub\agents\core\contracts.py
Pydantic Data Contracts for Multi-Agent Task Handoffs
"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class TaskHandoffPacket(BaseModel):
    task_id: str = Field(..., description="Unique UUID for tracing execution.")
    goal: str = Field(..., description="Unambiguous, single-sentence technical objective.")
    non_goals: List[str] = Field(default_factory=list, description="Explicit boundaries.")
    allowed_file_scope: List[str] = Field(..., description="Target file paths permitted for modification.")
    code_context: Dict[str, str] = Field(..., description="Map of file paths to code/header contents.")
    acceptance_criteria: List[str] = Field(..., description="Deterministic test/behavioral checks.")
    stop_conditions: List[str] = Field(default_factory=list, description="Triggers requiring immediate pause.")
    max_retries: int = Field(default=3, ge=1, le=5)

class TaskExecutionResult(BaseModel):
    task_id: str
    status: Literal["success", "refusal", "execution_error", "blocked"]
    modified_files: Dict[str, str] = Field(default_factory=dict, description="Updated file path to content map.")
    diff_summary: str = Field(..., description="Concise summary of changes made.")
    error_log: Optional[str] = None
    requires_human_escalation: bool = False
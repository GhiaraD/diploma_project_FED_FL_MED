"""
Audit logging helper functions for tracking user actions.
"""
from fastapi import Request
from sqlalchemy.orm import Session
from .security import security_manager
from typing import Optional, Dict, Any
import time
import asyncio


async def log_dataset_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log dataset-related actions."""
    event_data = {
        "action": action,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        **(details or {})
    }
    
    event_type = f"dataset_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )


async def log_model_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    model_id: Optional[str] = None,
    model_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log model-related actions."""
    event_data = {
        "action": action,
        "model_id": model_id,
        "model_name": model_name,
        **(details or {})
    }
    
    event_type = f"model_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )


async def log_inference_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    job_id: Optional[str] = None,
    num_images: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log inference-related actions."""
    event_data = {
        "action": action,
        "job_id": job_id,
        "num_images": num_images,
        **(details or {})
    }
    
    event_type = f"inference_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )


async def log_training_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    job_id: Optional[str] = None,
    model_name: Optional[str] = None,
    training_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log training-related actions."""
    event_data = {
        "action": action,
        "job_id": job_id,
        "model_name": model_name,
        "training_type": training_type,
        **(details or {})
    }
    
    event_type = f"training_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )


async def log_federated_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log federated learning actions."""
    event_data = {
        "action": action,
        "session_id": session_id,
        **(details or {})
    }
    
    event_type = f"federated_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )


async def log_job_action(
    action: str,
    user_id: str,
    request: Request,
    db: Session,
    job_id: Optional[str] = None,
    job_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    response_status: int = 200,
    start_time: Optional[float] = None
):
    """Log job-related actions."""
    event_data = {
        "action": action,
        "job_id": job_id,
        "job_type": job_type,
        **(details or {})
    }
    
    event_type = f"job_{action}"
    await security_manager.log_audit_event(
        event_type=event_type,
        user_id=user_id,
        request=request,
        additional_data=event_data,
        db=db,
        response_status=response_status,
        start_time=start_time
    )

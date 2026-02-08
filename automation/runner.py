import logging
from .models import Workflow, TaskLog
from .services import TASK_REGISTRY
import time
import datetime
from django.utils import timezone

logger = logging.getLogger('automation')

def execute_workflow(workflow_id):
    """
    Executes all steps of a given workflow in order.
    """
    try:
        workflow = Workflow.objects.get(pk=workflow_id)
        steps = workflow.steps.all().order_by('order')
        
        logger.info(f"Executing Workflow: {workflow.name}")
        
        execution_start = time.time()
        workflow_log_entries = []
        
        workflow.last_run = timezone.now()
        workflow.save()

        success_overall = True
        
        for step in steps:
            task_key = step.task.name  # Use name (key) instead of full path
            task_func = TASK_REGISTRY.get(task_key)
            
            log = TaskLog(
                workflow=workflow,
                task_name=step.task.name,
                status='RUNNING'
            )
            log.save()
            
            task_start = time.time()
            
            if not task_func:
                log.status = 'FAILED'
                log.output = f"Task function '{task_key}' not found in registry."
                log.duration_seconds = time.time() - task_start
                log.save()
                success_overall = False
                break 
            
            try:
                # Execute Task
                logger.info(f"Running Task: {step.task.name}")
                status, output = task_func() # Expecting (bool, str)
                
                log.status = 'SUCCESS' if status else 'FAILED'
                log.output = str(output)
                
                if not status:
                    success_overall = False
                    logger.error(f"Task Failed: {step.task.name}")
                    break 
                    
            except Exception as e:
                log.status = 'FAILED'
                log.output = f"Exception: {str(e)}"
                success_overall = False
                logger.error(f"Task Exception: {e}")
                break
            finally:
                log.duration_seconds = time.time() - task_start
                log.save()
        
        # Schedule Next Run
        if workflow.interval_minutes > 0:
            workflow.next_run = workflow.last_run + datetime.timedelta(minutes=workflow.interval_minutes)
            workflow.save()
            
        logger.info(f"Workflow '{workflow.name}' Completed. Success: {success_overall}")
        return success_overall

    except Workflow.DoesNotExist:
        logger.error(f"Workflow {workflow_id} not found.")
        return False

def execute_single_task(task_id):
    """
    Executes a single task immediately, logging the result.
    """
    from .models import Task
    try:
        task_model = Task.objects.get(pk=task_id)
        task_key = task_model.name
        task_func = TASK_REGISTRY.get(task_key)
        
        logger.info(f"Executing Single Task: {task_key}")
        
        task_start = time.time()
        
        log = TaskLog(
            workflow=None, # Standalone execution
            task_name=task_model.name,
            status='RUNNING'
        )
        log.save()
        
        if not task_func:
            log.status = 'FAILED'
            log.output = f"Task function '{task_key}' not found in registry."
            log.duration_seconds = time.time() - task_start
            log.save()
            logger.error(f"Task function not found in registry: {task_key}")
            return False
            
        try:
            status, output = task_func()
            
            log.status = 'SUCCESS' if status else 'FAILED'
            log.output = str(output)
            log.duration_seconds = time.time() - task_start
            log.save()
            
            if status:
                logger.info(f"Task {task_key} SUCCESS. Output len: {len(str(output))}")
            else:
                logger.warning(f"Task {task_key} FAILED. Output: {output}")
            
            return status
            
        except Exception as e:
            log.status = 'FAILED'
            log.output = f"Exception: {str(e)}"
            log.duration_seconds = time.time() - task_start
            log.save()
            logger.exception(f"Task Exception in execute_single_task: {e}")
            return False
            
    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found.")
        return False

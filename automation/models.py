from django.db import models
from django.utils import timezone

class Task(models.Model):
    """
    Represents a specific python function or command that can be executed.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    function_path = models.CharField(max_length=255, help_text="Python path to function, e.g. 'automation.tasks.scrape_bulletin'")
    code_snippet = models.TextField(blank=True, help_text="Actual source code of the function")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Workflow(models.Model):
    """
    A sequence of tasks to be executed in order.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    interval_minutes = models.IntegerField(default=60, help_text="Execution interval in minutes")
    is_active = models.BooleanField(default=False)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class WorkflowStep(models.Model):
    """
    Links a Task to a Workflow at a specific position.
    """
    workflow = models.ForeignKey(Workflow, related_name='steps', on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.order}. {self.task.name} ({self.workflow.name})"

class TaskLog(models.Model):
    """
    Log of task execution.
    """
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, null=True, blank=True)
    task_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20) # SUCCESS, FAILED, RUNNING
    output = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.created_at} - {self.task_name} - {self.status}"

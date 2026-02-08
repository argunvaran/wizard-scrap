from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Workflow, Task, WorkflowStep, TaskLog
from .runner import execute_workflow, execute_single_task

from .services import TASK_REGISTRY
import threading
import logging
from django.db import connection

logger = logging.getLogger('automation')


def dashboard(request):
    """
    Main Data Control Center Dashboard.
    Groups tasks by country and displays status.
    """
    try:
        workflows = Workflow.objects.filter(is_active=True)
        recent_logs = TaskLog.objects.all().order_by('-created_at')[:10]
        
        # Organize Sync Tasks by Country
        countries = ['Turkey', 'England', 'Spain', 'Italy']
        data_tasks = {}
        
        for country in countries:
            c_lower = country.lower()
            # Find tasks by name convention defined in registry
            # We need to ensure tasks are synced first (sync_tasks run at least once)
            t_standings = Task.objects.filter(name=f'sync_{c_lower}_standings').first()
            t_fixtures = Task.objects.filter(name=f'sync_{c_lower}_fixtures').first()
            t_squads = Task.objects.filter(name=f'sync_{c_lower}_squads').first()
            
            data_tasks[country] = {
                'standings': t_standings,
                'fixtures': t_fixtures,
                'squads': t_squads,
            }
            
        return render(request, 'automation/dashboard.html', {
            'workflows': workflows,
            'recent_logs': recent_logs,
            'data_tasks': data_tasks,
            'show_update_button': request.user.is_superuser
        })
    except Exception as e:
        logger.exception(f"CRITICAL DASHBOARD ERROR: {e}")
        from django.http import HttpResponse
        return HttpResponse(f"<h1>Dashboard Error</h1><pre>{str(e)}</pre>", status=500)

def task_run_direct(request, pk):
    """
    Manually triggers single task execution (background thread).
    """
    task = get_object_or_404(Task, pk=pk)
    
    def run_thread():
        # Ensure DB connection is clean for thread
        connection.close()
        execute_single_task(pk)
        connection.close()
        
    t = threading.Thread(target=run_thread)
    t.start()
    
    messages.info(request, f"Görev '{task.name}' arkaplanda başlatıldı.")
    return redirect('task_list')

def task_list(request):
    """
    Shows all available tasks (defined in services.py).
    """
    tasks = Task.objects.all().order_by('name')
    return render(request, 'automation/task_list.html', {'tasks': tasks})

from .services import TASK_REGISTRY
import threading
from django.db import connection

def sync_tasks(request):
    """
    Syncs available tasks from services.py to Database.
    """
    import inspect
    
    # Clear existing tasks and workflows to reset
    Task.objects.all().delete()
    Workflow.objects.all().delete()

    created_count = 0
    for task_key, task_func in TASK_REGISTRY.items():
        # Get Description from Docstring
        doc = inspect.getdoc(task_func) or "No description provided."
        
        # Get Source Code
        try:
            source = inspect.getsource(task_func)
        except Exception:
            source = "# Source not available"
            
        obj = Task.objects.create(
            name=task_key,
            description=doc,
            function_path=f"automation.services.{task_key}",
            code_snippet=source
        )
        created_count += 1
    messages.success(request, f"Tüm görevler sıfırlandı ve yeniden yüklendi. {created_count} görev aktif.")
    return redirect('workflow_list')

def workflow_list(request):
    workflows = Workflow.objects.all().order_by('name')
    return render(request, 'automation/workflow_list.html', {'workflows': workflows})

def workflow_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        desc = request.POST.get('description')
        interval = request.POST.get('interval', 60)
        is_active = request.POST.get('is_active') == 'on'
        selected_task_ids = request.POST.getlist('tasks')
        
        wf = Workflow.objects.create(name=name, description=desc, interval_minutes=int(interval), is_active=is_active)
        
        # Add tasks in order
        for idx, t_id in enumerate(selected_task_ids, start=1):
            task = Task.objects.get(pk=t_id)
            WorkflowStep.objects.create(workflow=wf, task=task, order=idx)
            
        messages.success(request, f"Akış '{name}' oluşturuldu ve {len(selected_task_ids)} görev eklendi.")
        return redirect('workflow_detail', pk=wf.pk)
        
    available_tasks = Task.objects.all().order_by('name')
    return render(request, 'automation/workflow_form.html', {'available_tasks': available_tasks})

def workflow_detail(request, pk):
    workflow = get_object_or_404(Workflow, pk=pk)
    available_tasks = Task.objects.all().order_by('name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_task':
            task_id = request.POST.get('task_id')
            order = request.POST.get('order', 1)
            task = get_object_or_404(Task, pk=task_id)
            WorkflowStep.objects.create(workflow=workflow, task=task, order=int(order))
            messages.success(request, f"Task '{task.name}' eklendi.")
            
        elif action == 'remove_task':
            step_id = request.POST.get('step_id')
            WorkflowStep.objects.filter(pk=step_id).delete()
            messages.success(request, "Task silindi.")
            
        elif action == 'update_settings':
            workflow.name = request.POST.get('name')
            workflow.description = request.POST.get('description')
            workflow.interval_minutes = int(request.POST.get('interval', 60))
            workflow.is_active = request.POST.get('is_active') == 'on'
            workflow.save()
            messages.success(request, "Ayarlar güncellendi.")
            
        return redirect('workflow_detail', pk=pk)
        
    return render(request, 'automation/workflow_detail.html', {
        'workflow': workflow,
        'available_tasks': available_tasks
    })

def workflow_delete(request, pk):
    """
    Deletes a workflow and redirects to list.
    """
    workflow = get_object_or_404(Workflow, pk=pk)
    if request.method == 'POST':
        workflow.delete()
        messages.success(request, f"Akış '{workflow.name}' silindi.")
        return redirect('workflow_list')
    
    return render(request, 'automation/workflow_confirm_delete.html', {'workflow': workflow})

def workflow_run(request, pk):
    """
    Manually triggers workflow execution (background thread).
    """
    workflow = get_object_or_404(Workflow, pk=pk)
    
    def run_thread():
        # Ensure DB connection is clean for thread
        connection.close()
        execute_workflow(pk)
        connection.close()
        
    t = threading.Thread(target=run_thread)
    t.start()
    
    messages.info(request, f"Worflow '{workflow.name}' arkaplanda başlatıldı.")
    return redirect('workflow_list')

def task_log_list(request):
    logs = TaskLog.objects.all().order_by('-created_at')[:100]
    return render(request, 'automation/log_list.html', {'logs': logs})




def sync_tasks(request):
    """
    Syncs the TASK_REGISTRY with the Database Task models.
    """
    created_count = 0
    updated_count = 0
    
    for task_name, task_func in TASK_REGISTRY.items():
        task, created = Task.objects.get_or_create(
            name=task_name,
            defaults={'description': f"Auto-generated task: {task_name}"}
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
            
    messages.success(request, f"Tasks Synced: {created_count} Created, {updated_count} Updated.")
    return redirect('automation_dashboard')

# --- INTERACTIVE DATA FLOW VIEWS ---


from .scraper_tasks import (
    fetch_standings, fetch_fixtures, fetch_squads,
    save_standings, save_fixtures, save_squads
)

def fetch_data_view(request, country, data_type):
    """
    Triggers the scraper and stages data for preview.
    """
    country = country.lower()
    data_type = data_type.lower()
    
    # Map to fetch function
    data = []
    
    # Extract optional params
    season = request.GET.get('season')
    url = request.GET.get('url') # Allow full URL override
    
    kwargs = {}
    if season: kwargs['season'] = season
    if url: kwargs['url'] = url

    try:
        if data_type == 'squads':
            # SQUADS: Run in Background (Too slow for sync HTTP -> 504 Timeout)
            task_name = f"sync_{country}_squads"
            task = Task.objects.filter(name=task_name).first()
            
            # Auto-heal: If task missing from DB but exists in Code Registry, create it.
            # TASK_REGISTRY is imported at top level now
            if not task and task_name in TASK_REGISTRY:
                try:
                    task = Task.objects.create(
                        name=task_name,
                        description=f"Auto-generated task for {country} squads",
                        function_path=f"automation.services.{task_name}"
                    )
                except Exception as e:
                    logger.error(f"Error auto-creating task {task_name}: {e}")

            if task:
                def run_thread():
                    logger_t = logging.getLogger('automation')
                    logger_t.info(f"THREAD STARTED: {task_name} (ID: {task.pk})")
                    connection.close()  # Ensure clean DB connection
                    # We use a fresh thread execution
                    try:
                        execute_single_task(task.pk)
                        logger_t.info(f"THREAD COMPLETED: {task_name}")
                    except Exception as e:
                        logger_t.error(f"Thread execution failed for {task_name}: {e}")
                    finally:
                        connection.close()
                
                t = threading.Thread(target=run_thread)
                t.start()
                logger.info(f"Spawned background thread for {task_name}")
                
                messages.success(request, f"{country.title()} Squads scraping started in BACKGROUND. Check logs for progress.")
                return redirect('automation_dashboard')
            else:
                messages.error(request, f"Background task '{task_name}' could not be initialized. Please check code registry.")
                return redirect('automation_dashboard')

        # STANDINGS / FIXTURES: Keep Synchronous (Fast enough for Preview)
        elif data_type == 'standings':
            data = fetch_standings(country, **kwargs)
        elif data_type == 'fixtures':
            data = fetch_fixtures(country, **kwargs)
        else:
            messages.error(request, f"Bilinmeyen veri tipi: {data_type}")
            return redirect('automation_dashboard')
            
        if not data:
            messages.error(request, f"{country.title()} {data_type} verisi çekilemedi veya boş döndü.")
            return redirect('automation_dashboard')
            
        # Stage data in Session
        request.session['staged_data'] = data
        request.session['staged_country'] = country
        request.session['staged_type'] = data_type
        
        return redirect('data_preview_view')

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL VIEW ERROR: {e}")
        messages.error(request, f"Sistem Hatası: {str(e)}")
        return redirect('automation_dashboard')

def data_preview_view(request):
    """
    Displays the staged data for user confirmation.
    """
    data = request.session.get('staged_data')
    country = request.session.get('staged_country')
    data_type = request.session.get('staged_type')
    
    if not data:
        messages.warning(request, "Önizlenecek veri bulunamadı.")
        return redirect('automation_dashboard')
        
    return render(request, 'automation/data_preview.html', {
        'data': data,
        'country': country,
        'data_type': data_type,
        'count': len(data)
    })

def data_commit_view(request):
    """
    Saves the staged data to the Data Manager DB.
    """
    if request.method != 'POST':
        return redirect('automation_dashboard')
        
    data = request.session.get('staged_data')
    country = request.session.get('staged_country')
    data_type = request.session.get('staged_type')
    
    if not data:
        messages.error(request, "Kaydedilecek veri bulunamadı/oturum süresi dolmuş.")
        return redirect('automation_dashboard')
        
    # Save Logic
    success, msg = False, "Unknown Error"
    
    if data_type == 'standings':
        success, msg = save_standings(country, data)
    elif data_type == 'fixtures':
        success, msg = save_fixtures(country, data)
    elif data_type == 'squads':
        success, msg = save_squads(country, data)
        
    if success:
        messages.success(request, f"BAŞARILI: {msg}")
        # Clear session
        del request.session['staged_data']
        del request.session['staged_country']
        del request.session['staged_type']
    else:
        messages.error(request, f"HATA: {msg}")
        
    return redirect('automation_dashboard')

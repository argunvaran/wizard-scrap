from django.core.management.base import BaseCommand
from automation.models import Workflow
from automation.runner import execute_workflow
from django.utils import timezone
import time
from django.db import connection

class Command(BaseCommand):
    help = 'Runs the automation scheduler loop'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('SCHEDULER BAŞLATILDI... (Durdurmak için Ctrl+C)'))
        
        while True:
            try:
                # Close old connections to avoid timeout in long loop
                connection.close()
                
                now = timezone.now()
                # Find due workflows
                due_workflows = Workflow.objects.filter(is_active=True, next_run__lte=now)
                
                if due_workflows.exists():
                    self.stdout.write(f"--- Kontrol Zamanı: {now.strftime('%H:%M:%S')} ---")
                
                for wf in due_workflows:
                    self.stdout.write(self.style.WARNING(f"ÇALIŞTIRILIYOR: {wf.name} (ID: {wf.id})"))
                    
                    success = execute_workflow(wf.id)
                    
                    if success:
                        self.stdout.write(self.style.SUCCESS(f"TAMAMLANDI: {wf.name}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"HATA: {wf.name} başarısız oldu."))
                
                # Sleep 10 seconds
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Scheduler durduruluyor...'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"SCHEDULER HATASI: {e}"))
                time.sleep(5)

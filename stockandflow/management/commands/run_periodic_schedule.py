from django.core.management.base import NoArgsCommand
import stockandflow

class Command(NoArgsCommand):
    args = ""
    help = "Run the periodic schedule entries. This should be called from cron at an interval that equals the shortest period length."
    
    def handle_noargs(self, *args, **options):
        stockandflow.periodic.schedule.run()

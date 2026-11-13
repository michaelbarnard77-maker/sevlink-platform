from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MaintenanceRequest


@receiver(post_save,sender=MaintenanceRequest,dispatch_uid='private-client-closed-access')
def closed_job(sender,instance,**kwargs):
    if instance.private_client_id and (instance.closed_at or instance.status in ('closed','cancelled')):
        from .private_clients import sync_closed_access
        sync_closed_access(instance)

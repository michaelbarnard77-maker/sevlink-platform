"""Calendar attendance and the parent job share one committed progress state."""
import uuid
from django.utils import timezone
from .models import TeamAppointment, AttendanceRequest, WorkflowDecision, MaintenanceStatusEvent, Audit


def progress_plan(job, action):
    from .workflow import assessment_ids
    if job.closed_at or job.status in ('closed','cancelled'):
        return job.status, False
    assessments = assessment_ids(job)
    assessment_appointments = AttendanceRequest.objects.filter(request=job,pk__in=assessments,appointment__isnull=False).values('appointment_id')
    visits = TeamAppointment.objects.filter(assignment__request=job,cancelled_at=None)
    work = visits.exclude(pk__in=assessment_appointments)
    assessment_only = not work.exists() and visits.exists()
    active = visits if assessment_only else work
    states = list(active.values_list('progress_status',flat=True))
    assessment_done = bool(assessment_only and states and all(s=='completed' for s in states))
    last = job.workflow_decisions.filter(operation='operations-triage').order_by('-created_at','-pk').first()
    close_assessment = bool(assessment_done and not job.quotations.exists() and last and last.snapshot.get('decision')=='attendance')
    if job.status=='completed':
        return job.status, False
    if 'on_site' in states:
        return 'on_site', False
    if states and all(s=='completed' for s in states) and action=='completed':
        return ('reviewed' if assessment_only else 'completed'), close_assessment
    if 'completed' in states:
        return ('reviewed' if assessment_done else 'in_progress'), close_assessment
    if 'booked' in states:
        return 'scheduled', False
    return 'reviewed', False


def sync_job(job, actor, action, *, key=None):
    """Caller holds the property and job locks in its existing transaction."""
    from .events import record
    previous=job.status
    status, assessment_done=progress_plan(job,action)
    if status==previous and not assessment_done:
        return False
    key=key or uuid.uuid4()
    if assessment_done:
        WorkflowDecision.objects.create(request=job,actor=actor,operation='operations-triage',
            key=uuid.uuid5(key,'assessment-complete'),fingerprint='calendar-assessment-complete',
            snapshot={'decision':'desktop','source':'calendar','assessment_completed':True})
    job.status=status;job.version+=1
    job.save(update_fields=['status','version','updated_at'])
    MaintenanceStatusEvent.objects.create(request=job,actor=actor,status=status)
    label='Assessment completed — quote to upload' if assessment_done else 'Job progress updated from calendar'
    record(job,actor,'job_completed' if status=='completed' else 'status_changed',
        'calendar-job:'+str(key),{'status':status})
    Audit.objects.create(agency=job.property.agency,actor=actor,action=label+': '+previous+' → '+status,object_id=str(job.pk))
    if status=='completed':
        # Physical completion is recorded immediately; documents and final payment
        # still gate the completion package and financial closure.
        from .completion_delivery import maybe_queue
        from .workflow import after_payment
        after_payment(job,actor)
        maybe_queue(job,actor)
    return True

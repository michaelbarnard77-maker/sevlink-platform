import uuid
from django.db import migrations


def preserve(apps, schema_editor):
    Quote = apps.get_model('portal', 'JobQuotation')
    Line = apps.get_model('portal', 'QuotationLine')
    Action = apps.get_model('portal', 'QuotationAction')
    for quote in Quote.objects.all().iterator():
        line = dict(position=1, description=quote.title, quantity='1.000', unit='job',
                    unit_price=str(quote.amount), net=str(quote.amount), vat='0.00', total=str(quote.amount))
        Line.objects.create(quote=quote, **line)
        snapshot = dict(title=quote.title, scope=quote.scope, currency='ZAR', tax_treatment='none',
                        vat_rate='0.000000', subtotal=str(quote.amount), vat_total='0.00', amount=str(quote.amount), lines=[line])
        Quote.objects.filter(pk=quote.pk).update(public_snapshot=snapshot)
        if quote.decided_by_id:
            Action.objects.create(quote=quote, actor_id=quote.decided_by_id, kind=quote.status,
                key=quote.decision_key or uuid.uuid4(), fingerprint='', reason=quote.decision_reason,
                snapshot=snapshot, created_at=quote.decided_at or quote.created_at)
    Inbox = apps.get_model('portal', 'OperationsInboxItem')
    Notice = apps.get_model('portal', 'OperationsNotification')
    for notice in Notice.objects.select_related('event').all().iterator():
        Inbox.objects.get_or_create(event_id=notice.event_id, defaults={'created_at': notice.event.created_at})


class Migration(migrations.Migration):
    dependencies = [('portal', '0007_operationsinboxitem_operationsinboxreceipt_and_more')]
    operations = [migrations.RunPython(preserve, migrations.RunPython.noop)]

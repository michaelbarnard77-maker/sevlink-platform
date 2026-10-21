"""Trusted administrator recovery only; no public recovery endpoint."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice
from portal.models import User, PrivilegedSecurityEvent


class Command(BaseCommand):
    help='Reset one staff authenticator after independently verified recovery; invalidates all existing sessions.'

    def add_arguments(self,parser):
        parser.add_argument('user_id',type=int)
        parser.add_argument('--actor',type=int,required=True)
        parser.add_argument('--reason',required=True)
        parser.add_argument('--confirmed-identity',action='store_true')

    def handle(self,*args,**options):
        if not options['confirmed_identity'] or not 1<=len(options['reason'].strip())<=500:
            raise CommandError('Independent identity verification and a reviewed reason are required.')
        with transaction.atomic():
            actor=User.objects.filter(pk=options['actor'],is_active=True,is_superuser=True).first()
            target=User.objects.select_for_update().filter(pk=options['user_id'],is_active=True,is_staff=True).first()
            if not actor or not target or actor.pk==target.pk:
                raise CommandError('A separate active Super Admin and an active staff target are required.')
            TOTPDevice.objects.filter(user=target).delete()
            target.session_version+=1;target.save(update_fields=['session_version'])
            PrivilegedSecurityEvent.objects.create(user=target,action=f'MFA recovery by administrator {actor.pk}')
            StaffMFARecovery.objects.create(user=target,actor=actor,reason=options['reason'].strip())
        self.stdout.write('Authenticator reset; prior sessions revoked. Require immediate re-enrollment.')


from portal.models import StaffMFARecovery

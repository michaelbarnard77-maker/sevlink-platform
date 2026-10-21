"""Trusted staff offboarding without changing any agency's business history."""
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from portal.models import User, Membership, PrivilegedSecurityEvent


class Command(BaseCommand):
    help='Deactivate a separately authorised Sevlink staff account and revoke all roles/sessions; retain history.'

    def add_arguments(self,parser):
        parser.add_argument('user_id',type=int)
        parser.add_argument('--actor',type=int,required=True)
        parser.add_argument('--reason-reference',required=True)
        parser.add_argument('--confirmed-offboarding',action='store_true')

    def handle(self,*args,**options):
        reference=options['reason_reference']
        if not options['confirmed_offboarding'] or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',reference):
            raise CommandError('Confirmed offboarding and a private reviewed ticket reference are required.')
        with transaction.atomic():
            actor=User.objects.filter(pk=options['actor'],is_active=True,is_superuser=True).first()
            target=User.objects.select_for_update().filter(Q(is_staff=True)|Q(is_superuser=True),pk=options['user_id']).first()
            if not actor or not target or actor.pk==target.pk or Membership.objects.filter(user=target).exists():
                raise CommandError('A separate active Super Admin and a Sevlink staff target without agency membership are required.')
            target.is_active=False;target.is_staff=False;target.is_superuser=False;target.session_version+=1
            target.save(update_fields=['is_active','is_staff','is_superuser','session_version'])
            target.groups.clear();target.user_permissions.clear()
            PrivilegedSecurityEvent.objects.create(user=target,action=f'Staff offboarded by {actor.pk}; reference {reference}')
        self.stdout.write('Staff access, roles and prior sessions revoked; historical records retained.')

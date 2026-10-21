from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from portal.upload_scanning import scan, ScanUnavailable


class Command(BaseCommand):
    help='Local scanner integration probe: clean bytes must pass and harmless EICAR test bytes must fail.'

    def handle(self,*args,**options):
        if not settings.UPLOAD_SCAN_REQUIRED:
            raise CommandError('Enable scanning explicitly for this local integration probe.')
        try:
            scan(b'Sevlink clean synthetic scanner probe\n')
        except ScanUnavailable:
            raise CommandError('Scanner failed the clean-file probe.') from None
        eicar=(b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*')
        try:
            scan(eicar)
        except ScanUnavailable:
            self.stdout.write('Clean probe accepted; EICAR probe rejected. Verify engine logs/signature freshness separately.')
        else:
            raise CommandError('Scanner accepted EICAR; do not release uploads.')

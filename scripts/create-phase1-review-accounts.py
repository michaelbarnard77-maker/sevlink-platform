"""Run using manage.py shell; create local SQLite review accounts, never production data."""
from getpass import getpass

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from portal.models import Agency, Membership, Property, Tenancy, User


def main():
    db = settings.DATABASES['default']
    if not settings.DEBUG or db['ENGINE'] != 'django.db.backends.sqlite3':
        raise SystemExit('Refusing: this helper requires DEBUG=1 and local SQLite. No records created.')
    if settings.SMTP_DELIVERY_ENABLED:
        raise SystemExit('Disable SMTP_DELIVERY_ENABLED before creating review accounts.')
    accounts = [
        ('tenant-a@review.example.test', 'Review Tenant A', 'tenant', 'A'),
        ('pm-a@review.example.test', 'Review PM A', 'pm', 'A'),
        ('tenant-b@review.example.test', 'Review Tenant B', 'tenant', 'B'),
        ('pm-b@review.example.test', 'Review PM B', 'pm', 'B'),
        ('superadmin@review.example.test', 'Review Super Admin', None, None),
    ]
    if User.objects.filter(email__in=[a[0] for a in accounts]).exists():
        raise SystemExit('Review accounts already exist. No passwords or records were changed. Use your existing passwords.')
    credentials = {}
    for email, name, role, agency in accounts:
        while True:
            password = getpass(f'Choose a password for {email}: ')
            if password != getpass('Confirm password: '):
                print('Passwords do not match. Try again.')
                continue
            try:
                validate_password(password, User(username=email, email=email, first_name=name))
            except ValidationError as error:
                print(' '.join(error.messages))
                continue
            credentials[email] = password
            break
    with transaction.atomic():
        agencies = {key: Agency.objects.create(name=f'LOCAL REVIEW Agency {key}', phone='Test only', area='Test only')
                    for key in ['A', 'B']}
        users = {}
        for email, name, role, key in accounts:
            users[email] = User.objects.create_user(username=email, email=email, first_name=name,
                password=credentials[email], is_active=True, is_staff=role is None, is_superuser=role is None)
            if role:
                Membership.objects.create(user=users[email], agency=agencies[key], role=role)
        for key in ['A', 'B']:
            tenant = users[f'tenant-{key.lower()}@review.example.test']
            prop = Property.objects.create(agency=agencies[key], manager=users[f'pm-{key.lower()}@review.example.test'],
                name=f'LOCAL REVIEW Home {key}', address=f'Example property {key}', access_notes='LOCAL PRIVATE ACCESS TEST')
            Tenancy.objects.create(property=prop, user=tenant, name=tenant.first_name, email=tenant.email, phone='Test only')
    credentials.clear()
    print('Created five separate local review accounts, two agencies and two linked properties. No emails sent.')
    print('Login at http://127.0.0.1:8000/login/ using the email addresses above and your chosen passwords.')
    print('Open http://127.0.0.1:8000/maintenance/ after login. Do not use the static demo for this test.')


main()

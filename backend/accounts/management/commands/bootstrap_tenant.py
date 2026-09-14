from getpass import getpass

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from organizations.models import Agency, AgencySettings
from reference.models import AgencyCurrency, Currency


class Command(BaseCommand):
    help = "Create the first agency and its owner account"

    def add_arguments(self, parser):
        parser.add_argument("--agency-name", required=True)
        parser.add_argument("--agency-slug", required=True)
        parser.add_argument("--email", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if Agency.objects.filter(slug=options["agency_slug"]).exists():
            raise CommandError("An agency with this slug already exists.")
        if User.objects.filter(email__iexact=options["email"]).exists():
            raise CommandError("A user with this email already exists.")

        password = getpass("Owner password: ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            raise CommandError("Passwords do not match.")
        if len(password) < 10:
            raise CommandError("The password must contain at least 10 characters.")

        agency = Agency.objects.create(name=options["agency_name"], slug=options["agency_slug"])
        AgencySettings.objects.create(agency=agency)
        for currency in Currency.objects.filter(code__in=["DZD", "EUR", "SAR", "USD"]):
            AgencyCurrency.objects.create(
                agency=agency,
                currency=currency,
                is_enabled=True,
                is_accounting=currency.code == "DZD",
            )
        owner_role = Role.objects.create(
            agency=agency,
            name="Agency Owner",
            code="agency-owner",
            description="Full administration within this agency.",
        )
        owner_role.permissions.set(
            Permission.objects.filter(content_type__app_label__in=["accounts", "organizations"])
        )
        owner = User.objects.create_user(
            email=options["email"], password=password, agency=agency, is_staff=True
        )
        owner.roles.add(owner_role)
        self.stdout.write(
            self.style.SUCCESS(f"Created agency '{agency.name}' and owner {owner.email}.")
        )

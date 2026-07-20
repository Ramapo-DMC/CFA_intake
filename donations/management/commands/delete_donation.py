"""
Delete donation(s) by their assigned donation number (the "cc#").

Usage:
    python manage.py delete_donation 57
    python manage.py delete_donation 57 --yes          # skip confirmation
    python manage.py delete_donation 57 --pk 110       # pick one when several share the cc#
    python manage.py delete_donation 57 --all --yes    # delete every match

Note: the donation number cycles 1-500 and is reused, so a single cc# can
match more than one donation. When that happens this command refuses to guess
- it lists the matches and asks you to narrow with --pk or confirm with --all.
"""

from django.core.management.base import BaseCommand, CommandError

from donations.models import Donation


def _describe(d: Donation) -> str:
    donor = d.donor_name or "(no name)"
    site = d.site.name if d.site_id else "(no site)"
    return (
        f"  pk={d.pk} | cc#{d.cdonation_number} | {d.donation_date} | "
        f"{donor} | site={site} | email={d.email or '-'}"
    )


class Command(BaseCommand):
    help = "Delete donation(s) by their assigned donation number (cc#)."

    def add_arguments(self, parser):
        parser.add_argument(
            "cc_number",
            type=int,
            help="The donation number (cc#) assigned to the donation.",
        )
        parser.add_argument(
            "--pk",
            type=int,
            default=None,
            help="When several donations share the cc#, delete only this record's primary key.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Delete every donation matching the cc# (use when the number was reused).",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )

    def handle(self, *args, **options):
        cc_number = options["cc_number"]
        pick_pk = options["pk"]
        delete_all = options["all"]
        assume_yes = options["yes"]

        matches = list(
            Donation.objects.filter(cdonation_number=cc_number).order_by(
                "-donation_date", "-created_at"
            )
        )

        if not matches:
            raise CommandError(f"No donation found with donation number (cc#) {cc_number}.")

        # Resolve which donations to delete.
        if pick_pk is not None:
            targets = [d for d in matches if d.pk == pick_pk]
            if not targets:
                raise CommandError(
                    f"No donation with pk={pick_pk} has cc#{cc_number}. "
                    f"Matches for cc#{cc_number} are:\n"
                    + "\n".join(_describe(d) for d in matches)
                )
        elif len(matches) == 1:
            targets = matches
        elif delete_all:
            targets = matches
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(matches)} donations share cc#{cc_number} "
                    f"(the number is reused every 500 donations):"
                )
            )
            for d in matches:
                self.stdout.write(_describe(d))
            raise CommandError(
                "Refusing to guess. Re-run with --pk <primary key> to delete one, "
                "or --all to delete every match."
            )

        # Show what will be deleted.
        self.stdout.write(
            f"About to delete {len(targets)} donation(s) with cc#{cc_number}:"
        )
        for d in targets:
            self.stdout.write(_describe(d))

        # Confirm.
        if not assume_yes:
            answer = input("Type 'yes' to permanently delete: ").strip().lower()
            if answer != "yes":
                self.stdout.write(self.style.NOTICE("Aborted. Nothing was deleted."))
                return

        deleted_pks = [d.pk for d in targets]
        count, _ = Donation.objects.filter(pk__in=deleted_pks).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {len(deleted_pks)} donation(s) with cc#{cc_number} "
                f"(pks: {', '.join(str(pk) for pk in deleted_pks)})."
            )
        )

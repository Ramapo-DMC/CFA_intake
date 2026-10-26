"""
List sites and control who can manage them in the Django admin (/admin/).

Usage:
    python manage.py site_managers                  # list sites and current managers
    python manage.py site_managers --grant alice    # let alice view/add/change every site
    python manage.py site_managers --revoke alice   # take that away again

Django permissions apply to the Site model as a whole, so a site manager can
manage every site, not a chosen few. Granting also turns on "staff status",
without which the user cannot log in to /admin/ at all. Delete is
deliberately not granted: retire a site by unchecking "Is active" instead.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from donations.models import Site

SITE_CODENAMES = ["view_site", "add_site", "change_site"]


def _site_permissions():
    perms = list(
        Permission.objects.filter(
            content_type__app_label="donations", codename__in=SITE_CODENAMES
        )
    )
    if len(perms) != len(SITE_CODENAMES):
        raise CommandError("Site permissions are missing. Run 'python manage.py migrate' first.")
    return perms


def _is_manager(user) -> bool:
    return user.is_active and user.is_staff and all(
        user.has_perm(f"donations.{codename}") for codename in SITE_CODENAMES
    )


class Command(BaseCommand):
    help = "List sites and grant or revoke a user's permission to manage them."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--grant", metavar="USERNAME", help="Let this user view, add and change sites.")
        group.add_argument("--revoke", metavar="USERNAME", help="Remove this user's site permissions.")

    def handle(self, *args, **options):
        if options["grant"]:
            self._grant(self._get_user(options["grant"]))
        elif options["revoke"]:
            self._revoke(self._get_user(options["revoke"]))
        self._list()

    def _get_user(self, username):
        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            usernames = ", ".join(User.objects.order_by("username").values_list("username", flat=True))
            raise CommandError(f"No user named '{username}'. Existing users: {usernames or '(none)'}")

    def _grant(self, user):
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        user.user_permissions.add(*_site_permissions())
        self.stdout.write(self.style.SUCCESS(f"{user.username} can now manage sites at /admin/.\n"))

    def _revoke(self, user):
        if user.is_superuser:
            raise CommandError(f"{user.username} is a superuser and can manage everything; revoke that in /admin/ instead.")
        user.user_permissions.remove(*_site_permissions())
        # Only drop staff status when nothing else needs it, so other admin access survives.
        if not user.user_permissions.exists() and not user.groups.exists():
            user.is_staff = False
            user.save(update_fields=["is_staff"])
        self.stdout.write(self.style.SUCCESS(f"{user.username} can no longer manage sites.\n"))

    def _list(self):
        sites = Site.objects.annotate(donation_count=Count("donations")).order_by("name")
        self.stdout.write("Sites:")
        if not sites:
            self.stdout.write("  (none)")
        for site in sites:
            status = "active" if site.is_active else "inactive"
            self.stdout.write(f"  {site.name:<30} {status:<9} {site.donation_count} donation(s)")

        managers = [u for u in get_user_model().objects.order_by("username") if _is_manager(u)]
        self.stdout.write("\nCan manage all sites:")
        if not managers:
            self.stdout.write("  (nobody)")
        for user in managers:
            note = " (superuser)" if user.is_superuser else ""
            self.stdout.write(f"  {user.username}{note}")

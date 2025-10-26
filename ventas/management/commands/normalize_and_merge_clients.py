import sys
import re
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min
from django.db import transaction, models, IntegrityError
from ventas.models import Cliente, VentaReserva, MovimientoCliente, GiftCard

# --- Phone Normalization Logic ---
def normalize_phone(phone_number):
    """
    Cleans and normalizes a phone number to +569XXXXXXXX format.
    Handles spaces, common prefixes (+56, 56).
    Returns normalized number or None if invalid/unclear.
    """
    if not phone_number or not isinstance(phone_number, str):
        return None

    cleaned = phone_number.strip()
    if cleaned.startswith('+'):
        digits = '+' + ''.join(filter(str.isdigit, cleaned[1:]))
    else:
        digits = ''.join(filter(str.isdigit, cleaned))

    if digits.startswith('+569') and len(digits) == 12:
        return digits
    if digits.startswith('569') and len(digits) == 11:
        return '+' + digits
    if digits.startswith('9') and len(digits) == 9:
        return '+56' + digits

    # Consider other valid formats or return None
    return None # Indicate normalization failed or number is not Chilean mobile


class Command(BaseCommand):
    help = (
        'Normalizes all Cliente phone numbers first, then finds and merges '
        'duplicates based on the normalized numbers.'
    )

    def handle(self, *args, **options):
        self.stdout.write("Starting client phone normalization and duplicate merge process...")
        self.stdout.write(self.style.WARNING("IMPORTANT: Ensure you have a database backup before proceeding!"))

        clients_to_update = []
        normalization_skipped = 0
        normalization_failed_count = 0
        potential_conflicts = []

        # --- Phase 1: Normalize All Phone Numbers ---
        self.stdout.write("\n--- Phase 1: Normalizing All Phone Numbers ---")
        all_clients = Cliente.objects.exclude(telefono__isnull=True).exclude(telefono__exact='')

        for client in all_clients:
            original_phone = client.telefono
            normalized_phone = normalize_phone(original_phone)

            if normalized_phone != original_phone:
                # Check if the target normalized number *already exists* for another client
                # This check happens *before* attempting the update
                if normalized_phone and Cliente.objects.filter(telefono=normalized_phone).exclude(pk=client.pk).exists():
                    self.stderr.write(self.style.ERROR(
                        f"  Conflict detected: Normalizing '{original_phone}' for Client ID {client.id} "
                        f"to '{normalized_phone}' would create a duplicate. Skipping this normalization."
                    ))
                    potential_conflicts.append({'id': client.id, 'original': original_phone, 'normalized': normalized_phone})
                    normalization_skipped += 1
                    continue # Skip adding this client to the update list

                if normalized_phone is None:
                    self.stdout.write(f"  Client ID {client.id}: Could not normalize '{original_phone}', setting to NULL.")
                    client.telefono = None
                    clients_to_update.append(client)
                    normalization_failed_count += 1
                else:
                    self.stdout.write(f"  Client ID {client.id}: Normalizing '{original_phone}' to '{normalized_phone}'.")
                    client.telefono = normalized_phone
                    clients_to_update.append(client)

        if clients_to_update:
            self.stdout.write(f"\nAttempting to bulk update {len(clients_to_update)} phone numbers...")
            try:
                with transaction.atomic():
                    Cliente.objects.bulk_update(clients_to_update, ['telefono'])
                self.stdout.write(self.style.SUCCESS("Bulk update successful."))
            except IntegrityError as e:
                 # This might happen if normalization created duplicates *during* the bulk update
                 # despite the pre-check (e.g., two different numbers normalizing to the same value).
                 self.stderr.write(self.style.ERROR(f"IntegrityError during bulk update: {e}. "
                                                    "This likely means normalization created new duplicates. "
                                                    "The transaction was rolled back."))
                 self.stderr.write(self.style.WARNING("Please re-run the script to handle duplicates based on current values."))
                 sys.exit(1)
            except Exception as e:
                 raise CommandError(f"An unexpected error occurred during bulk update: {e}\nTransaction rolled back.")
        else:
             self.stdout.write("No phone numbers required normalization or updates.")

        if normalization_skipped > 0:
            self.stdout.write(self.style.WARNING(f"\nSkipped normalization for {normalization_skipped} clients due to potential conflicts."))
            self.stdout.write(self.style.WARNING("These conflicts need manual review or will be handled in the merge phase if they still exist."))

        # --- Phase 2: Merge Duplicates Based on *Normalized* Phone Numbers ---
        self.stdout.write("\n--- Phase 2: Merging Duplicates (Post-Normalization) ---")

        # Find duplicates again, now based on potentially normalized numbers
        duplicates_after_norm = Cliente.objects.filter(telefono__isnull=False) \
                                    .exclude(telefono__exact='') \
                                    .values('telefono') \
                                    .annotate(telefono_count=Count('id')) \
                                    .filter(telefono_count__gt=1)

        duplicate_phones_after_norm = [item['telefono'] for item in duplicates_after_norm]

        if not duplicate_phones_after_norm:
            self.stdout.write(self.style.SUCCESS("No duplicate phone numbers found after normalization."))
            self.stdout.write(self.style.SUCCESS("Process finished. You should now be able to run the migration."))
            sys.exit(0)

        self.stdout.write(f"Found {len(duplicate_phones_after_norm)} phone numbers with duplicates after normalization:")
        # for phone in duplicate_phones_after_norm:
        #     self.stdout.write(f"- {phone}") # Can be verbose

        total_merged_groups = 0
        total_deleted = 0

        try:
            with transaction.atomic():
                for phone in duplicate_phones_after_norm:
                    clients_with_duplicate = Cliente.objects.filter(telefono=phone).order_by('id')
                    if clients_with_duplicate.count() <= 1: continue

                    master_client = clients_with_duplicate.first()
                    ids_to_delete = list(clients_with_duplicate.values_list('id', flat=True)[1:])

                    self.stdout.write(f"\nProcessing normalized phone: '{phone}'")
                    self.stdout.write(f"  Keeping Client ID: {master_client.id} ({master_client.nombre})")
                    self.stdout.write(f"  Attempting to merge and delete Client IDs: {ids_to_delete}")

                    # Re-link related models
                    updated_vr_count = VentaReserva.objects.filter(cliente_id__in=ids_to_delete).update(cliente=master_client)
                    if updated_vr_count > 0: self.stdout.write(f"    Re-linked {updated_vr_count} VentaReserva records.")

                    updated_mc_count = MovimientoCliente.objects.filter(cliente_id__in=ids_to_delete).update(cliente=master_client)
                    if updated_mc_count > 0: self.stdout.write(f"    Re-linked {updated_mc_count} MovimientoCliente records.")

                    updated_gc1_count = GiftCard.objects.filter(cliente_comprador_id__in=ids_to_delete).update(cliente_comprador=master_client)
                    if updated_gc1_count > 0: self.stdout.write(f"    Re-linked {updated_gc1_count} GiftCard (comprador) records.")

                    updated_gc2_count = GiftCard.objects.filter(cliente_destinatario_id__in=ids_to_delete).update(cliente_destinatario=master_client)
                    if updated_gc2_count > 0: self.stdout.write(f"    Re-linked {updated_gc2_count} GiftCard (destinatario) records.")

                    # Delete the duplicate Cliente records
                    deleted_count, _ = Cliente.objects.filter(id__in=ids_to_delete).delete()
                    if deleted_count > 0:
                        self.stdout.write(f"    Deleted {deleted_count} duplicate Cliente records.")
                        total_deleted += deleted_count
                        total_merged_groups += 1

        except Exception as e:
            raise CommandError(f"An error occurred during merge phase: {e}\nTransaction rolled back. No changes were saved.")

        self.stdout.write(self.style.SUCCESS(f"\nMerge phase complete. Merged data for {total_merged_groups} duplicate phone numbers, deleting {total_deleted} client records."))
        self.stdout.write(self.style.SUCCESS("Process finished. You should now be able to run the migration."))

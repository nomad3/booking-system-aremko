import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from ventas.models import Comanda, VentaReserva

print("=== VERIFICAR USUARIO ERNESTO ===\n")

try:
    user = User.objects.get(username='Ernesto')

    print(f"Usuario: {user.username} (ID={user.id})")
    print(f"Email: {user.email}")
    print(f"is_active: {user.is_active}")
    print(f"is_staff: {user.is_staff}")
    print(f"is_superuser: {user.is_superuser}")

    print("\nGrupos:")
    grupos = user.groups.all()
    if grupos:
        for g in grupos:
            print(f"  - {g.name}")
            perms = g.permissions.all()
            if perms:
                for p in perms[:5]:  # Mostrar primeros 5 permisos del grupo
                    print(f"    • {p.codename}")
    else:
        print("  (Sin grupos)")

    print("\nPermisos directos del usuario:")
    perms = user.user_permissions.all()
    if perms:
        for p in perms:
            print(f"  - {p.content_type.app_label}.{p.codename}: {p.name}")
    else:
        print("  (Sin permisos directos)")

    # Verificar permisos específicos de Comanda
    print("\nPermisos de Comanda:")
    comanda_perms = [
        'ventas.add_comanda',
        'ventas.change_comanda',
        'ventas.delete_comanda',
        'ventas.view_comanda',
    ]

    for perm in comanda_perms:
        has_perm = user.has_perm(perm)
        print(f"  - {perm}: {'✅ SI' if has_perm else '❌ NO'}")

    # Verificar permisos de VentaReserva
    print("\nPermisos de VentaReserva:")
    vr_perms = [
        'ventas.add_ventareserva',
        'ventas.change_ventareserva',
        'ventas.view_ventareserva',
    ]

    for perm in vr_perms:
        has_perm = user.has_perm(perm)
        print(f"  - {perm}: {'✅ SI' if has_perm else '❌ NO'}")

    # Verificar si puede acceder al admin
    print("\nAcceso al admin:")
    print(f"  - Puede acceder al admin: {'✅ SI' if user.is_staff else '❌ NO'}")
    print(f"  - Cuenta activa: {'✅ SI' if user.is_active else '❌ NO'}")

except User.DoesNotExist:
    print("❌ El usuario Ernesto no existe")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
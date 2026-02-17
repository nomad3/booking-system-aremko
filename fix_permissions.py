import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from ventas.models import Comanda, DetalleComanda

print("=== ASIGNAR PERMISOS DE COMANDA ===\n")

try:
    # Usuarios que necesitan permisos
    usuarios = ['Ernesto', 'Deborah', 'Rafael']

    # Obtener permisos de Comanda
    ct_comanda = ContentType.objects.get_for_model(Comanda)
    ct_detalle = ContentType.objects.get_for_model(DetalleComanda)

    permisos_necesarios = [
        # Comanda
        Permission.objects.get(content_type=ct_comanda, codename='add_comanda'),
        Permission.objects.get(content_type=ct_comanda, codename='change_comanda'),
        Permission.objects.get(content_type=ct_comanda, codename='delete_comanda'),
        Permission.objects.get(content_type=ct_comanda, codename='view_comanda'),
        # DetalleComanda
        Permission.objects.get(content_type=ct_detalle, codename='add_detallecomanda'),
        Permission.objects.get(content_type=ct_detalle, codename='change_detallecomanda'),
        Permission.objects.get(content_type=ct_detalle, codename='delete_detallecomanda'),
        Permission.objects.get(content_type=ct_detalle, codename='view_detallecomanda'),
    ]

    print(f"Permisos a asignar: {len(permisos_necesarios)}")

    for username in usuarios:
        try:
            user = User.objects.get(username=username)

            if user.is_superuser:
                print(f"\n✅ {username} es superusuario - ya tiene todos los permisos")
                continue

            print(f"\nAsignando permisos a {username}...")

            # Asignar permisos
            for perm in permisos_necesarios:
                user.user_permissions.add(perm)
                print(f"  + {perm.codename}")

            print(f"✅ {len(permisos_necesarios)} permisos asignados a {username}")

        except User.DoesNotExist:
            print(f"\n⚠️  Usuario {username} no existe")

    print("\n✅ Permisos actualizados exitosamente")
    print("\nAhora los usuarios deberían poder crear comandas desde el admin.")

except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN ===")
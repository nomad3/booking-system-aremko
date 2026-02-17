import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from ventas.models import Comanda

print("=== VERIFICAR PERMISOS DE USUARIOS ===\n")

# Obtener content type de Comanda
ct = ContentType.objects.get_for_model(Comanda)

# Permisos necesarios para Comanda
permisos_comanda = Permission.objects.filter(content_type=ct)
print("Permisos disponibles para Comanda:")
for perm in permisos_comanda:
    print(f"  - {perm.codename}: {perm.name}")

print("\n" + "="*50 + "\n")

# Verificar permisos de usuarios staff
usuarios_staff = User.objects.filter(is_staff=True)[:5]

for user in usuarios_staff:
    print(f"\n{user.username} (ID={user.id}):")
    print(f"  - is_staff: {user.is_staff}")
    print(f"  - is_superuser: {user.is_superuser}")

    if user.is_superuser:
        print("  - ✅ SUPERUSUARIO - Tiene TODOS los permisos")
    else:
        # Verificar permisos específicos de Comanda
        permisos = []
        for perm in permisos_comanda:
            if user.has_perm(f'ventas.{perm.codename}'):
                permisos.append(perm.codename)

        if permisos:
            print(f"  - Permisos de Comanda: {', '.join(permisos)}")
        else:
            print("  - ❌ NO tiene permisos de Comanda")

        # Verificar grupos
        grupos = user.groups.all()
        if grupos:
            print(f"  - Grupos: {', '.join([g.name for g in grupos])}")

print("\n" + "="*50)
print("\nPara dar permisos a un usuario, ejecuta:")
print("python manage.py shell")
print(">>> from django.contrib.auth.models import User, Permission")
print(">>> user = User.objects.get(username='Ernesto')")
print(">>> perm = Permission.objects.get(codename='add_comanda')")
print(">>> user.user_permissions.add(perm)")
print(">>> perm = Permission.objects.get(codename='change_comanda')")
print(">>> user.user_permissions.add(perm)")
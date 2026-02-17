import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== ARREGLAR TODAS LAS COLUMNAS DEL CALENDARIO ===\n")

cursor = connection.cursor()

# Mapeo de columnas: lo que el calendario busca -> lo que realmente existe
fixes = {
    'ventas_serviciobloqueo': [
        # El calendario busca created_at/updated_at pero existen como creado_en
        ("ALTER TABLE ventas_serviciobloqueo ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE",
         "UPDATE ventas_serviciobloqueo SET created_at = creado_en WHERE created_at IS NULL"),

        ("ALTER TABLE ventas_serviciobloqueo ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
         "UPDATE ventas_serviciobloqueo SET updated_at = creado_en WHERE updated_at IS NULL"),
    ],

    'ventas_ventareserva': [
        # El calendario busca 'fecha' pero existe 'fecha_reserva'
        ("ALTER TABLE ventas_ventareserva ADD COLUMN IF NOT EXISTS fecha DATE",
         "UPDATE ventas_ventareserva SET fecha = fecha_reserva WHERE fecha IS NULL"),

        # El calendario busca 'hora' - necesitamos extraerla de fecha_reserva si es timestamp
        ("ALTER TABLE ventas_ventareserva ADD COLUMN IF NOT EXISTS hora TIME",
         "UPDATE ventas_ventareserva SET hora = fecha_reserva::time WHERE hora IS NULL"),

        # El calendario busca 'estado' pero existe 'estado_reserva'
        ("ALTER TABLE ventas_ventareserva ADD COLUMN IF NOT EXISTS estado VARCHAR(50)",
         "UPDATE ventas_ventareserva SET estado = estado_reserva WHERE estado IS NULL"),

        # Timestamps
        ("ALTER TABLE ventas_ventareserva ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE",
         "UPDATE ventas_ventareserva SET created_at = fecha_creacion WHERE created_at IS NULL"),

        ("ALTER TABLE ventas_ventareserva ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
         "UPDATE ventas_ventareserva SET updated_at = fecha_creacion WHERE updated_at IS NULL"),
    ],

    'ventas_servicio': [
        # Solo necesita timestamps
        ("ALTER TABLE ventas_servicio ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", None),
        ("ALTER TABLE ventas_servicio ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", None),
    ]
}

print("Este script agregará columnas duplicadas que mapean a las existentes.")
print("Esto permite que el calendario funcione sin cambiar el código.\n")

respuesta = input("¿Proceder con los arreglos? (s/n): ")

if respuesta.lower() == 's':
    errores = []
    exitos = []

    for tabla, comandos in fixes.items():
        print(f"\n{'='*50}")
        print(f"Procesando tabla: {tabla}")
        print('='*50)

        for i, (alter_cmd, update_cmd) in enumerate(comandos):
            try:
                # Ejecutar ALTER TABLE
                print(f"\nEjecutando: {alter_cmd[:60]}...")
                cursor.execute(alter_cmd)

                # Si hay comando UPDATE, ejecutarlo
                if update_cmd:
                    print(f"Copiando datos: {update_cmd[:60]}...")
                    cursor.execute(update_cmd)
                    rows_affected = cursor.rowcount
                    print(f"✅ {rows_affected} filas actualizadas")

                connection.commit()
                exitos.append(f"{tabla}: {alter_cmd.split(' ')[-1]}")

            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg:
                    print(f"⚠️  La columna ya existe, saltando...")
                else:
                    print(f"❌ Error: {error_msg}")
                    errores.append(f"{tabla}: {error_msg}")
                connection.rollback()

    # Resumen final
    print(f"\n\n{'='*50}")
    print("RESUMEN")
    print('='*50)

    if exitos:
        print(f"\n✅ Cambios exitosos: {len(exitos)}")
        for exito in exitos:
            print(f"   - {exito}")

    if errores:
        print(f"\n❌ Errores encontrados: {len(errores)}")
        for error in errores:
            print(f"   - {error}")

    print("\n🎯 RESULTADO FINAL:")
    if not errores or all("already exists" in e for e in errores):
        print("   ✅ El calendario debería funcionar ahora!")
        print("   Recarga la página del calendario para verificar.")
    else:
        print("   ⚠️  Algunos cambios fallaron. Revisa los errores arriba.")

else:
    print("\nOperación cancelada.")

print("\n=== FIN ===")
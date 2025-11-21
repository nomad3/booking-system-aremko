# 📸 Guía: Subir Imágenes a las GiftCards

Esta guía te explica cómo agregar fotos reales a las experiencias de GiftCard para que aparezcan en los PDFs que reciben los clientes.

---

## 🎯 Objetivo

Reemplazar los iconos del wizard con **fotos profesionales** de:
- Tinas calientes con vapor
- Masajes en domos
- Cabañas y alojamientos
- Packs románticos
- Experiencias de cumpleaños

---

## 📋 Lista de Experiencias que Necesitan Fotos

### 🛁 Tinas y Hidromasajes (5 experiencias)
1. **`tinas`** - Tina para 2
2. **`tinas_masajes_semana`** - Tina + Masajes (Dom-Jue)
3. **`tinas_masajes_finde`** - Tina + Masajes (Vie-Sáb)
4. **`pack_4_personas`** - Pack 4 Personas
5. **`pack_6_personas`** - Pack 6 Personas

### 💆 Masajes (4 experiencias)
6. **`masaje_piedras`** - Masaje Piedras Calientes
7. **`masaje_deportivo`** - Masaje Deportivo
8. **`masaje_pareja`** - Masaje para Dos
9. **`drenaje_linfatico`** - Drenaje Linfático

### 🏡 Alojamiento (3 experiencias)
10. **`alojamiento_semana`** - Alojamiento + Tinas (Dom-Jue)
11. **`alojamiento_finde`** - Alojamiento + Tinas (Vie-Sáb)
12. **`alojamiento_romantico`** - Paquete Romántico Completo

### 🎉 Celebraciones (2 experiencias)
13. **`tina_cumpleaños`** - Tina + Celebración Especial
14. **`tina_celebracion`** - Tina + Ambientación Romántica

### 💳 Tarjetas de Valor (1 experiencia)
15. **`monto_libre`** - Monto Libre

---

## 🔧 Método 1: Subir desde el Admin Django (RECOMENDADO)

### Paso 1: Accede al Admin
1. Ve a: https://www.aremko.cl/admin/
2. Inicia sesión con tu usuario admin
3. En el menú lateral, busca **"VENTAS Y RESERVAS"**
4. Haz clic en **"Crear GiftCards"** (botón que acabamos de agregar)

O directo: https://www.aremko.cl/admin/ventas/giftcardexperiencia/

### Paso 2: Edita cada Experiencia
1. Haz clic en el nombre de la experiencia (ej: "Tina para 2")
2. En la sección **"Imagen"**, verás:
   ```
   Imagen: [Actualmente: giftcards/experiencias/tinas_placeholder.jpg]
   [Cambiar:] [Examinar...] [Borrar]
   ```
3. Haz clic en **"Examinar..."**
4. Selecciona la foto de tu computadora
5. Haz clic en **"Guardar"** (abajo a la derecha)

### Paso 3: Repite para las 15 Experiencias
- Puedes editarlas todas en una sesión
- Las imágenes se guardan automáticamente en `/media/giftcards/experiencias/`

---

## 📸 Especificaciones de las Fotos

### Requisitos Técnicos
- **Formato**: JPG o PNG (JPG recomendado para menor peso)
- **Resolución**: Mínimo 800x600px, óptimo 1200x900px
- **Peso**: Máximo 500KB por imagen
- **Orientación**: Horizontal (landscape) preferiblemente

### Calidad Visual
✅ **Buenas prácticas:**
- Fotos con buena iluminación natural
- Tinas con vapor visible (efecto spa)
- Sin personas (para privacidad) o modelos autorizados
- Fondo limpio y profesional
- Colores cálidos y acogedores

❌ **Evitar:**
- Fotos borrosas o pixeladas
- Imágenes muy oscuras
- Fotos con marca de agua de bancos de imágenes
- Fotos verticales (se verán cortadas)

---

## 🖼️ Opciones para Conseguir las Fotos

### Opción A: Fotos Propias de Aremko
**MEJOR OPCIÓN** - Usa fotos reales de tu spa:
- Toma fotos con tu celular o cámara
- Muestra la experiencia real que recibirán
- Auténtico y genera confianza

**Tips de fotografía:**
- Hora dorada: Fotografía al atardecer para luz cálida
- Vapor: Agrega agua caliente para efecto spa
- Ángulos: Toma desde arriba (cenital) o a nivel del agua
- Edición: Ajusta brillo y contraste con apps como Lightroom Mobile

### Opción B: Banco de Imágenes Gratuitas
Si no tienes fotos propias, usa bancos libres de derechos:

**Unsplash** (https://unsplash.com/)
```
Búsquedas recomendadas:
- "hot tub forest" (tinas en bosque)
- "spa massage stones" (masaje piedras)
- "cabin forest" (cabañas bosque)
- "romantic spa" (spa romántico)
- "birthday spa" (spa cumpleaños)
```

**Pexels** (https://pexels.com/)
```
Búsquedas en español:
- "tinas calientes"
- "masaje spa"
- "cabaña bosque"
- "spa pareja"
```

### Opción C: Contratar Fotógrafo
Para resultados profesionales:
- Fotógrafo local de Puerto Varas
- Sesión de 2-3 horas
- 15-20 fotos editadas
- Inversión: $100.000 - $200.000 CLP

---

## 🚀 Método 2: Subir por SSH (Avanzado)

Si tienes las imágenes en tu computadora y quieres subirlas directamente al servidor:

### Paso 1: Conectar por SSH
```bash
# Desde tu terminal
ssh <usuario>@<servidor-render>
```

### Paso 2: Crear directorio si no existe
```bash
mkdir -p /app/media/giftcards/experiencias/
```

### Paso 3: Subir imágenes con SCP
```bash
# Desde tu computadora local (otra terminal)
scp tinas.jpg <usuario>@<servidor>:/app/media/giftcards/experiencias/tinas.jpg
scp masaje_piedras.jpg <usuario>@<servidor>:/app/media/giftcards/experiencias/masaje_piedras.jpg
# ... repetir para todas
```

### Paso 4: Actualizar Base de Datos
```bash
# En el servidor, ejecutar:
cd /app
python manage.py shell

# Dentro de shell:
from ventas.models import GiftCardExperiencia

exp = GiftCardExperiencia.objects.get(id_experiencia='tinas')
exp.imagen = 'giftcards/experiencias/tinas.jpg'
exp.save()

# Repetir para cada experiencia
```

---

## 📝 Nombres Sugeridos para los Archivos

Para mantener consistencia, nombra tus archivos así:

```
tinas.jpg
tinas_masajes_semana.jpg
tinas_masajes_finde.jpg
pack_4_personas.jpg
pack_6_personas.jpg
masaje_piedras.jpg
masaje_deportivo.jpg
masaje_pareja.jpg
drenaje_linfatico.jpg
alojamiento_semana.jpg
alojamiento_finde.jpg
alojamiento_romantico.jpg
tina_cumpleanos.jpg
tina_celebracion.jpg
monto_libre.jpg
```

---

## ✅ Verificar que Funcionó

Después de subir las imágenes:

### 1. Verificar en el Admin
- Ve a: https://www.aremko.cl/admin/ventas/giftcardexperiencia/
- Deberías ver miniaturas de las fotos en la lista

### 2. Probar el PDF
**IMPORTANTE**: Para probar, necesitas hacer una compra de prueba:
1. Ve al wizard: https://www.aremko.cl/ventas/giftcards/wizard/
2. Selecciona una experiencia que ya tenga foto
3. Completa el proceso hasta el checkout
4. Paga (puedes usar tarjeta de prueba en Flow)
5. Revisa el email - el PDF debe mostrar la foto

### 3. Verificar URL de la imagen
En el admin, haz clic en "Ver en el sitio" de una experiencia.
La URL de la imagen debe ser:
```
https://www.aremko.cl/media/giftcards/experiencias/tinas.jpg
```

---

## 🆘 Solución de Problemas

### "La imagen no aparece en el PDF"
✅ **Solución**:
1. Verifica que la imagen se subió correctamente en el admin
2. Revisa que el campo `servicio_asociado` del GiftCard coincida con `id_experiencia` de la experiencia
3. Revisa los logs del servidor para errores de carga de imagen

### "Error al subir imagen: Archivo muy grande"
✅ **Solución**:
- Comprime la imagen con TinyPNG (https://tinypng.com/)
- O redimensiona a 1200x900px máximo

### "Las imágenes aparecen distorsionadas"
✅ **Solución**:
- Usa fotos horizontales (landscape)
- Aspecto ratio recomendado: 4:3 o 16:9
- El PDF las mostrará con max-height: 300px automáticamente

---

## 📊 Resultado Esperado

Una vez que subas todas las fotos, los clientes recibirán PDFs como este:

```
┌─────────────────────────────────────────┐
│   AREMKO AGUAS CALIENTES & SPA         │
│      🎁 Certificado de Regalo 🎁       │
├─────────────────────────────────────────┤
│         Para: María González            │
│                                         │
│  ╔═══════════════════════════════════╗ │
│  ║                                   ║ │
│  ║   [FOTO REAL DE TINAS CON VAPOR] ║ │
│  ║                                   ║ │
│  ╚═══════════════════════════════════╝ │
│                                         │
│  "Querida María, disfruta de un        │
│   momento de relajación en las tinas   │
│   calientes de Aremko Spa..."          │
│                                         │
│      EXPERIENCIA: Tina para 2          │
│         CÓDIGO: GC-ABC123              │
│      VÁLIDO HASTA: 21 Feb 2026         │
└─────────────────────────────────────────┘
```

---

## 💡 Preguntas Frecuentes

**P: ¿Puedo usar las mismas fotos para varias experiencias?**
R: Sí, pero no es recomendado. Cada experiencia debería tener su foto única para dar sensación de variedad.

**P: ¿Las fotos se muestran también en el wizard?**
R: Por ahora no, el wizard sigue usando iconos. Puedes actualizar el wizard después para mostrar las fotos.

**P: ¿Qué pasa si no subo foto a una experiencia?**
R: El PDF se generará igual pero sin la imagen, solo con el nombre de la experiencia.

**P: ¿Puedo cambiar las fotos después?**
R: Sí, simplemente edita la experiencia en el admin y sube una nueva imagen. Los PDFs futuros usarán la nueva foto.

---

## 📞 Soporte

Si tienes problemas subiendo las imágenes o necesitas ayuda:
1. Revisa los logs del servidor en Render
2. Verifica permisos de escritura en `/media/giftcards/experiencias/`
3. Contacta al equipo de desarrollo

---

**Última actualización**: 2025-11-21
**Versión**: 1.0

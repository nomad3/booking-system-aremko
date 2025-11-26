# Plan de Trabajo: Cumplimiento de Requisitos SendGrid

Este plan detalla los pasos necesarios para cumplir con los requisitos de verificación de cuenta de SendGrid para Aremko.

## 1. Requisitos de Información (Acción: Usuario)
El usuario debe redactar y tener lista la siguiente información para responder al correo de soporte de SendGrid:

*   **Descripción del Negocio:** Un párrafo detallando qué hace Aremko (servicios de relajación, tinas, cabañas, masajes) y quiénes son sus clientes.
*   **Datos Personales:** Nombre completo y rol (ej. Dueño/Gerente) de quien solicita la cuenta.
*   **Verificación de Identidad:** Enlace al perfil de LinkedIn del solicitante o red social del negocio donde aparezca su nombre.
*   **Dirección Física:** La dirección exacta de Aremko para incluir en el pie de página de los correos.

## 2. Requisitos Técnicos en el Sitio Web (Acción: Desarrollador)

### 2.1. Página de Política de Privacidad
SendGrid exige un enlace funcional a la política de privacidad.
*   **Tarea:** Crear vista y template `/privacy-policy/`.
*   **Contenido:** Texto estándar sobre protección de datos, uso de cookies y no compartición de emails con terceros.

### 2.2. Sistema de Suscripción (Opt-in)
Para enviar correos de marketing, se debe demostrar cómo se obtienen los correos (consentimiento).
*   **Tarea:** Implementar un formulario de suscripción simple en el pie de página del sitio web ("Suscríbete a nuestro newsletter").
*   **Tarea:** Crear modelo `NewsletterSubscriber` o campo en `Cliente` para registrar fecha e IP de suscripción.

### 2.3. Sistema de Desuscripción (Opt-out)
Todo correo de marketing debe tener un enlace funcional para darse de baja.
*   **Tarea:** Crear vista `/unsubscribe/<email>/` (o con token seguro).
*   **Tarea:** Crear página de confirmación de desuscripción.

## 3. Plantilla de Email Cumplimiento (Acción: Desarrollador)

### 3.1. Template Base de Marketing
Crear un template HTML para correos que incluya obligatoriamente en el footer:
*   Enlace "Darse de baja" (Unsubscribe).
*   Enlace "Política de Privacidad".
*   Dirección física del negocio.

### 3.2. Generación de Muestra
Generar un correo de prueba real utilizando este template para tomar capturas de pantalla o exportar como evidencia para SendGrid.

## Cronograma de Ejecución

1.  **Paso 1:** Crear página de Política de Privacidad (Prioridad Alta).
2.  **Paso 2:** Implementar formulario de suscripción en el sitio (Prioridad Alta).
3.  **Paso 3:** Implementar lógica de desuscripción (Prioridad Media).
4.  **Paso 4:** Crear template de email con footer legal (Prioridad Alta).
5.  **Paso 5:** Recopilar capturas de pantalla y textos para enviar a SendGrid.

---
**Siguiente paso recomendado:** Comenzar con el Paso 1 y 2 (Política de Privacidad y Formulario de Suscripción).

# ventas/apps.py

from django.apps import AppConfig

class VentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ventas'
    verbose_name = 'Ventas y CRM' # Optional: Set a more descriptive name for the admin

    def ready(self):
        # Importar triggers de comunicación para registrar señales (post_save VentaReserva)
        # Nota: mantener este import aquí para garantizar el registro en arranque
        try:
            import ventas.services.communication_triggers  # noqa: F401
        except Exception as exc:
            # Loguear, pero no romper el arranque del proyecto
            from django.conf import settings
            import logging
            logging.getLogger(__name__).warning(
                f"No se pudo importar communication_triggers: {exc}"
            )

        # Import admin classes and models here to avoid circular imports
        from django.contrib import admin
        from . import models
        from . import admin as ventas_admin # Import the admin module itself

        # Register models explicitly, ensuring dependencies are met
        # Standard Models
        admin.site.register(models.Cliente, ventas_admin.ClienteAdmin) # Register Cliente first
        admin.site.register(models.Proveedor, ventas_admin.ProveedorAdmin)
        admin.site.register(models.CategoriaProducto, ventas_admin.CategoriaProductoAdmin)
        admin.site.register(models.Producto, ventas_admin.ProductoAdmin)
        admin.site.register(models.Compra, ventas_admin.CompraAdmin)
        admin.site.register(models.GiftCard, ventas_admin.GiftCardAdmin)
        admin.site.register(models.CategoriaServicio, ventas_admin.CategoriaServicioAdmin)
        admin.site.register(models.Servicio, ventas_admin.ServicioAdmin)
        admin.site.register(models.VentaReserva, ventas_admin.VentaReservaAdmin)
        admin.site.register(models.Pago, ventas_admin.PagoAdmin)
        admin.site.register(models.HomepageConfig, ventas_admin.HomepageConfigAdmin)
        # Note: MovimientoCliente, ReservaServicio, ReservaProducto, DetalleCompra are typically handled via inlines

        # CRM Models
        admin.site.register(models.Lead, ventas_admin.LeadAdmin)
        admin.site.register(models.Company, ventas_admin.CompanyAdmin)
        admin.site.register(models.Contact, ventas_admin.ContactAdmin)
        admin.site.register(models.Activity, ventas_admin.ActivityAdmin)
        admin.site.register(models.Campaign, ventas_admin.CampaignAdmin)
        admin.site.register(models.Deal, ventas_admin.DealAdmin)
        admin.site.register(models.CampaignInteraction, ventas_admin.CampaignInteractionAdmin)

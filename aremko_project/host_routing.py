"""Middleware que cambia request.urlconf según el host de la request.

Aremko y Destino Puerto Varas comparten la misma instancia Django y BD,
pero exponen catálogos distintos. Este middleware enruta el host
destinopuertovaras.cl al URLConf alternativo `dpv_root_urls`, que monta
la app DPV en root (sin prefijo `/dpv/`).

Para aremko.cl y resto de hosts, no toca nada — usa el URLConf por
defecto (`aremko_project.urls`).
"""
from __future__ import annotations


DPV_HOSTS = {
    "destinopuertovaras.cl",
    "www.destinopuertovaras.cl",
}


class HostBasedURLConfMiddleware:
    """Setea request.urlconf=dpv_root_urls si el host es DPV."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        if host in DPV_HOSTS:
            request.urlconf = "aremko_project.dpv_root_urls"
        return self.get_response(request)

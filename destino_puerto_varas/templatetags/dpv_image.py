"""Template filters para optimización de imágenes Cloudinary en DPV."""
import re
from django import template

register = template.Library()

CLD_HOST_RE = re.compile(r"https?://res\.cloudinary\.com/[^/]+/image/upload/")
CLD_HAS_TRANSFORM_RE = re.compile(
    r"https?://res\.cloudinary\.com/[^/]+/image/upload/[^/]*[a-z]_[^/]+/"
)


@register.filter(name="cld_transform")
def cld_transform(url, params):
    """Inyecta parámetros de transformación Cloudinary tras `/upload/`.

    - Si la URL no es Cloudinary → la devuelve sin tocar.
    - Si ya tiene transformación (segmento con `letra_valor`) → no la duplica.
    - `params` es string tipo "f_auto,q_auto,w_1600".

    Uso: {{ photo.image.url|cld_transform:"f_auto,q_auto,w_1600" }}
    """
    if not url or not isinstance(url, str):
        return url
    if "res.cloudinary.com" not in url or "/image/upload/" not in url:
        return url
    if CLD_HAS_TRANSFORM_RE.match(url):
        return url
    if not params:
        return url
    return CLD_HOST_RE.sub(
        lambda m: m.group(0) + params.strip("/") + "/",
        url,
        count=1,
    )

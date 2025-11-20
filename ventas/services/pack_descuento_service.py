"""
Servicio para gestionar descuentos por packs de servicios
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional
from django.utils import timezone
from ..models import PackDescuento, Servicio


class PackDescuentoService:
    """Servicio para detectar y aplicar descuentos por packs"""

    @staticmethod
    def detectar_packs_aplicables(cart_items: List[Dict]) -> List[Dict]:
        """
        Detecta qué packs de descuento aplican para los items del carrito

        Args:
            cart_items: Lista de items del carrito con estructura:
                [{
                    'id': servicio_id,
                    'nombre': str,
                    'precio': float,
                    'fecha': 'YYYY-MM-DD',
                    'hora': 'HH:MM',
                    'cantidad_personas': int,
                    'tipo_servicio': str
                }, ...]

        Returns:
            Lista de packs aplicables con estructura:
                [{
                    'pack': PackDescuento instance,
                    'descuento': Decimal,
                    'items_incluidos': [indices de items que forman el pack],
                    'descripcion_aplicacion': str
                }, ...]
        """
        packs_aplicables = []

        print(f"DEBUG PackDescuento: Detectando packs para {len(cart_items)} items")
        for idx, item in enumerate(cart_items):
            print(f"  Item {idx}: {item.get('nombre')} - Tipo: {item.get('tipo_servicio')} - Fecha: {item.get('fecha')}")

        # Obtener todos los packs activos
        packs_activos = PackDescuento.objects.filter(
            activo=True,
            fecha_inicio__lte=timezone.now().date()
        ).exclude(
            fecha_fin__lt=timezone.now().date()
        ).order_by('-prioridad', '-descuento')

        print(f"DEBUG: Encontrados {packs_activos.count()} packs activos")

        # Agrupar items por fecha si es necesario
        items_por_fecha = {}
        for idx, item in enumerate(cart_items):
            fecha = item.get('fecha')
            if fecha:
                if fecha not in items_por_fecha:
                    items_por_fecha[fecha] = []
                items_por_fecha[fecha].append((idx, item))

        # Verificar cada pack
        for pack in packs_activos:
            print(f"\nDEBUG: Verificando pack '{pack.nombre}'")
            print(f"  - Usa servicios específicos: {pack.usa_servicios_especificos}")
            print(f"  - Servicios requeridos: {pack.servicios_requeridos}")
            print(f"  - Días válidos: {pack.dias_semana_validos}")
            print(f"  - Misma fecha: {pack.misma_fecha}")

            # Si el pack requiere misma fecha
            if pack.misma_fecha:
                # Verificar por cada fecha
                for fecha_str, items_fecha in items_por_fecha.items():
                    pack_aplicable = PackDescuentoService._verificar_pack_para_items(
                        pack, items_fecha, fecha_str
                    )
                    if pack_aplicable:
                        packs_aplicables.append(pack_aplicable)
            else:
                # Verificar todos los items sin importar fecha
                todos_items = [(idx, item) for idx, item in enumerate(cart_items)]
                pack_aplicable = PackDescuentoService._verificar_pack_para_items(
                    pack, todos_items, None
                )
                if pack_aplicable:
                    packs_aplicables.append(pack_aplicable)

        # Resolver conflictos si hay múltiples packs aplicables
        packs_aplicables = PackDescuentoService._resolver_conflictos_packs(packs_aplicables)

        return packs_aplicables

    @staticmethod
    def _verificar_pack_para_items(pack: PackDescuento,
                                   items_con_indices: List[tuple],
                                   fecha_str: Optional[str]) -> Optional[Dict]:
        """
        Verifica si un pack aplica para un conjunto de items

        Returns:
            Dict con información del pack si aplica, None si no aplica
        """
        print(f"\nDEBUG _verificar_pack_para_items: Pack '{pack.nombre}', fecha: {fecha_str}")

        # Verificar fecha si es necesario
        if fecha_str and pack.dias_semana_validos:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                # En Python: 0=Lunes, 1=Martes... 6=Domingo
                # Pero en el modelo usamos: 0=Domingo, 1=Lunes... 6=Sábado
                # Convertir el weekday de Python al formato del modelo
                dia_python = fecha.weekday()  # 0-6 donde 0=Lunes
                dia_modelo = (dia_python + 1) % 7  # Convertir a 0=Domingo

                print(f"  - Fecha {fecha_str} día Python: {dia_python}, día modelo: {dia_modelo} (0=Dom, 1=Lun...6=Sab)")

                if dia_modelo not in pack.dias_semana_validos:
                    print(f"  - Día {dia_modelo} no está en días válidos: {pack.dias_semana_validos}")
                    return None
            except ValueError:
                print(f"  - Error parseando fecha: {fecha_str}")
                return None

        # Verificar si el pack usa servicios específicos
        if hasattr(pack, 'usa_servicios_especificos') and pack.usa_servicios_especificos:
            # Lógica para servicios específicos
            servicios_ids_requeridos = set(pack.servicios_especificos.values_list('id', flat=True))
            servicios_ids_en_carrito = set()
            indices_por_servicio = {}

            for idx, item in items_con_indices:
                servicio_id = item.get('id')
                if servicio_id:
                    servicios_ids_en_carrito.add(servicio_id)
                    if servicio_id not in indices_por_servicio:
                        indices_por_servicio[servicio_id] = []
                    indices_por_servicio[servicio_id].append(idx)

            # Verificar si todos los servicios específicos están presentes
            if not servicios_ids_requeridos.issubset(servicios_ids_en_carrito):
                return None

            # Recopilar índices de items incluidos
            items_incluidos = []
            for servicio_id in servicios_ids_requeridos:
                if servicio_id in indices_por_servicio:
                    items_incluidos.extend(indices_por_servicio[servicio_id][:1])  # Solo uno de cada

        else:
            # Lógica para tipos de servicio
            # Como todos los servicios están marcados como 'otro' en la BD,
            # inferimos el tipo basándonos en el nombre del servicio

            # Contar tipos de servicio presentes basándonos en nombres
            tipos_presentes = {}
            indices_por_tipo = {}

            for idx, item in items_con_indices:
                nombre_servicio = item.get('nombre', '').lower()
                tipo_pack = None

                # Identificar tipo basado en el nombre del servicio
                # Categorías existentes: Cabañas, Tinas, Masajes, Ambientaciones
                if any(word in nombre_servicio for word in ['cabaña', 'cabana', 'torre', 'refugio', 'lodge']):
                    tipo_pack = 'cabana'  # Mapea a Cabañas
                elif any(word in nombre_servicio for word in ['tina', 'tinaja', 'termas', 'hot tub']):
                    tipo_pack = 'tina'    # Mapea a Tinas
                elif any(word in nombre_servicio for word in ['masaje', 'spa', 'relajación', 'descontracturante']):
                    tipo_pack = 'masaje'  # Mapea a Masajes
                elif any(word in nombre_servicio for word in ['decoración', 'ambientación', 'pétalos', 'velas']):
                    tipo_pack = 'decoracion'  # Mapea a Ambientaciones
                else:
                    tipo_pack = 'otro'

                print(f"  - Item {idx}: {item.get('nombre')} identificado como tipo: {tipo_pack}")

                if tipo_pack not in tipos_presentes:
                    tipos_presentes[tipo_pack] = 0
                    indices_por_tipo[tipo_pack] = []

                tipos_presentes[tipo_pack] += 1
                indices_por_tipo[tipo_pack].append(idx)

            # Verificar si todos los servicios requeridos están presentes
            servicios_requeridos = set(pack.servicios_requeridos) if pack.servicios_requeridos else set()
            print(f"  - Servicios requeridos originales: {servicios_requeridos}")
            print(f"  - Tipos presentes en carrito: {tipos_presentes}")

            # Convertir servicios requeridos a mayúsculas para compatibilidad
            servicios_requeridos_upper = set()
            for servicio in servicios_requeridos:
                if servicio == 'cabana':
                    servicios_requeridos_upper.add('ALOJAMIENTO')
                elif servicio == 'tina':
                    servicios_requeridos_upper.add('TINA')
                elif servicio == 'masaje':
                    servicios_requeridos_upper.add('MASAJE')
                else:
                    servicios_requeridos_upper.add(servicio.upper())

            print(f"  - Servicios requeridos convertidos: {servicios_requeridos_upper}")
            cumple_requisitos = servicios_requeridos_upper.issubset(set(tipos_presentes.keys()))
            print(f"  - ¿Cumple requisitos?: {cumple_requisitos}")

            if servicios_requeridos_upper and not cumple_requisitos:
                return None

            # Verificar cantidad mínima de noches para alojamiento
            if 'ALOJAMIENTO' in servicios_requeridos_upper or 'cabana' in servicios_requeridos:
                cantidad_alojamientos = tipos_presentes.get('ALOJAMIENTO', 0)
                if cantidad_alojamientos < pack.cantidad_minima_noches:
                    return None

            # Recopilar índices de items incluidos
            items_incluidos = []
            for tipo_orig in servicios_requeridos:
                # Convertir tipo para buscar en indices
                tipo_buscar = tipo_orig
                if tipo_orig == 'cabana':
                    tipo_buscar = 'ALOJAMIENTO'
                elif tipo_orig == 'tina':
                    tipo_buscar = 'TINA'
                elif tipo_orig == 'masaje':
                    tipo_buscar = 'MASAJE'
                else:
                    tipo_buscar = tipo_orig.upper()

                if tipo_buscar in indices_por_tipo:
                    # Solo incluir la cantidad necesaria
                    cantidad_necesaria = 1
                    if tipo_buscar == 'ALOJAMIENTO':
                        cantidad_necesaria = pack.cantidad_minima_noches
                    items_incluidos.extend(indices_por_tipo[tipo_buscar][:cantidad_necesaria])

        # Crear descripción de aplicación
        items_nombres = []
        for idx in items_incluidos:
            for i, (item_idx, item) in enumerate(items_con_indices):
                if item_idx == idx:
                    items_nombres.append(item['nombre'])
                    break

        descripcion = f"Pack aplicado: {pack.nombre} ({' + '.join(items_nombres)})"

        return {
            'pack': pack,
            'descuento': pack.descuento,
            'items_incluidos': sorted(items_incluidos),
            'descripcion_aplicacion': descripcion
        }

    @staticmethod
    def _resolver_conflictos_packs(packs_aplicables: List[Dict]) -> List[Dict]:
        """
        Resuelve conflictos cuando múltiples packs pueden aplicar
        Usa la prioridad y luego el mayor descuento
        """
        if len(packs_aplicables) <= 1:
            return packs_aplicables

        # Agrupar por items para detectar conflictos
        packs_sin_conflicto = []
        items_usados = set()

        # Ordenar por prioridad (ya vienen ordenados) y descuento
        for pack_info in packs_aplicables:
            items_pack = set(pack_info['items_incluidos'])

            # Si no hay conflicto con items ya usados
            if not items_pack.intersection(items_usados):
                packs_sin_conflicto.append(pack_info)
                items_usados.update(items_pack)

        return packs_sin_conflicto

    @staticmethod
    def calcular_total_con_descuentos(cart: Dict) -> Dict:
        """
        Calcula el total del carrito aplicando descuentos por packs

        Args:
            cart: Diccionario del carrito con estructura estándar

        Returns:
            Dict con:
                - subtotal: Total sin descuentos
                - descuentos: Lista de descuentos aplicados
                - total_descuentos: Suma de todos los descuentos
                - total: Total final con descuentos
        """
        # Calcular subtotal
        subtotal_servicios = sum(
            Decimal(str(item.get('subtotal', 0)))
            for item in cart.get('servicios', [])
        )
        subtotal_giftcards = sum(
            Decimal(str(item.get('precio', 0)))
            for item in cart.get('giftcards', [])
        )
        subtotal = subtotal_servicios + subtotal_giftcards

        # Detectar packs aplicables
        descuentos = []
        total_descuentos = Decimal('0')

        if cart.get('servicios'):
            packs_aplicables = PackDescuentoService.detectar_packs_aplicables(
                cart['servicios']
            )

            for pack_info in packs_aplicables:
                descuentos.append({
                    'nombre': pack_info['pack'].nombre,
                    'descripcion': pack_info['descripcion_aplicacion'],
                    'monto': float(pack_info['descuento']),
                    'items_incluidos': pack_info['items_incluidos']
                })
                total_descuentos += pack_info['descuento']

        return {
            'subtotal': float(subtotal),
            'descuentos': descuentos,
            'total_descuentos': float(total_descuentos),
            'total': float(subtotal - total_descuentos)
        }

    @staticmethod
    def obtener_sugerencias_pack(cart_items: List[Dict]) -> List[Dict]:
        """
        Sugiere qué servicios agregar para calificar para un pack

        Returns:
            Lista de sugerencias con estructura:
                [{
                    'pack': PackDescuento instance,
                    'servicios_faltantes': ['TINA', 'MASAJE'],
                    'ahorro_potencial': Decimal,
                    'mensaje': str
                }, ...]
        """
        sugerencias = []

        # Obtener packs activos
        packs_activos = PackDescuento.objects.filter(
            activo=True,
            fecha_inicio__lte=timezone.now().date()
        ).exclude(
            fecha_fin__lt=timezone.now().date()
        ).order_by('-descuento')

        # Mapear tipos actuales en el carrito
        tipo_servicio_map = {
            'cabana': 'ALOJAMIENTO',
            'cabin': 'ALOJAMIENTO',
            'alojamiento': 'ALOJAMIENTO',
            'tina': 'TINA',
            'hot_tub': 'TINA',
            'masaje': 'MASAJE',
            'massage': 'MASAJE',
            'decoracion': 'DECORACION',
            'decoration': 'DECORACION'
        }

        tipos_en_carrito = set()
        for item in cart_items:
            tipo_cart = item.get('tipo_servicio', '').lower()
            tipo_pack = tipo_servicio_map.get(tipo_cart, tipo_cart.upper())
            tipos_en_carrito.add(tipo_pack)

        # Verificar cada pack
        for pack in packs_activos:
            servicios_requeridos = set(pack.servicios_requeridos)
            servicios_faltantes = list(servicios_requeridos - tipos_en_carrito)

            # Si solo falta 1 servicio, es una buena sugerencia
            if len(servicios_faltantes) == 1:
                tipo_legible_map = {
                    'ALOJAMIENTO': 'una cabaña',
                    'TINA': 'tinas calientes',
                    'MASAJE': 'un masaje',
                    'DECORACION': 'decoración especial'
                }

                servicio_faltante = servicios_faltantes[0]
                servicio_legible = tipo_legible_map.get(
                    servicio_faltante,
                    servicio_faltante.lower()
                )

                mensaje = (
                    f"¡Agrega {servicio_legible} y ahorra "
                    f"${pack.descuento:,.0f} con el {pack.nombre}!"
                )

                sugerencias.append({
                    'pack': pack,
                    'servicios_faltantes': servicios_faltantes,
                    'ahorro_potencial': pack.descuento,
                    'mensaje': mensaje
                })

        return sugerencias[:2]  # Máximo 2 sugerencias
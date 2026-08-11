# -*- coding: utf-8 -*-
"""Registro financiero del dueño (P-22 F1): gastos, traspasos y saldos.

Qué guarda y qué NO guarda, a propósito:

- Los INGRESOS de reservas NO se duplican acá. Viven en `ventas.Pago` (día a día,
  por método) y el tablero los lee directo de ahí. Copiarlos crearía dos fuentes
  de verdad que se desincronizan solas.
- Acá vive lo que Django no tenía: GASTOS (por categoría del plan de cuentas),
  TRASPASOS entre cuentas propias (dos líneas que suman cero) y SALDOS de cierre
  mensual (el ancla de la conciliación: saldo inicial + entradas − salidas debe
  dar el saldo final de la cartola).

Jerarquía de fuentes (de más a menos confiable): api > correo > captura > manual.
Cada movimiento declara la suya, para que la auditoría sepa cuánto pesa.

Todo el módulo es SOLO SUPERUSUARIO (admin y tablero): es el instrumento del
dueño, separado de la operación diaria (el Conciliador de Deborah no se toca).
"""
from django.core.exceptions import ValidationError
from django.db import models


class CuentaFinanciera(models.Model):
    TIPOS = [
        ('pasarela', 'Pasarela de pago'),
        ('banco', 'Cuenta bancaria'),
        ('efectivo', 'Efectivo (caja)'),
        ('tarjeta_credito', 'Tarjeta de crédito'),
        ('billetera', 'Billetera digital'),
    ]

    clave = models.SlugField(max_length=40, unique=True,
                             help_text='Identificador estable: mercado_pago, bancoestado, scotiabank…')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    activa = models.BooleanField(default=True)
    notas = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Cuenta financiera'
        verbose_name_plural = 'Cuentas financieras'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class CategoriaFinanciera(models.Model):
    CLASES = [('ingreso', 'Ingreso'), ('gasto', 'Gasto')]
    # Plan de cuentas definido por Jorge el 2026-08-08: sus grupos, no los de
    # un manual. Los "personales" separados permiten ver el resultado
    # OPERACIONAL del negocio aparte de los retiros de la familia.
    GRUPOS = [
        ('personal', 'Sueldos de personal'),
        ('masajistas', 'Honorarios masajistas'),
        ('energia', 'Energía eléctrica'),
        ('marketing', 'Marketing'),
        ('infra_web', 'Infraestructura web e IA'),
        ('admin_fin', 'Administración y financieros'),
        ('operacion', 'Operación e insumos'),
        ('combustibles', 'Combustibles'),
        ('impuestos', 'Impuestos'),
        ('devoluciones', 'Devoluciones a clientes'),
        ('personales_martin', 'Personales Martín'),
        ('personales_alda', 'Personales Alda'),
        ('personales_jorge', 'Personales Jorge'),
        ('ingresos', 'Ingresos'),
        ('otros', 'Otros / por clasificar'),
    ]

    clave = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    clase = models.CharField(max_length=10, choices=CLASES, default='gasto')
    grupo = models.CharField(max_length=30, choices=GRUPOS, default='otros',
                             db_index=True)
    orden = models.PositiveSmallIntegerField(default=100)
    # Cuánto se piensa gastar al mes en este ítem (pedido de Jorge
    # 2026-08-10): el reporte del mes compara contra esto. En CERO significa
    # «sin presupuesto definido» y el reporte lo dice con un guion, en vez de
    # mostrar un exceso de todo lo gastado contra un presupuesto de $0.
    presupuesto_mensual = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text='Monto mensual esperado. 0 = sin presupuesto definido.')
    # Casi la mitad del gasto de Aremko se mueve con las ventas —insumos,
    # masajistas, comisiones, impuestos—, y un monto fijo ahí miente en las dos
    # direcciones: en temporada baja se cumple sin esfuerzo mientras entra
    # menos plata (Jorge 2026-08-11, después de ver que julio fue vacaciones de
    # invierno). Con un % puesto, ESE manda sobre el monto fijo.
    presupuesto_pct_ventas = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='% de las ventas del mes. Si es mayor que 0, manda sobre el '
                  'monto fijo. Ej: 20 = 20% de lo vendido ese mes.')

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías (plan de cuentas)'
        ordering = ['clase', 'orden', 'nombre']

    def __str__(self):
        return self.nombre


class MovimientoFinanciero(models.Model):
    CLASES = [
        ('ingreso', 'Ingreso'),
        ('gasto', 'Gasto'),
        ('traspaso', 'Traspaso entre cuentas propias'),
    ]
    SENTIDOS = [('entra', 'Entra'), ('sale', 'Sale')]
    FUENTES = [
        ('api', 'API verificada'),
        ('correo', 'Aviso por correo'),
        ('captura', 'Captura de pantalla'),
        ('manual', 'Digitación manual'),
    ]

    fecha = models.DateField(db_index=True)
    # PROTECT en cuenta y categoría: borrar una cuenta con movimientos dejaría
    # plata huérfana en el registro. Primero se reclasifica, después se borra.
    cuenta = models.ForeignKey(CuentaFinanciera, on_delete=models.PROTECT,
                               related_name='movimientos')
    clase = models.CharField(max_length=10, choices=CLASES, db_index=True)
    sentido = models.CharField(max_length=6, choices=SENTIDOS)
    monto = models.DecimalField(max_digits=12, decimal_places=0,
                                help_text='Siempre positivo; el signo lo pone clase/sentido.')
    categoria = models.ForeignKey(CategoriaFinanciera, on_delete=models.PROTECT,
                                  null=True, blank=True, related_name='movimientos',
                                  help_text='Obligatoria para ingresos/gastos; vacía en traspasos.')
    descripcion = models.CharField(max_length=255, blank=True, default='')
    fuente = models.CharField(max_length=10, choices=FUENTES, default='manual', db_index=True)
    referencia = models.CharField(
        max_length=100, blank=True, default='', db_index=True,
        help_text='Id externo (pago MP, nº operación de cartola, o id de carga histórica). '
                  'Es la llave de idempotencia: la misma referencia no se carga dos veces.')
    fecha_estimada = models.BooleanField(
        default=False,
        help_text='True cuando la fuente solo dio el mes (ej. correos agregados): '
                  'la fecha es el día 1 y no debe usarse para análisis diario.')
    traspaso_par = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text='La otra pierna del traspaso. Un traspaso son SIEMPRE dos líneas '
                  'que suman cero: sale de una cuenta y entra a la otra.')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Movimiento'
        verbose_name_plural = 'Movimientos'
        ordering = ['-fecha', '-id']
        constraints = [
            models.CheckConstraint(check=models.Q(monto__gt=0),
                                   name='finanzas_monto_positivo'),
            # Idempotencia de cargas: referencia única cuando existe.
            models.UniqueConstraint(fields=['referencia'],
                                    condition=~models.Q(referencia=''),
                                    name='finanzas_referencia_unica'),
        ]

    def __str__(self):
        signo = '+' if self.sentido == 'entra' else '−'
        return f'{self.fecha} {self.cuenta.clave} {signo}${self.monto:,.0f}'.replace(',', '.')

    def clean(self):
        # La coherencia clase/sentido no es opcional: un "gasto que entra" es un
        # dato corrupto que después nadie sabe interpretar.
        if self.clase == 'ingreso' and self.sentido != 'entra':
            raise ValidationError('Un ingreso siempre entra.')
        if self.clase == 'gasto' and self.sentido != 'sale':
            raise ValidationError('Un gasto siempre sale.')
        if self.clase == 'traspaso' and self.categoria_id:
            raise ValidationError('Un traspaso no lleva categoría: no es ingreso ni gasto.')
        if self.clase in ('ingreso', 'gasto') and not self.categoria_id:
            raise ValidationError('Ingresos y gastos necesitan categoría.')


class SaldoMensual(models.Model):
    """Saldo de cierre de cada cuenta al fin de mes — el ancla de la auditoría.

    Con esto la fórmula `saldo anterior + entradas − salidas = saldo de cierre`
    se puede verificar por cuenta. Si no cuadra, hay movimientos sin registrar
    (el caso Scotiabank entrante) o plata perdida. Es el único control que
    atrapa lo que ninguna API ni correo avisa.
    """
    FUENTES = [
        ('captura', 'Captura de pantalla'),
        ('cartola', 'Cartola (PDF/CSV)'),
        ('manual', 'Digitación manual'),
    ]

    cuenta = models.ForeignKey(CuentaFinanciera, on_delete=models.CASCADE,
                               related_name='saldos')
    periodo = models.DateField(help_text='Primer día del mes al que corresponde el cierre.')
    saldo_cierre = models.DecimalField(max_digits=14, decimal_places=0)
    fuente = models.CharField(max_length=10, choices=FUENTES, default='captura')
    notas = models.CharField(max_length=255, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Saldo mensual'
        verbose_name_plural = 'Saldos mensuales'
        ordering = ['-periodo', 'cuenta__nombre']
        constraints = [
            models.UniqueConstraint(fields=['cuenta', 'periodo'],
                                    name='finanzas_saldo_unico_por_mes'),
        ]

    def __str__(self):
        return f'{self.cuenta.clave} {self.periodo:%Y-%m}: ${self.saldo_cierre:,.0f}'.replace(',', '.')


class ReglaGlosa(models.Model):
    """La lista finita de glosas que SÍ son gasto de Aremko.

    Regla de Jorge (2026-08-10): en sus cuentas — la CuentaRUT, el Scotiabank
    de Alda y sus tarjetas — NADA se asigna solo a una cuenta del plan de
    cuentas. Todo queda por clasificar salvo lo que esté acá, y esta lista la
    administra él, no el código.

    Vale para TODAS las cuentas a propósito: Render se paga hoy con la
    CuentaRUT y mañana con la tarjeta de Alda, y no hay que enseñarle de nuevo.
    Quien la pagó igual queda registrado en el movimiento, que es lo que arma
    la cuenta corriente.
    """
    patron = models.CharField(
        max_length=120, unique=True,
        help_text='Texto que debe aparecer en la glosa. Se guarda en '
                  'MAYÚSCULAS y se compara sin distinguir mayúsculas.')
    categoria = models.ForeignKey(CategoriaFinanciera, on_delete=models.PROTECT,
                                  related_name='reglas_glosa')
    nota = models.CharField(max_length=200, blank=True, default='',
                            help_text='Por qué es de Aremko. Para acordarse en seis meses.')
    activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey('auth.User', null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='reglas_glosa')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regla de glosa'
        verbose_name_plural = 'Reglas de glosa (siempre Aremko)'
        ordering = ['patron']

    def save(self, *args, **kwargs):
        # El patrón se guarda normalizado: comparar en minúsculas contra un
        # banco que escribe TODO EN MAYÚSCULAS no calzaría nunca.
        self.patron = (self.patron or '').strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.patron} → {self.categoria.nombre}'

"""
Tests para Operación Vuelta a Casa, Etapa Geo.2.

Cubre:
    - Comando normalizar_ciudades_clientes:
        * Match exacto canónico (case-insensitive, trim, sin puntos)
        * Match por alias
        * Inferencia desde Cliente.comuna (sin ciudad)
        * Detección extranjero por marcadores de texto
        * Detección extranjero por Cliente.pais != Chile
        * Sin match → sin_clasificar
        * Respeta ciudad_normalizada_manual=True (no toca)
        * --dry-run no escribe
        * --solo-sin-clasificar filtra correctamente
        * --limit recorta
    - Admin: tocar ciudad_normalizada manualmente setea flag

Ejecutar:
    python manage.py test ventas.tests_geo
"""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from ventas.models import Ciudad, Cliente, Comuna, Region


class NormalizarCiudadesCommandTests(TestCase):
    """Verifica la lógica de clasificación del comando."""

    @classmethod
    def setUpTestData(cls):
        # Seed mínimo de ciudades (replicamos lo esencial del 0100)
        cls.pto_varas = Ciudad.objects.create(
            nombre_canonico='Puerto Varas',
            aliases='puerto varas|pto varas|pto. varas|p. varas',
            region_geografica='sur',
        )
        cls.pto_montt = Ciudad.objects.create(
            nombre_canonico='Puerto Montt',
            aliases='puerto montt|pto montt',
            region_geografica='sur',
        )
        cls.santiago = Ciudad.objects.create(
            nombre_canonico='Santiago',
            aliases='santiago|stgo|santiago de chile',
            region_geografica='nacional',
        )
        cls.las_condes = Ciudad.objects.create(
            nombre_canonico='Las Condes',
            aliases='las condes',
            region_geografica='nacional',
        )
        cls.coyhaique = Ciudad.objects.create(
            nombre_canonico='Coyhaique',
            aliases='coyhaique|coyahique',
            region_geografica='nacional',
        )
        cls.extranjero_gen = Ciudad.objects.create(
            nombre_canonico='_otros_extranjero_',
            aliases='',
            region_geografica='extranjero',
        )

    def _make_cliente(self, ciudad='', pais='', comuna=None, telefono=None):
        return Cliente.objects.create(
            nombre=f'Test {ciudad or "noname"}',
            telefono=telefono or f'+5698{Cliente.objects.count():07d}',
            ciudad=ciudad,
            pais=pais,
            comuna=comuna,
        )

    def _run(self, **kwargs):
        out = StringIO()
        call_command('normalizar_ciudades_clientes', stdout=out, **kwargs)
        return out.getvalue()

    # ---- Match canónico ----
    def test_match_canonico_case_insensitive(self):
        c = self._make_cliente(ciudad='puerto varas')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)
        self.assertEqual(c.region_geografica, 'sur')

    def test_match_canonico_con_mayusculas(self):
        c = self._make_cliente(ciudad='PUERTO VARAS')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)

    def test_match_canonico_con_trim(self):
        c = self._make_cliente(ciudad='  Puerto Varas  ')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)

    # ---- Match por alias ----
    def test_match_alias_pto_varas(self):
        c = self._make_cliente(ciudad='Pto Varas')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)
        self.assertEqual(c.region_geografica, 'sur')

    def test_match_alias_con_punto(self):
        c = self._make_cliente(ciudad='pto. varas')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)

    def test_match_alias_coyahique_typo(self):
        c = self._make_cliente(ciudad='coyahique')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.coyhaique.id)
        self.assertEqual(c.region_geografica, 'nacional')

    def test_match_alias_las_condes_es_nacional(self):
        c = self._make_cliente(ciudad='las condes')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.las_condes.id)
        self.assertEqual(c.region_geografica, 'nacional')

    # ---- Extranjero por texto ----
    def test_extranjero_por_marcador_argentina(self):
        c = self._make_cliente(ciudad='Buenos Aires, Argentina')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.region_geografica, 'extranjero')
        self.assertEqual(c.ciudad_normalizada_id, self.extranjero_gen.id)

    def test_extranjero_por_marcador_usa(self):
        c = self._make_cliente(ciudad='Denver, USA')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.region_geografica, 'extranjero')

    def test_extranjero_por_marcador_brasil(self):
        c = self._make_cliente(ciudad='Sao Paulo')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.region_geografica, 'extranjero')

    # ---- Extranjero por país ----
    def test_extranjero_por_pais(self):
        c = self._make_cliente(ciudad='', pais='Argentina')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.region_geografica, 'extranjero')

    def test_pais_chile_NO_es_extranjero(self):
        c = self._make_cliente(ciudad='Puerto Varas', pais='Chile')
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.region_geografica, 'sur')  # sur gana sobre pais

    # ---- Inferencia comuna → ciudad ----
    def test_inferencia_comuna(self):
        # Crear Comuna y asociar a cliente sin ciudad
        comuna_pv = Comuna.objects.create(nombre='Puerto Varas')
        c = self._make_cliente(ciudad='', comuna=comuna_pv)
        self._run()
        c.refresh_from_db()
        self.assertEqual(c.ciudad_normalizada_id, self.pto_varas.id)
        self.assertEqual(c.region_geografica, 'sur')

    def test_ciudad_gana_sobre_comuna_si_ambos_existen(self):
        comuna_stgo = Comuna.objects.create(nombre='Santiago')
        c = self._make_cliente(ciudad='Puerto Montt', comuna=comuna_stgo)
        self._run()
        c.refresh_from_db()
        # Gana ciudad="Puerto Montt", NO la comuna Santiago
        self.assertEqual(c.ciudad_normalizada_id, self.pto_montt.id)

    # ---- Sin match ----
    def test_sin_match(self):
        c = self._make_cliente(ciudad='asdkjhaskjdh')
        self._run()
        c.refresh_from_db()
        self.assertIsNone(c.ciudad_normalizada)
        self.assertEqual(c.region_geografica, 'sin_clasificar')

    def test_sin_ciudad_sin_comuna_sin_pais(self):
        c = self._make_cliente(ciudad='', pais='', comuna=None)
        self._run()
        c.refresh_from_db()
        self.assertIsNone(c.ciudad_normalizada)
        self.assertEqual(c.region_geografica, 'sin_clasificar')

    # ---- Respeta manual ----
    def test_respeta_manual_no_sobrescribe(self):
        c = self._make_cliente(ciudad='puerto varas')
        # Marcar manual con valor DIFERENTE
        c.ciudad_normalizada = self.santiago
        c.region_geografica = 'nacional'
        c.ciudad_normalizada_manual = True
        c.save()

        self._run()

        c.refresh_from_db()
        # Comando NO debe haber tocado nada
        self.assertEqual(c.ciudad_normalizada_id, self.santiago.id)
        self.assertEqual(c.region_geografica, 'nacional')

    # ---- Flags ----
    def test_dry_run_no_escribe(self):
        c = self._make_cliente(ciudad='Puerto Varas')
        self._run(dry_run=True)
        c.refresh_from_db()
        # No persistió cambio
        self.assertIsNone(c.ciudad_normalizada)
        self.assertEqual(c.region_geografica, 'sin_clasificar')

    def test_limit_recorta(self):
        for i in range(5):
            self._make_cliente(ciudad='Puerto Varas')
        self._run(limit=2)
        # Solo los primeros 2 actualizados
        clasificados = Cliente.objects.filter(region_geografica='sur').count()
        self.assertEqual(clasificados, 2)

    def test_solo_sin_clasificar_salta_clasificados(self):
        c_clasificado = self._make_cliente(ciudad='Puerto Varas')
        c_clasificado.region_geografica = 'sur'  # ya clasificado
        c_clasificado.save()

        c_pendiente = self._make_cliente(ciudad='Santiago')

        out = self._run(solo_sin_clasificar=True)

        c_pendiente.refresh_from_db()
        self.assertEqual(c_pendiente.region_geografica, 'nacional')

        # El clasificado quedó intacto (todavía 'sur' porque ya estaba)
        c_clasificado.refresh_from_db()
        self.assertEqual(c_clasificado.region_geografica, 'sur')


class CiudadModelTests(TestCase):
    def test_aliases_list_split(self):
        c = Ciudad.objects.create(
            nombre_canonico='Test',
            aliases='alpha|beta|gamma',
            region_geografica='nacional',
        )
        self.assertEqual(c.aliases_list(), ['alpha', 'beta', 'gamma'])

    def test_aliases_list_vacio(self):
        c = Ciudad.objects.create(
            nombre_canonico='Test', aliases='', region_geografica='nacional',
        )
        self.assertEqual(c.aliases_list(), [])

    def test_aliases_list_trimea_y_lower(self):
        c = Ciudad.objects.create(
            nombre_canonico='Test',
            aliases='  ALPHA  | Beta |gamma  ',
            region_geografica='nacional',
        )
        self.assertEqual(c.aliases_list(), ['alpha', 'beta', 'gamma'])


class AdminClienteManualFlagTests(TestCase):
    """Verifica que el admin setea ciudad_normalizada_manual=True al editar."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_superuser(
            username='admin_geo', email='a@test.com', password='pwd',
        )
        cls.santiago = Ciudad.objects.create(
            nombre_canonico='Santiago',
            aliases='santiago',
            region_geografica='nacional',
        )

    def setUp(self):
        self.client_http = Client()
        self.client_http.force_login(self.admin_user)
        self.cli = Cliente.objects.create(
            nombre='Manual Test', telefono='+56987651111',
            ciudad='', region_geografica='sin_clasificar',
        )

    def test_editar_ciudad_normalizada_setea_flag(self):
        # POST al admin cambiando ciudad_normalizada
        url = f'/admin/ventas/cliente/{self.cli.id}/change/'
        r = self.client_http.get(url)
        self.assertEqual(r.status_code, 200)

        # Hacer POST con los campos modificados
        r = self.client_http.post(url, data={
            'nombre': self.cli.nombre,
            'telefono': self.cli.telefono,
            'ciudad_normalizada': self.santiago.id,  # CAMBIO
            'region_geografica': 'nacional',
            'opt_out_whatsapp': False,
            # Resto vacío
            'ciudad': '',
            'email': '',
            'documento_identidad': '',
            'pais': '',
            'ciudad_normalizada_manual': False,  # NO marcado en form
            '_continue': 'Save and continue editing',
        })
        # Aunque mande 302 (redirect post-save) o 200, validamos el efecto
        self.cli.refresh_from_db()
        self.assertEqual(self.cli.ciudad_normalizada_id, self.santiago.id)
        # El admin debe haber seteado el flag automáticamente
        self.assertTrue(self.cli.ciudad_normalizada_manual)


class ExclusionCarabinerosTests(TestCase):
    """Verifica que el setting actualizado incluye 'carabineros'."""

    def test_carabineros_esta_en_settings_icontains(self):
        from django.conf import settings
        icontains = getattr(settings, 'OVC_CLIENTES_EXCLUIDOS_ICONTAINS', [])
        self.assertIn('carabineros', icontains)
        # Y aremko sigue ahí
        self.assertIn('aremko', icontains)

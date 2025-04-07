from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json
from datetime import date, time, datetime # Added datetime
import requests # Needed for mocking flow error

# Import models needed for setup
from .models import CategoriaServicio, Servicio, Cliente, VentaReserva, ReservaServicio, Pago # Added Pago

# Removed signal imports as disconnection workaround is no longer needed
# from django.db.models.signals import pre_save
# from .signals import validar_disponibilidad_admin

# Import view functions directly for potential direct testing if needed,
# but primarily test through URLs using the client.
# from .views import public_views, availability_views, flow_views, checkout_views, crud_views

class VentasViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for the class."""
        # No longer need to disconnect signal as validation logic is fixed
        # pre_save.disconnect(validar_disponibilidad_admin, sender=ReservaServicio)

        cls.categoria1 = CategoriaServicio.objects.create(nombre="Masajes")
        # Ensure slots_disponibles uses strings matching the model field type
        cls.servicio1 = Servicio.objects.create(
            nombre="Masaje Descontracturante",
            precio_base=30000,
            duracion=60,
            categoria=cls.categoria1,
            activo=True,
            publicado_web=True,
            # Use a fixed known Monday for reliable slot testing
            slots_disponibles={"monday": ["10:00", "11:00"], "tuesday": ["14:00"]}
        )
        cls.servicio_no_publicado = Servicio.objects.create(
            nombre="Masaje Secreto",
            duracion=30,
            precio_base=50000,
            categoria=cls.categoria1,
            activo=True,
            publicado_web=False # Not public
        )
        cls.cliente1 = Cliente.objects.create(nombre="Juan Perez", telefono="987654321", email="juan@test.com")
        cls.venta1 = VentaReserva.objects.create(cliente=cls.cliente1, total=30000, fecha_reserva=timezone.now())

        # Use a fixed known Monday date for creating the existing reservation
        cls.test_monday = date(2024, 6, 3) # Example Monday

        # Create the conflicting reservation *without* the signal running
        # Use string for hora_inicio matching the CharField model definition
        cls.reserva_existente = ReservaServicio.objects.create(
            venta_reserva=cls.venta1,
            servicio=cls.servicio1,
            fecha_agendamiento=cls.test_monday,
            hora_inicio='10:00', # Use string 'HH:MM'
            cantidad_personas=1
        )

        # No longer need to reconnect signal
        # pre_save.connect(validar_disponibilidad_admin, sender=ReservaServicio)

    def setUp(self):
        """Set up test client for each test."""
        self.client = Client()

    # --- Test Public Views ---
    def test_homepage_view_loads(self):
        """Test that the homepage loads correctly and shows public services."""
        url = reverse('homepage')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/homepage.html')
        self.assertContains(response, self.servicio1.nombre)
        self.assertNotContains(response, self.servicio_no_publicado.nombre) # Check non-public service isn't shown

    def test_category_detail_view_loads(self):
        """Test that the category detail page loads correctly."""
        url = reverse('categoria_detail', args=[self.categoria1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/category_detail.html')
        self.assertContains(response, self.categoria1.nombre)
        self.assertContains(response, self.servicio1.nombre)
        self.assertNotContains(response, self.servicio_no_publicado.nombre)

    def test_category_detail_view_404(self):
        """Test that a non-existent category returns 404."""
        url = reverse('categoria_detail', args=[999]) # Non-existent ID
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- Test Availability Views ---
    # Removed mock - using fixed date cls.test_monday now
    def test_get_available_hours_success(self):
        """Test getting available hours for a service on a specific date."""
        url = reverse('get_available_hours')
        # Use the fixed Monday date from setUpTestData
        response = self.client.get(url, {'servicio_id': self.servicio1.id, 'fecha': self.test_monday.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        # 10:00 is booked by self.reserva_existente
        expected_data = {'success': True, 'horas_disponibles': ['11:00']}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_data)

    def test_get_available_hours_no_slots_defined(self):
        """Test getting hours when no slots are defined for the day."""
        test_wednesday = date(2024, 6, 5) # Example Wednesday (no slots defined in model)
        url = reverse('get_available_hours')
        response = self.client.get(url, {'servicio_id': self.servicio1.id, 'fecha': test_wednesday.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        expected_data = {'success': True, 'horas_disponibles': []}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_data)

    def test_get_available_hours_missing_params(self):
        """Test get_available_hours with missing parameters."""
        # Note: self.client is now set in setUp, not setUpTestData
        url = reverse('get_available_hours')
        response = self.client.get(url, {'servicio_id': self.servicio1.id}) # Missing fecha
        self.assertEqual(response.status_code, 400)
        response = self.client.get(url, {'fecha': '2024-01-01'}) # Missing servicio_id
        self.assertEqual(response.status_code, 400)

    def test_check_slot_availability_available(self):
        """Test checking an available slot."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': self.servicio1.id,
            'fecha': self.test_monday.strftime('%Y-%m-%d'), # Use fixed Monday
            'hora': '11:00' # This slot should be available
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'available': True})

    def test_check_slot_availability_booked(self):
        """Test checking a booked slot."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': self.servicio1.id,
            'fecha': self.test_monday.strftime('%Y-%m-%d'), # Use fixed Monday
            'hora': '10:00' # This slot is booked in setUpTestData
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'available': False})

    def test_check_slot_availability_invalid_service(self):
        """Test checking availability for a non-existent service."""
        # Note: self.client is now set in setUp, not setUpTestData
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': 999,
            'fecha': '2024-01-01',
            'hora': '10:00'
        })
        self.assertEqual(response.status_code, 404) # Should be 404 Not Found

    # --- Test CRUD Views (Basic) ---
    def test_venta_reserva_list_loads(self):
        """Test that the VentaReserva list view loads."""
        url = reverse('venta_reserva_list')
        # This view might require login, adjust if necessary
        # self.client.login(username='testuser', password='password') # Example login
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/venta_reserva_list.html')
        self.assertContains(response, self.venta1.cliente.nombre) # Check if data is present

    def test_venta_reserva_detail_loads(self):
        """Test that the VentaReserva detail view loads for an existing object."""
        url = reverse('venta_reserva_detail', args=[self.venta1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/venta_reserva_detail.html')
        self.assertContains(response, self.venta1.cliente.nombre)

    def test_venta_reserva_detail_404(self):
        """Test that the VentaReserva detail view returns 404 for non-existent object."""
        url = reverse('venta_reserva_detail', args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- Test Checkout Views (Basic Cart) ---
    def test_add_to_cart(self):
        """Test adding an item to the cart via POST request."""
        url = reverse('add_to_cart')
        test_date = '2024-07-15'
        test_time = '14:00'
        post_data = {
            'servicio_id': self.servicio1.id,
            'fecha': test_date,
            'hora': test_time,
            'cantidad_personas': 1
        }
        response = self.client.post(url, post_data)
        self.assertRedirects(response, reverse('cart')) # Should redirect to cart

        # Check session data
        cart = self.client.session.get('cart')
        self.assertIsNotNone(cart)
        self.assertEqual(len(cart['servicios']), 1)
        self.assertEqual(cart['servicios'][0]['id'], self.servicio1.id)
        self.assertEqual(cart['servicios'][0]['fecha'], test_date)
        self.assertEqual(cart['servicios'][0]['hora'], test_time)
        self.assertEqual(cart['total'], self.servicio1.precio_base)

    def test_remove_from_cart(self):
        """Test removing an item from the cart."""
        # First, add an item
        add_url = reverse('add_to_cart')
        self.client.post(add_url, {
            'servicio_id': self.servicio1.id,
            'fecha': '2024-07-15',
            'hora': '14:00',
            'cantidad_personas': 1
        })
        cart = self.client.session.get('cart')
        self.assertEqual(len(cart['servicios']), 1)

        # Now, remove it
        remove_url = reverse('remove_from_cart')
        response = self.client.post(remove_url, {'index': 0}) # Remove the first item (index 0)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'success': True})

        # Check session data again
        cart = self.client.session.get('cart')
        self.assertEqual(len(cart['servicios']), 0)
        self.assertEqual(cart['total'], 0)

    def test_cart_view_loads(self):
        """Test that the cart view loads."""
        url = reverse('cart')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/cart.html')

    def test_checkout_view_loads(self):
        """Test that the checkout view loads."""
        # Add something to cart first, as checkout might expect it
        self.client.post(reverse('add_to_cart'), {
            'servicio_id': self.servicio1.id,
            'fecha': '2024-07-15',
            'hora': '14:00',
            'cantidad_personas': 1
        })
        url = reverse('checkout')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/checkout.html')
        self.assertContains(response, 'flow') # Check if payment method is shown

    # --- Test Flow Views (Mocking External API) ---

    @patch('ventas.views.flow_views.requests.post')
    def test_create_flow_payment_success(self, mock_post):
        """Test successful Flow payment creation."""
        # Configure the mock response from Flow API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'url': 'https://flow.cl/payment/pay',
            'token': 'someflowtoken123'
        }
        mock_post.return_value = mock_response

        url = reverse('create_flow_payment')
        data = json.dumps({'reserva_id': self.venta1.id})
        response = self.client.post(url, data, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {
            'url': 'https://flow.cl/payment/pay?token=someflowtoken123',
            'token': 'someflowtoken123'
        })
        mock_post.assert_called_once() # Check that requests.post was called

    @patch('ventas.views.flow_views.requests.post')
    def test_create_flow_payment_api_error(self, mock_post):
        """Test Flow payment creation when Flow API returns an error."""
        mock_response = MagicMock()
        mock_response.status_code = 400 # Simulate Flow error
        mock_response.json.return_value = {'code': 123, 'message': 'Invalid API Key'}
        # Simulate raise_for_status() behavior for bad status codes
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error")
        mock_post.return_value = mock_response

        url = reverse('create_flow_payment')
        data = json.dumps({'reserva_id': self.venta1.id})
        response = self.client.post(url, data, content_type='application/json')

        self.assertEqual(response.status_code, 502) # Bad Gateway as we couldn't reach Flow properly
        self.assertIn('Flow API request failed', str(response.content, encoding='utf8'))

    @patch('ventas.views.flow_views.requests.get')
    def test_flow_confirmation_success(self, mock_get):
        """Test successful Flow confirmation webhook processing."""
        # Mock the getStatus response from Flow
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'flowOrder': 9876,
            'commerceOrder': str(self.venta1.id), # Link back to our reservation
            'requestDate': '2024-06-04 10:00:00',
            'status': 2, # Paid
            'subject': f'Reserva Aremko #{self.venta1.id}',
            'currency': 'CLP',
            'amount': str(int(self.venta1.total)),
            'payer': 'test@payer.com',
            'optional': {},
            'pending_info': None,
            'paymentData': {'date': '2024-06-04 10:01:00', 'media': 'WebPay', 'fee': '0', 'balance': '0'},
            'merchantId': 'FlowMerchantID'
        }
        mock_get.return_value = mock_response

        url = reverse('flow_confirmation')
        # Simulate POST data from Flow
        post_data = {'token': 'validconfirmationtoken'}
        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Payment Confirmed")

        # Verify Pago object was created and VentaReserva status updated
        self.venta1.refresh_from_db()
        self.assertTrue(Pago.objects.filter(venta_reserva=self.venta1, metodo_pago='flow').exists())
        self.assertEqual(self.venta1.estado_pago, 'pagado')
        mock_get.assert_called_once() # Check getStatus was called

    # Add more tests for flow_confirmation (rejected status, invalid token, etc.)
    # Add tests for flow_return view

    # Add tests for other view modules (reporting, import/export, misc, api) later

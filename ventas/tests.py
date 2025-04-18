from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json
from datetime import date, time, datetime # Added datetime
import requests # Needed for mocking flow error

# Import models needed for setup
from .models import (
    CategoriaServicio, Servicio, Cliente, VentaReserva, ReservaServicio, Pago,
    Lead, Contact, Company, Campaign, Deal, Activity, User, Producto # Added Producto
)
from django.contrib.admin.sites import AdminSite # For testing admin actions
from .admin import LeadAdmin # Import LeadAdmin
from django.contrib.messages.storage.fallback import FallbackStorage # For mocking messages
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.test import override_settings # Import override_settings
# Import signals and relevant models/senders for disconnecting
from . import signals
from django.db.models.signals import post_save, pre_delete
# Need to import messages module for the assertion in admin action test
from django.contrib import messages as messages_module

# Import view functions directly for potential direct testing if needed,
# but primarily test through URLs using the client.
# from .views import public_views, availability_views, flow_views, checkout_views, crud_views

class VentasViewTests(TestCase):

    _movement_signals_disconnected = False # Class attribute to track disconnection status

    @classmethod
    def setUpClass(cls):
        """Set up test data once for the class and disconnect signals."""
        super().setUpClass()

        # Store signals to disconnect/reconnect (Commented out MovimientoCliente signals)
        cls._movement_signals_to_manage = [
            # (post_save, signals.registrar_movimiento_venta, VentaReserva),
            # (post_save, signals.registrar_movimiento_cliente, Cliente),
            # (post_save, signals.registrar_movimiento_reserva_producto, ReservaProducto),
            # (post_save, signals.registrar_movimiento_reserva_servicio, ReservaServicio),
            # (post_save, signals.registrar_movimiento_pago, Pago),
            # (pre_delete, signals.registrar_movimiento_eliminacion_venta, VentaReserva),
            # (pre_delete, signals.registrar_movimiento_eliminacion_cliente, Cliente),
            # (pre_delete, signals.registrar_movimiento_eliminacion_producto, ReservaProducto),
            # (pre_delete, signals.registrar_movimiento_eliminacion_servicio, ReservaServicio),
            # (pre_delete, signals.registrar_movimiento_eliminacion_pago, Pago),
        ]

        # Disconnect signals (Only if list is not empty)
        for signal_obj, receiver_func, sender_model in cls._movement_signals_to_manage:
            dispatch_uid = f"{cls.__name__}_{receiver_func.__name__}_{sender_model.__name__}"
            signal_obj.disconnect(receiver=receiver_func, sender=sender_model, dispatch_uid=dispatch_uid)
        cls._movement_signals_disconnected = True


        # --- Original setUpTestData content ---
        cls.user = User.objects.create_user(username='defaulttestuser', password='password')
        cls.categoria1 = CategoriaServicio.objects.create(nombre="Masajes")
        cls.servicio1 = Servicio.objects.create(
            nombre="Masaje Descontracturante",
            precio_base=30000,
            duracion=60,
            categoria=cls.categoria1,
            activo=True,
            publicado_web=True,
            slots_disponibles={"monday": ["10:00", "11:00"], "tuesday": ["14:00"]}
        )
        cls.servicio_no_publicado = Servicio.objects.create(
            nombre="Masaje Secreto",
            duracion=30,
            precio_base=50000,
            categoria=cls.categoria1,
            activo=True,
            publicado_web=False
        )
        cls.cliente1 = Cliente.objects.create(nombre="Juan Perez", telefono="987654321", email="juan@test.com")
        cls.venta1 = VentaReserva.objects.create(cliente=cls.cliente1, total=30000, fecha_reserva=timezone.now())
        cls.test_monday = date(2024, 6, 3)
        cls.reserva_existente = ReservaServicio.objects.create(
            venta_reserva=cls.venta1,
            servicio=cls.servicio1,
            fecha_agendamiento=cls.test_monday,
            hora_inicio='10:00',
            cantidad_personas=1
        )
        # --- End of Original setUpTestData content ---

    @classmethod
    def tearDownClass(cls):
        """Reconnect signals after tests in this class are done."""
        # Reconnect signals only if they were disconnected and the list is not empty
        if hasattr(cls, '_movement_signals_to_manage') and cls._movement_signals_disconnected and cls._movement_signals_to_manage:
             for signal_obj, receiver_func, sender_model in cls._movement_signals_to_manage:
                 dispatch_uid = f"{cls.__name__}_{receiver_func.__name__}_{sender_model.__name__}"
                 # Use weak=False if signals were originally connected without it
                 signal_obj.connect(receiver=receiver_func, sender=sender_model, weak=False, dispatch_uid=dispatch_uid)

        super().tearDownClass() # Ensure parent tearDownClass runs

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
        self.assertNotContains(response, self.servicio_no_publicado.nombre)

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
        url = reverse('categoria_detail', args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- Test Availability Views ---
    def test_get_available_hours_success(self):
        """Test getting available hours for a service on a specific date."""
        url = reverse('get_available_hours')
        response = self.client.get(url, {'servicio_id': self.servicio1.id, 'fecha': self.test_monday.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        expected_data = {'success': True, 'horas_disponibles': ['11:00']}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_data)

    def test_get_available_hours_no_slots_defined(self):
        """Test getting hours when no slots are defined for the day."""
        test_wednesday = date(2024, 6, 5)
        url = reverse('get_available_hours')
        response = self.client.get(url, {'servicio_id': self.servicio1.id, 'fecha': test_wednesday.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        expected_data = {'success': True, 'horas_disponibles': []}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_data)

    def test_get_available_hours_missing_params(self):
        """Test get_available_hours with missing parameters."""
        url = reverse('get_available_hours')
        response = self.client.get(url, {'servicio_id': self.servicio1.id})
        self.assertEqual(response.status_code, 400)
        response = self.client.get(url, {'fecha': '2024-01-01'})
        self.assertEqual(response.status_code, 400)

    def test_check_slot_availability_available(self):
        """Test checking an available slot."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': self.servicio1.id,
            'fecha': self.test_monday.strftime('%Y-%m-%d'),
            'hora': '11:00'
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'available': True})

    def test_check_slot_availability_booked(self):
        """Test checking a booked slot."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': self.servicio1.id,
            'fecha': self.test_monday.strftime('%Y-%m-%d'),
            'hora': '10:00'
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'available': False})

    def test_check_slot_availability_invalid_service(self):
        """Test checking availability for a non-existent service."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': 999,
            'fecha': '2024-01-01',
            'hora': '10:00'
        })
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False) # Ensure DEBUG is False for this test
    def test_check_slot_availability_invalid_service(self):
        """Test checking availability for a non-existent service."""
        url = reverse('check_slot_availability')
        response = self.client.get(url, {
            'servicio_id': 999,
            'fecha': '2024-01-01',
            'hora': '10:00'
        })
        self.assertEqual(response.status_code, 404) # Should now correctly receive 404

    # --- Test CRUD Views (Basic) ---
    def test_venta_reserva_list_loads(self):
        """Test that the VentaReserva list view loads."""
        url = reverse('venta_reserva_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ventas/venta_reserva_list.html')
        self.assertContains(response, self.venta1.cliente.nombre)

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
        self.assertRedirects(response, reverse('cart'))
        cart = self.client.session.get('cart')
        self.assertIsNotNone(cart)
        self.assertEqual(len(cart['servicios']), 1)
        self.assertEqual(cart['servicios'][0]['id'], self.servicio1.id)
        self.assertEqual(cart['servicios'][0]['fecha'], test_date)
        self.assertEqual(cart['servicios'][0]['hora'], test_time)
        self.assertEqual(cart['total'], self.servicio1.precio_base)

    def test_remove_from_cart(self):
        """Test removing an item from the cart."""
        add_url = reverse('add_to_cart')
        self.client.post(add_url, {
            'servicio_id': self.servicio1.id,
            'fecha': '2024-07-15',
            'hora': '14:00',
            'cantidad_personas': 1
        })
        remove_url = reverse('remove_from_cart')
        response = self.client.post(remove_url, {'index': 0})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'success': True})
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
        self.assertContains(response, 'flow')

    # --- Test Flow Views (Mocking External API) ---

    @patch('ventas.views.flow_views.requests.post')
    def test_create_flow_payment_success(self, mock_post):
        """Test successful Flow payment creation."""
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
        mock_post.assert_called_once()

    @patch('ventas.views.flow_views.requests.post')
    def test_create_flow_payment_api_error(self, mock_post):
        """Test Flow payment creation when Flow API returns an error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'code': 123, 'message': 'Invalid API Key'}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error")
        mock_post.return_value = mock_response
        url = reverse('create_flow_payment')
        data = json.dumps({'reserva_id': self.venta1.id})
        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, 502)
        self.assertIn('Flow API request failed', str(response.content, encoding='utf8'))

    @patch('ventas.views.flow_views.requests.get')
    def test_flow_confirmation_success(self, mock_get):
        """Test successful Flow confirmation webhook processing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'flowOrder': 9876,
            'commerceOrder': str(self.venta1.id),
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
        post_data = {'token': 'validconfirmationtoken'}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Payment Confirmed")
        self.venta1.refresh_from_db()
        # Check Pago exists (signal is disconnected, so check view logic created it)
        # self.assertTrue(Pago.objects.filter(venta_reserva=self.venta1, metodo_pago='flow').exists())
        self.assertEqual(self.venta1.estado_pago, 'pagado')
        mock_get.assert_called_once()

# --- CRM Model Tests ---

class CRMModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.campaign = Campaign.objects.create(name="Summer Sale", status='Active')
        cls.company = Company.objects.create(name="Test Corp")
        cls.lead = Lead.objects.create(
            first_name="Test", last_name="Lead", email="testlead@example.com", status='New', campaign=cls.campaign
        )
        cls.contact = Contact.objects.create(
            first_name="Test", last_name="Contact", email="testcontact@example.com", company=cls.company, linked_user=cls.user
        )
        cls.deal = Deal.objects.create(
            name="Big Deal", contact=cls.contact, stage='Prospecting', amount=50000, campaign=cls.campaign
        )
        cls.cliente_crm = Cliente.objects.create(nombre="CRM Client", telefono="11223344", email="crm@client.com")
        cls.venta_crm = VentaReserva.objects.create(cliente=cls.cliente_crm, total=10000)
        cls.deal_with_booking = Deal.objects.create(
            name="Deal with Booking", contact=cls.contact, stage='Closed Won', amount=10000, related_booking=cls.venta_crm
        )

    def test_campaign_creation(self):
        self.assertEqual(self.campaign.name, "Summer Sale")
        self.assertEqual(str(self.campaign), "Summer Sale")

    def test_lead_creation(self):
        self.assertEqual(self.lead.email, "testlead@example.com")
        self.assertEqual(str(self.lead), "Test Lead (testlead@example.com)")
        self.assertEqual(self.lead.campaign, self.campaign)

    def test_company_creation(self):
        self.assertEqual(self.company.name, "Test Corp")
        self.assertEqual(str(self.company), "Test Corp")

    def test_contact_creation(self):
        self.assertEqual(self.contact.email, "testcontact@example.com")
        self.assertEqual(str(self.contact), "Test Contact (testcontact@example.com)")
        self.assertEqual(self.contact.company, self.company)
        self.assertEqual(self.contact.linked_user, self.user)

    def test_deal_creation(self):
        self.assertEqual(self.deal.name, "Big Deal")
        self.assertEqual(str(self.deal), f"Deal: Big Deal for {self.contact}")
        self.assertEqual(self.deal.contact, self.contact)
        self.assertEqual(self.deal.campaign, self.campaign)
        self.assertEqual(self.deal_with_booking.related_booking, self.venta_crm)

    def test_activity_creation(self):
        activity = Activity.objects.create(
            activity_type='Call', subject="Initial Call", related_lead=self.lead, created_by=self.user
        )
        self.assertEqual(activity.subject, "Initial Call")
        self.assertEqual(str(activity), f"Call: Initial Call ({self.lead})")
        self.assertEqual(activity.related_lead, self.lead)
        self.assertEqual(activity.created_by, self.user)

    def test_activity_clean_validation(self):
        """Test that Activity clean method prevents linking multiple objects."""
        activity = Activity(
            activity_type='Meeting',
            subject="Multi-link test",
            related_lead=self.lead,
            related_contact=self.contact
        )
        with self.assertRaises(ValidationError):
            activity.clean()

        activity_deal = Activity(
            activity_type='Meeting',
            subject="Multi-link test 2",
            related_contact=self.contact,
            related_deal=self.deal
        )
        with self.assertRaises(ValidationError):
            activity_deal.clean()

        activity_valid = Activity(
            activity_type='Note Added',
            subject="Single link",
            related_deal=self.deal
        )
        try:
            activity_valid.clean()
        except ValidationError:
            self.fail("Activity.clean() raised ValidationError unexpectedly for single link.")

    def test_campaign_roi_methods(self):
        """Test the ROI calculation methods on the Campaign model."""
        self.assertEqual(self.campaign.get_associated_leads_count(), 1)
        self.assertEqual(self.campaign.get_won_deals_count(), 0)
        self.assertEqual(self.campaign.get_won_deals_value(), 0)
        self.deal.stage = 'Closed Won'
        self.deal.save()
        self.assertEqual(self.campaign.get_won_deals_count(), 1)
        self.assertEqual(self.campaign.get_won_deals_value(), 50000)


# --- CRM Signal Tests ---

class CRMSignalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.lead_new = Lead.objects.create(first_name="Signal", last_name="Test", email="signal@test.com", status='New')
        self.lead_contacted = Lead.objects.create(first_name="Already", last_name="Contacted", email="contacted@test.com", status='Contacted')

    def test_lead_status_update_on_activity_signal(self):
        """Test that lead status changes from New to Contacted when a relevant activity is created."""
        Activity.objects.create(
            activity_type='Call',
            subject="First call",
            related_lead=self.lead_new,
            created_by=self.user
        )
        self.lead_new.refresh_from_db()
        self.assertEqual(self.lead_new.status, 'Contacted')

    def test_lead_status_no_update_if_not_new(self):
        """Test that lead status does not change if it's not 'New'."""
        Activity.objects.create(
            activity_type='Call',
            subject="Follow-up call",
            related_lead=self.lead_contacted,
            created_by=self.user
        )
        self.lead_contacted.refresh_from_db()
        self.assertEqual(self.lead_contacted.status, 'Contacted')

    def test_lead_status_no_update_on_irrelevant_activity(self):
        """Test that lead status does not change for irrelevant activity types."""
        Activity.objects.create(
            activity_type='Note Added',
            subject="Internal note",
            related_lead=self.lead_new,
            created_by=self.user
        )
        self.lead_new.refresh_from_db()
        self.assertEqual(self.lead_new.status, 'New')


# --- CRM Admin Action Tests ---

class CRMAdminActionTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.lead_admin = LeadAdmin(Lead, self.site)
        self.user = User.objects.create_superuser(username='admin', password='password', email='admin@test.com')
        self.client.login(username='admin', password='password')

        self.lead_qualified = Lead.objects.create(first_name="Qual", last_name="Lead", email="qual@test.com", status='Qualified')
        self.lead_new = Lead.objects.create(first_name="New", last_name="Lead", email="new@test.com", status='New')
        self.lead_converted = Lead.objects.create(first_name="Conv", last_name="Lead", email="conv@test.com", status='Converted')
        self.lead_qual_existing_contact = Lead.objects.create(first_name="Existing", last_name="ContactLead", email="existing@contact.com", status='Qualified')
        Contact.objects.create(first_name="Already", last_name="Exists", email="existing@contact.com")

    def test_convert_to_contact_admin_action(self):
        """Test the 'convert_to_contact' admin action."""
        queryset = Lead.objects.filter(pk__in=[self.lead_qualified.pk, self.lead_new.pk, self.lead_qual_existing_contact.pk])
        request = self.client.request().wsgi_request
        request.user = self.user
        setattr(request, '_messages', FallbackStorage(request))
        self.lead_admin.convert_to_contact(request, queryset)

        self.lead_qualified.refresh_from_db()
        self.assertEqual(self.lead_qualified.status, 'Converted')
        self.assertTrue(Contact.objects.filter(email=self.lead_qualified.email).exists())
        self.assertTrue(Deal.objects.filter(contact__email=self.lead_qualified.email).exists())
        self.assertTrue(Activity.objects.filter(related_lead=self.lead_qualified, activity_type='Status Change').exists())

        self.lead_new.refresh_from_db()
        self.assertEqual(self.lead_new.status, 'New')
        self.assertFalse(Contact.objects.filter(email=self.lead_new.email).exists())

        self.lead_qual_existing_contact.refresh_from_db()
        self.assertEqual(self.lead_qual_existing_contact.status, 'Qualified')
        self.assertEqual(Contact.objects.filter(email=self.lead_qual_existing_contact.email).count(), 1)

        messages = list(request._messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].level, messages_module.WARNING)
        self.assertIn(f"Contact with email {self.lead_qual_existing_contact.email} already exists", messages[0].message)
        self.assertEqual(messages[1].level, messages_module.SUCCESS)
        self.assertIn("1 qualified leads converted successfully", messages[1].message)

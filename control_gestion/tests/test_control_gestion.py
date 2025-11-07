"""
Tests para Control de Gestión

Tests de:
- Regla WIP=1 (Work In Progress = 1)
- Prioridad ALTA va a top de cola
- Creación de logs automáticos
- QA al cerrar tarea
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from control_gestion.models import (
    Task, ChecklistItem, TaskLog,
    Swimlane, TaskState, Priority, TaskSource
)

User = get_user_model()


class WIPOneRuleTestCase(TestCase):
    """Tests para la regla WIP=1"""
    
    def setUp(self):
        """Crear usuarios de prueba"""
        self.user1 = User.objects.create_user(username='ops', password='test123')
        self.user2 = User.objects.create_user(username='recep', password='test123')
    
    def test_wip_one_enforcement(self):
        """Test: No se puede tener más de una tarea EN CURSO por usuario"""
        
        # Crear primera tarea
        task1 = Task.objects.create(
            title="Tarea 1",
            description="Primera tarea",
            swimlane=Swimlane.OPERACION,
            owner=self.user1,
            created_by=self.user1,
            state=TaskState.BACKLOG
        )
        
        # Marcar como EN CURSO
        task1.state = TaskState.IN_PROGRESS
        task1.save()  # Debe funcionar sin problema
        
        # Crear segunda tarea para el mismo usuario
        task2 = Task.objects.create(
            title="Tarea 2",
            description="Segunda tarea",
            swimlane=Swimlane.OPERACION,
            owner=self.user1,
            created_by=self.user1,
            state=TaskState.BACKLOG
        )
        
        # Intentar marcar la segunda como EN CURSO
        task2.state = TaskState.IN_PROGRESS
        
        # Debe fallar por WIP=1
        with self.assertRaises(ValidationError) as context:
            task2.save()
        
        self.assertIn("WIP=1", str(context.exception))
    
    def test_wip_one_different_users(self):
        """Test: Usuarios diferentes pueden tener tareas EN CURSO simultáneamente"""
        
        # Usuario 1 con tarea EN CURSO
        task1 = Task.objects.create(
            title="Tarea User1",
            description="Tarea de usuario 1",
            swimlane=Swimlane.OPERACION,
            owner=self.user1,
            created_by=self.user1,
            state=TaskState.IN_PROGRESS
        )
        
        # Usuario 2 con tarea EN CURSO
        task2 = Task.objects.create(
            title="Tarea User2",
            description="Tarea de usuario 2",
            swimlane=Swimlane.RECEPCION,
            owner=self.user2,
            created_by=self.user2,
            state=TaskState.IN_PROGRESS
        )
        
        # Ambas deben existir sin problema
        self.assertEqual(Task.objects.filter(state=TaskState.IN_PROGRESS).count(), 2)
    
    def test_wip_one_after_block(self):
        """Test: Después de bloquear una tarea, se puede iniciar otra"""
        
        # Crear y empezar tarea 1
        task1 = Task.objects.create(
            title="Tarea 1",
            description="Primera",
            swimlane=Swimlane.OPERACION,
            owner=self.user1,
            created_by=self.user1,
            state=TaskState.IN_PROGRESS
        )
        
        # Bloquear tarea 1
        task1.state = TaskState.BLOCKED
        task1.save()
        
        # Ahora debería poder iniciar tarea 2
        task2 = Task.objects.create(
            title="Tarea 2",
            description="Segunda",
            swimlane=Swimlane.OPERACION,
            owner=self.user1,
            created_by=self.user1,
            state=TaskState.IN_PROGRESS
        )
        
        # Debe funcionar
        self.assertEqual(task2.state, TaskState.IN_PROGRESS)


class PriorityTestCase(TestCase):
    """Tests para prioridades"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
    
    def test_alta_priority_goes_to_top(self):
        """Test: Prioridad ALTA debe ir a posición 1 automáticamente"""
        
        task = Task.objects.create(
            title="Urgente - Cliente en sitio",
            description="Atender inmediatamente",
            swimlane=Swimlane.RECEPCION,
            owner=self.user,
            created_by=self.user,
            priority=Priority.ALTA_CLIENTE_EN_SITIO,
            queue_position=10  # Aunque se especifique 10...
        )
        
        # Debe haberse cambiado a 1 automáticamente
        task.refresh_from_db()
        self.assertEqual(task.queue_position, 1)


class TaskLogTestCase(TestCase):
    """Tests para logs automáticos"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
    
    def test_log_created_on_task_creation(self):
        """Test: Se crea log automáticamente al crear tarea"""
        
        task = Task.objects.create(
            title="Nueva tarea",
            description="Descripción",
            swimlane=Swimlane.OPERACION,
            owner=self.user,
            created_by=self.user
        )
        
        # Debe haber un log CREATED
        logs = TaskLog.objects.filter(task=task, action="CREATED")
        self.assertTrue(logs.exists())
    
    def test_log_updated_on_task_change(self):
        """Test: Se crea log al actualizar tarea"""
        
        task = Task.objects.create(
            title="Tarea",
            description="Desc",
            swimlane=Swimlane.OPERACION,
            owner=self.user,
            created_by=self.user
        )
        
        # Cambiar el título
        task.title = "Tarea Actualizada"
        task.save()
        
        # Debe haber logs CREATED y UPDATED
        self.assertTrue(TaskLog.objects.filter(task=task, action="CREATED").exists())
        self.assertTrue(TaskLog.objects.filter(task=task, action="UPDATED").exists())


class QATestCase(TestCase):
    """Tests para QA automático"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
    
    def test_qa_on_done_without_checklist(self):
        """Test: QA al completar tarea sin checklist"""
        
        task = Task.objects.create(
            title="Tarea sin checklist",
            description="Desc",
            swimlane=Swimlane.OPERACION,
            owner=self.user,
            created_by=self.user,
            state=TaskState.BACKLOG
        )
        
        # Marcar como DONE
        task.state = TaskState.DONE
        task.save()
        
        # Debe haberse creado un log QA_RESULT
        qa_log = TaskLog.objects.filter(task=task, action="QA_RESULT").first()
        self.assertIsNotNone(qa_log)
        self.assertIn("Sin checklist", qa_log.note)
    
    def test_qa_on_done_with_complete_checklist(self):
        """Test: QA al completar tarea con checklist completo"""
        
        task = Task.objects.create(
            title="Tarea con checklist",
            description="Desc",
            swimlane=Swimlane.OPERACION,
            owner=self.user,
            created_by=self.user,
            state=TaskState.BACKLOG
        )
        
        # Agregar checklist
        ChecklistItem.objects.create(task=task, text="Paso 1", done=True)
        ChecklistItem.objects.create(task=task, text="Paso 2", done=True)
        
        # Marcar como DONE
        task.state = TaskState.DONE
        task.save()
        
        # Debe haberse creado un log QA_RESULT positivo
        qa_log = TaskLog.objects.filter(task=task, action="QA_RESULT").first()
        self.assertIsNotNone(qa_log)
        self.assertIn("Completo", qa_log.note)


class ChecklistTestCase(TestCase):
    """Tests para checklist items"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test123')
        self.task = Task.objects.create(
            title="Tarea de prueba",
            description="Descripción",
            swimlane=Swimlane.OPERACION,
            owner=self.user,
            created_by=self.user
        )
    
    def test_create_checklist_items(self):
        """Test: Crear items de checklist"""
        
        item1 = ChecklistItem.objects.create(
            task=self.task,
            text="Verificar temperatura",
            done=False
        )
        
        item2 = ChecklistItem.objects.create(
            task=self.task,
            text="Limpiar filtros",
            done=True
        )
        
        self.assertEqual(self.task.checklist.count(), 2)
        self.assertEqual(self.task.checklist.filter(done=True).count(), 1)
    
    def test_checklist_str_representation(self):
        """Test: Representación string del checklist"""
        
        item_todo = ChecklistItem.objects.create(
            task=self.task,
            text="Por hacer",
            done=False
        )
        
        item_done = ChecklistItem.objects.create(
            task=self.task,
            text="Completado",
            done=True
        )
        
        self.assertIn("□", str(item_todo))
        self.assertIn("✔", str(item_done))


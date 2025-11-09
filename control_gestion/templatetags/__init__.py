from django import template

register = template.Library()


@register.filter
def can_edit_task(task, user):
    """
    Verifica si un usuario puede editar una tarea
    
    Args:
        task: Instancia de Task
        user: Usuario actual
    
    Returns:
        bool: True si el usuario puede editar la tarea
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    # Verificar si está en grupo SUPERVISION
    try:
        if user.groups.filter(name='SUPERVISION').exists():
            return True
    except Exception:
        pass
    
    # Verificar si es el owner
    if task.owner and task.owner.id == user.id:
        return True
    
    return False


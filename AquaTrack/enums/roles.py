from enum import Enum

class Role(str, Enum):
    admin_global = "admin_global"      # Dueño del sistema
    admin_granja = "admin_granja"      # Admin principal de una o varias granjas
    biologo = "biologo"                # Biólogo designado (no admin principal)
    operador = "operador"              # Marca tareas como completadas
    consultor = "consultor"            # Solo lectura en dashboards/biometrías/proyecciones

# Paquete vacío a propósito.
# Antes hacía `from .X import *` de cada submódulo, lo que forzaba cargar TODO
# el paquete al importar cualquier submódulo, creando imports circulares
# (obligando a imports inline por todo el código). Vacío, cada submódulo se
# importa aislado y los imports pueden ir al inicio del archivo.

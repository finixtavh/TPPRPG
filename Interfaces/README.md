# Interfaces – Pruebas de concepto UI

Demos de interfaz para TPPRPG. **No modifican el juego**: son solo pruebas que puedes ejecutar y luego integrar si te gustan.

## Cómo ejecutar

Desde la raíz del proyecto:

```bash
python Interfaces/01_dashboard.py
python Interfaces/02_main_menu.py
python Interfaces/03_combat_ui.py
python Interfaces/04_inventory.py
python Interfaces/05_theme_dark.py
```

O desde `Interfaces/`:

```bash
cd Interfaces && python 01_dashboard.py
```

## Demos

| Archivo | Descripción |
|---------|-------------|
| **01_dashboard.py** | Estado del jugador: barras HP/MP/EXP, stats en columnas, zona actual. |
| **02_main_menu.py** | Menú principal agrupado (Explorar, Tienda, Personaje, Sistema) con cabecera y separadores. |
| **03_combat_ui.py** | Pantalla de combate: jugador vs enemigo en columnas, barras de vida/mana y acciones. |
| **04_inventory.py** | Inventario en tarjetas/lista con ítems, cantidades y categorías. |
| **05_theme_dark.py** | Tema oscuro alternativo y paleta de colores para consola. |

## Dependencias

Solo se usa **Rich** (ya en el proyecto). Si ejecutas los demos por separado, instala Rich si hace falta: `pip install rich`. Si ya corres el juego desde el mismo entorno, no necesitas nada más.

## Uso en el juego

Si quieres reutilizar algo:
- Copia el tema o los helpers de un demo a tu código.
- Los demos usan datos de ejemplo (nombre, HP, oro, etc.); en el juego sustituye por `player`, `enemy`, `vInventory`, etc.

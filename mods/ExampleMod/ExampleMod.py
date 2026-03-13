"""
Mod de Ejemplo - Sistema de archivos mejorado
==============================================
El mod lee sus datos de ExampleMod.json automáticamente
"""

def init_mod(api, mod_data):
    """
    Función principal del mod
    
    Args:
        api: ModAPI para registrar contenido
        mod_data: Datos del JSON del mod
    """
    print("\n" + "="*70)
    print("📦 Cargando: Example Mod v1.0.0")
    print("="*70)
    
    # Los datos ya están en mod_data, auto-inyectados
    # Pero puedes usarlos si necesitas lógica adicional
    
    # Registrar atributo de ejemplo
    api.register_player_attribute(
        attr_name="example_stat",
        default_value=0,
        description="Estadística de ejemplo"
    )
    
    # Registrar eventos
    def on_player_created(player):
        print(f"  [ExampleMod] ¡Jugador creado!")
        if hasattr(player, 'example_stat'):
            print(f"  [ExampleMod] example_stat inicializado: {player.example_stat}")
    
    api.register_event_handler("player_created", on_player_created)
    
    print("="*70)
    print("✅ Example Mod cargado!")
    print("   - 1 arma")
    print("   - 1 zona")
    print("   - 1 tienda")
    print("   - 1 atributo nuevo")
    print("="*70 + "\n")


def cleanup_mod():
    """Se llama al descargar el mod"""
    print("📦 Example Mod descargado")

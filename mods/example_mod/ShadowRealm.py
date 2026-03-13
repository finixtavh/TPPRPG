"""
Shadow Realm Expansion - Sistema de archivos mejorado
======================================================
Lee sus datos de ShadowRealm.json automáticamente
"""

def init_mod(api, mod_data):
    """
    Función principal del mod
    
    Args:
        api: ModAPI para registrar contenido
        mod_data: Datos del ShadowRealm.json (ya cargados)
    """
    print("\n" + "="*70)
    print("🌑 Cargando: Shadow Realm Expansion v1.0.0")
    print("="*70)
    
    # Los datos ya están auto-inyectados desde ShadowRealm.json
    # Solo necesitamos registrar atributos y eventos personalizados
    
    # 1. Registrar atributo "Oscuridad"
    register_player_attributes(api)
    
    # 2. Registrar eventos
    register_events(api)
    
    # 3. Mostrar resumen
    items_count = sum(len(items) for items in mod_data.get("items", {}).values())
    zones_count = len(mod_data.get("zones", {}))
    shops_count = len(mod_data.get("shops", {}))
    
    print("="*70)
    print("✅ Shadow Realm Expansion cargado!")
    print(f"   - {items_count} items (armas + armaduras)")
    print(f"   - {zones_count} zona nueva")
    print(f"   - {shops_count} tienda")
    print("   - Atributo nuevo: Oscuridad")
    print("="*70 + "\n")


def register_player_attributes(api):
    """Registra el atributo 'Oscuridad'"""
    api.register_player_attribute(
        attr_name="darkness",
        default_value=0,
        description="Poder de las sombras. +1% daño profundo, +0.5% resistencia profunda por punto"
    )
    print("  ✓ Atributo registrado: Oscuridad")


def register_events(api):
    """Registra manejadores de eventos"""
    
    # Evento: Cuando se crea el jugador
    def on_player_created(player):
        """Inicializa el atributo de oscuridad"""
        if not hasattr(player, 'darkness'):
            player.darkness = 0
        print(f"  [Shadow Realm] Atributo 'darkness' inicializado: {player.darkness}")
    
    api.register_event_handler("player_created", on_player_created)
    
    # Evento: Cuando un enemigo muere en Shadow Realm
    def on_enemy_killed(player, enemy, zone):
        """Aumenta oscuridad al matar enemigos del Shadow Realm"""
        if zone == "ShadowRealm":
            # Aumentar oscuridad según el enemigo
            darkness_gain = 1
            
            if "Señor" in enemy.NAME or "Lord" in enemy.NAME:
                darkness_gain = 5  # Boss da más oscuridad
            elif "Guardián" in enemy.NAME or "Guardian" in enemy.NAME:
                darkness_gain = 3
            
            player.darkness += darkness_gain
            print(f"  🌑 +{darkness_gain} Oscuridad (Total: {player.darkness})")
            
            # Bonus cada 10 puntos de oscuridad
            if player.darkness % 10 == 0 and player.darkness > 0:
                print(f"  ✨ ¡Nuevo nivel de oscuridad alcanzado! ({player.darkness})")
                print(f"     Bonus: +{player.darkness}% daño profundo")
    
    api.register_event_handler("enemy_killed", on_enemy_killed)
    
    # Evento: Cuando se equipa un item del mod
    def on_item_equipped(player, item):
        """Mensaje especial al equipar items del Shadow Realm"""
        shadow_items = [
            "Espada de las Sombras", "Daga del Vacío", "Báculo del Eclipse",
            "Armadura del Abismo", "Casco de Obsidiana Oscura", "Botas del Caminante Sombrío"
        ]
        
        if hasattr(item, 'name') and item.name in shadow_items:
            print(f"  🌑 El poder de las sombras fluye a través de {item.name}")
            # Bonus temporal de oscuridad al equipar
            if hasattr(player, 'darkness'):
                player.darkness += 1
                print(f"     +1 Oscuridad permanente (Total: {player.darkness})")
    
    api.register_event_handler("item_equipped", on_item_equipped)
    
    # Evento: Al entrar a la zona
    def on_zone_entered(player, zone_name):
        """Mensaje al entrar al Shadow Realm"""
        if zone_name == "ShadowRealm":
            print("\n" + "="*70)
            print("🌑 Has entrado al Reino de las Sombras...")
            print("   La oscuridad te envuelve. Cuidado con lo que acecha aquí.")
            if hasattr(player, 'darkness'):
                print(f"   Tu oscuridad actual: {player.darkness}")
            print("="*70 + "\n")
    
    api.register_event_handler("zone_entered", on_zone_entered)
    
    print("  ✓ 4 event handlers registrados")


def cleanup_mod():
    """Se llama cuando el mod se descarga"""
    print("🌑 Shadow Realm Expansion descargado")

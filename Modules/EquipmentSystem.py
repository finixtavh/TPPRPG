from Modules.input_utils import wait_for_enter, interactive_menu_select

class EquipmentManager:
    """
    Gestor de equipamiento que maneja la aplicación y remoción de stats
    de forma dinámica cuando se equipan/desequipan items.
    """
    
    # Definir los slots válidos de equipamiento
    VALID_SLOTS = {
        "Weapon": "weapon",
        "Helmet": "helmet", 
        "Armor": "armor",
        "Boots": "boots",
        "Ring": ["ring", "ring2", "ring3"]  # Múltiples slots para anillos
    }
    
    @staticmethod
    def get_item_stats(item):
        """
        Extrae todos los stats que un item proporciona.
        
        Args:
            item: El item del cual extraer stats
            
        Returns:
            Dict con los stats que el item proporciona
        """
        stats = {}
        
        # Para items equipables (cEquippableItems)
        if hasattr(item, 'Defense'):
            stats['DEF'] = item.Defense
            
        if hasattr(item, 'HealthBoost') and item.HealthBoost > 0:
            stats['Health_max'] = item.HealthBoost
            
        if hasattr(item, 'DmgBoost') and item.DmgBoost > 0:
            stats['DmgBoost'] = item.DmgBoost
            
        if hasattr(item, 'HealthSteal') and item.HealthSteal > 0:
            stats['HealthSteal'] = item.HealthSteal
        
        # Para armas (cWeapon) - no aplicamos stats automáticamente,
        # el daño ya se calcula en el método attack()
        
        return stats
    
    @staticmethod
    def apply_item_stats(player, item):
        """
        Aplica los stats de un item al jugador.
        
        Args:
            player: El objeto jugador
            item: El item a aplicar
        """
        stats = EquipmentManager.get_item_stats(item)
        
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        for stat_name, stat_value in stats.items():
            if stat_name == 'DEF':
                print(f"  + Defensa:")
                for i in range(min(5, len(stat_value))):
                    if stat_value[i] > 0:
                        player.DEF[i] += stat_value[i]
                        print(f"    - {damage_type_names[i]}: +{stat_value[i]}")
            elif hasattr(player, stat_name):
                current_value = getattr(player, stat_name)
                setattr(player, stat_name, current_value + stat_value)
                print(f"  + {stat_name}: +{stat_value}")
        
        # Marcar el item como aplicado
        if hasattr(item, 'AppliedStats'):
            item.AppliedStats = True
    
    @staticmethod
    def remove_item_stats(player, item):
        """
        Remueve los stats de un item del jugador.
        
        Args:
            player: El objeto jugador
            item: El item a remover
        """
        if not hasattr(item, 'AppliedStats') or not item.AppliedStats:
            return  # El item no estaba aplicado
            
        stats = EquipmentManager.get_item_stats(item)
        
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        for stat_name, stat_value in stats.items():
            if stat_name == 'DEF':
                print(f"  - Defensa:")
                for i in range(min(5, len(stat_value))):
                    if stat_value[i] > 0:
                        player.DEF[i] -= stat_value[i]
                        print(f"    - {damage_type_names[i]}: -{stat_value[i]}")
            elif hasattr(player, stat_name):
                current_value = getattr(player, stat_name)
                setattr(player, stat_name, current_value - stat_value)
                print(f"  - {stat_name}: -{stat_value}")
        
        # Marcar el item como no aplicado
        item.AppliedStats = False
    
    @staticmethod
    def find_available_ring_slot(player):
        """
        Encuentra el primer slot de anillo disponible.
        
        Returns:
            Nombre del slot disponible o None si todos están ocupados
        """
        for slot in ["ring", "ring2", "ring3"]:
            if getattr(player, slot, None) is None:
                return slot
        return None
    
    @staticmethod
    def equip_item(player, item, inventory=None):
        """
        Equipa un item en el jugador, desequipando el anterior si existe.
        
        Args:
            player: El objeto jugador
            item: El item a equipar
            inventory: El inventario donde guardar items desequipados (opcional)
            
        Returns:
            True si se equipó correctamente, False en caso contrario
        """
        # Manejo especial para herramientas (cTool)
        from Modules.GatheringMasterySystem import cTool
        if isinstance(item, cTool):
            current_tool = getattr(player, "tool", None)
            if current_tool is not None:
                tool_name = current_tool.Name if hasattr(current_tool, "Name") else str(current_tool)
                print(f"\nDesequipando {tool_name}...")
                if inventory is not None:
                    inventory.addObject(current_tool)
            item_name = item.Name if hasattr(item, "Name") else str(item)
            print(f"\nEquipando {item_name}...")
            player.tool = item
            print(f"\u2713 {item_name} equipado en herramienta!")
            return True

        # Manejo especial para armas (cWeapon, que no tiene objectcheck)
        from Modules.setup import cWeapon
        if isinstance(item, cWeapon):
            current_weapon = getattr(player, "weapon", None)
            if current_weapon is not None:
                w_name = current_weapon.Name if hasattr(current_weapon, "Name") else current_weapon.name
                print(f"\nDesequipando {w_name}...")
                if inventory is not None:
                    inventory.addObject(current_weapon)
            item_name = item.Name if hasattr(item, "Name") else item.name
            print(f"\nEquipando {item_name}...")
            player.weapon = item
            print(f"\u2713 {item_name} equipado en weapon!")
            return True

        if not hasattr(item, 'objectcheck'):
            print(f"Error: {item.Name if hasattr(item, 'Name') else 'Item'} no es equipable")
            return False
        
        item_type = item.objectcheck
        
        # Determinar el slot a usar
        if item_type == "Ring":
            # Mostrar men\u00fa interactivo para elegir slot de anillo
            ring_slots_list = ["ring", "ring2", "ring3"]
            ring_options = []
            default_slot = 1
            first_empty_found = False
            for i, rslot in enumerate(ring_slots_list, 1):
                current_r = getattr(player, rslot, None)
                if current_r is not None:
                    cur_rname = current_r.Name if hasattr(current_r, "Name") else current_r.name
                    ring_options.append((i, f"Slot {i}: {cur_rname}  (reemplazar)"))
                else:
                    ring_options.append((i, f"Slot {i}: [Vac\u00edo]"))
                    if not first_empty_found:
                        default_slot = i
                        first_empty_found = True
            ring_options.append((0, "Cancelar"))

            slot_choice = interactive_menu_select(
                title="\u00bfEn qu\u00e9 slot equipar el anillo?",
                subtitle="Selecciona una posici\u00f3n para el anillo",
                options=ring_options,
                prompt="Slot: ",
                default_value=default_slot,
                border_style="yellow",
            )
            if slot_choice == 0:
                return False
            slot_name = ring_slots_list[slot_choice - 1]
        elif item_type in ["Weapon", "Helmet", "Armor", "Boots"]:
            slot_name = EquipmentManager.VALID_SLOTS[item_type]
        else:
            print(f"Tipo de item desconocido: {item_type}")
            return False
        
        # Obtener el item actualmente equipado
        current_item = getattr(player, slot_name, None)
        
        # Si hay algo equipado, desequiparlo primero
        if current_item is not None:
            print(f"\nDesequipando {current_item.Name if hasattr(current_item, 'Name') else current_item.name}...")
            EquipmentManager.remove_item_stats(player, current_item)
            
            # Agregar al inventario si se proporcionó
            if inventory is not None:
                inventory.addObject(current_item)
        
        # Equipar el nuevo item
        print(f"\nEquipando {item.Name if hasattr(item, 'Name') else item.name}...")
        setattr(player, slot_name, item)
        
        # Aplicar stats del nuevo item
        EquipmentManager.apply_item_stats(player, item)
        
        print(f"✓ {item.Name if hasattr(item, 'Name') else item.name} equipado en {slot_name}!")
        return True
    
    @staticmethod
    def unequip_item(player, slot_name, inventory=None):
        """
        Desequipa un item de un slot específico.
        
        Args:
            player: El objeto jugador
            slot_name: Nombre del slot a desequipar (weapon, helmet, armor, etc.)
            inventory: El inventario donde guardar el item (opcional)
            
        Returns:
            El item desequipado o None
        """
        if not hasattr(player, slot_name):
            print(f"Slot '{slot_name}' no válido")
            return None
        
        current_item = getattr(player, slot_name, None)
        
        if current_item is None:
            print(f"No hay nada equipado en {slot_name}")
            return None
        
        print(f"\nDesequipando {current_item.Name if hasattr(current_item, 'Name') else current_item.name}...")
        
        # Remover stats
        EquipmentManager.remove_item_stats(player, current_item)
        
        # Quitar del slot
        setattr(player, slot_name, None)
        
        # Agregar al inventario si se proporcionó
        if inventory is not None:
            inventory.addObject(current_item)
        
        print(f"✓ {slot_name} desequipado!")
        return current_item
    
    @staticmethod
    def show_equipment(player):
        """
        Muestra todo el equipamiento actual del jugador con sus stats.
        
        Args:
            player: El objeto jugador
        """
        print("\n" + "="*70)
        print("EQUIPAMIENTO ACTUAL".center(70))
        print("="*70)
        
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        slots_to_check = [
            ("weapon", "Arma"),
            ("helmet", "Casco"),
            ("armor", "Armadura"),
            ("boots", "Botas"),
            ("ring", "Anillo 1"),
            ("ring2", "Anillo 2"),
            ("ring3", "Anillo 3"),
            ("tool",  "Herramienta"),
        ]
        
        for slot, display_name in slots_to_check:
            item = getattr(player, slot, None)
            
            if item is not None:
                item_name = item.Name if hasattr(item, 'Name') else item.name
                print(f"\n{display_name}: {item_name}")
                
                # Mostrar stats del item
                stats = EquipmentManager.get_item_stats(item)
                if stats:
                    for stat_name, stat_value in stats.items():
                        if stat_name == 'DEF' and isinstance(stat_value, (list, tuple)):
                            # Mostrar defensa multi-tipo
                            print(f"  • Defensa:")
                            for i, val in enumerate(stat_value):
                                if val > 0 and i < len(damage_type_names):
                                    print(f"    - {damage_type_names[i]}: +{val}")
                        else:
                            print(f"  • {stat_name}: +{stat_value}")
                
                # Mostrar daño para armas
                if hasattr(item, 'DMG') and isinstance(item.DMG, (list, tuple)):
                    print(f"  • Daño:")
                    for i, val in enumerate(item.DMG):
                        if val > 0 and i < len(damage_type_names):
                            # Mostrar rango de daño
                            min_val = item.DMG_min[i] if i < 4 and hasattr(item, 'DMG_min') else val
                            if i == 4:  # Deep siempre es máximo
                                print(f"    - {damage_type_names[i]}: {val} (siempre máximo)")
                            else:
                                print(f"    - {damage_type_names[i]}: {min_val}-{val}")
            else:
                print(f"\n{display_name}: [Vacío]")
        
        print("\n" + "="*70)
    
    @staticmethod
    def get_total_stats(player):
        """
        Calcula los stats totales del jugador incluyendo equipamiento.
        Útil para mostrar en el menú de estadísticas.
        
        Returns:
            Dict con los stats totales
        """
        # Stats base (estos ya deberían incluir el equipamiento aplicado)
        total_stats = {
            'Health': player.Health,
            'Health_max': player.Health_max,
            'Mana': player.Mana,
            'Mana_max': player.Mana_max,
            'DEF': player.DEF,  # Ahora es array
            'MDEF': player.MDEF,
            'AGI': player.AGI,
            'Level': player.Level,
            'EXP': player.EXP,
            'EXP_M': player.EXP_M,
            'Gold': player.Gold
        }
        
        return total_stats


def equip_menu(player, inventory):
    """
    Menú interactivo para equipar items del inventario.
    
    Args:
        player: El objeto jugador
        inventory: El objeto inventario
    """
    while True:
        choice = interactive_menu_select(
            title="MENÚ DE EQUIPAMIENTO",
            subtitle="Selecciona una opción",
            options=[
                (1, "Equipar item del inventario"),
                (2, "Desequipar item"),
                (3, "Ver equipamiento actual"),
                (0, "Volver"),
            ],
            prompt="Opción: ",
            default_value=1,
            border_style="yellow",
        )

        if choice == 1:
            # Mostrar items equipables del inventario
            from Modules.GatheringMasterySystem import cTool
            from Modules.setup import cWeapon
            equipable_items = [
                item for item in inventory.lObjectsInventory
                if hasattr(item, 'objectcheck') or isinstance(item, (cTool, cWeapon))
            ]
            
            if not equipable_items:
                print("\nNo tienes items equipables en el inventario.")
                wait_for_enter()
                continue
            
            try:
                equip_options = [(0, "Cancelar")]
                for i, item in enumerate(equipable_items, 1):
                    item_name = item.Name if hasattr(item, 'Name') else item.name
                    if isinstance(item, cWeapon):
                        item_type_label = "Arma"
                    elif isinstance(item, cTool):
                        item_type_label = "Herramienta"
                    else:
                        item_type_label = getattr(item, 'objectcheck', '?')
                    equip_options.append((i, f"{item_name} ({item_type_label})"))

                pick = interactive_menu_select(
                    title="Equipar item",
                    subtitle="Selecciona un item del inventario",
                    options=equip_options,
                    prompt="Item: ",
                    default_value=1 if len(equip_options) > 1 else 0,
                    border_style="yellow",
                )

                selection = pick - 1
                
                if 0 <= selection < len(equipable_items):
                    selected_item = equipable_items[selection]
                    
                    # Equipar el item (pasar inventory para que el item desplazado vuelva)
                    if EquipmentManager.equip_item(player, selected_item, inventory):
                        # Remover del inventario (1 unidad)
                        inventory.remove_item(selected_item, 1)
                    
                    wait_for_enter()
                else:
                    print("Selección inválida.")
                    wait_for_enter()
            except ValueError:
                print("Entrada inválida.")
                wait_for_enter()
        
        elif choice == 2:
            slot_map = {
                1: "weapon",
                2: "helmet",
                3: "armor",
                4: "boots",
                5: "ring",
                6: "ring2",
                7: "ring3",
                8: "tool",
            }

            slot_choice = interactive_menu_select(
                title="Desequipar",
                subtitle="Selecciona un slot",
                options=[
                    (1, "Arma"),
                    (2, "Casco"),
                    (3, "Armadura"),
                    (4, "Botas"),
                    (5, "Anillo 1"),
                    (6, "Anillo 2"),
                    (7, "Anillo 3"),
                    (8, "Herramienta"),
                    (0, "Cancelar"),
                ],
                prompt="Slot: ",
                default_value=1,
                border_style="yellow",
            )

            if slot_choice in slot_map:
                EquipmentManager.unequip_item(player, slot_map[slot_choice], inventory)
                wait_for_enter()
            else:
                print("Selección inválida.")
                wait_for_enter()
        
        elif choice == 3:
            EquipmentManager.show_equipment(player)
            wait_for_enter()
        
        elif choice == 0:
            break
        else:
            print("Opción inválida.")
            wait_for_enter()
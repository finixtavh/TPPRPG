"""
Sistema de Tiendas basado en JSON
==================================
Las tiendas cargan sus inventarios desde DataShops.json
"""

import json
import os
from typing import List, Optional
from Modules.input_utils import wait_for_enter, interactive_menu_select
from Modules.setup import cWeapon, cEquippableItems, cObject
from Modules.GatheringMasterySystem import cTool

class ShopManager:
    """Gestor de tiendas que carga inventarios desde JSON"""
    
    def __init__(self, shops_json_path: str = "./Data/DataShops.json"):
        """
        Inicializa el gestor de tiendas
        
        Args:
            shops_json_path: Ruta al archivo JSON de tiendas
        """
        self.shops_json_path = shops_json_path
        self.shops_data = {}
    
    def load_shops(self) -> bool:
        """
        Carga la configuración de tiendas desde JSON
        
        Returns:
            True si se cargó correctamente
        """
        try:
            if not os.path.exists(self.shops_json_path):
                print(f"[WARNING] Archivo {self.shops_json_path} no encontrado")
                self._create_default_shops_file()
            
            with open(self.shops_json_path, 'r', encoding='utf-8') as f:
                self.shops_data = json.load(f)
            
            print(f"[SUCCESS] {len(self.shops_data)} tiendas cargadas")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al cargar tiendas: {e}")
            return False
    
    def get_shop_items(self, shop_name: str) -> List[int]:
        """
        Obtiene la lista de IDs de items disponibles en una tienda
        
        Args:
            shop_name: Nombre de la tienda
            
        Returns:
            Lista de IDs de items
        """
        if shop_name in self.shops_data:
            shop_info = self.shops_data[shop_name]
            if isinstance(shop_info, list) and len(shop_info) > 0:
                return shop_info[0].get("IDs", [])
        return []
    
    def add_item_to_shop(self, shop_name: str, item_id: int) -> bool:
        """
        Agrega un item a una tienda
        
        Args:
            shop_name: Nombre de la tienda
            item_id: ID del item a agregar
            
        Returns:
            True si se agregó correctamente
        """
        try:
            if shop_name not in self.shops_data:
                self.shops_data[shop_name] = [{"IDs": []}]
            
            ids = self.shops_data[shop_name][0]["IDs"]
            if item_id not in ids:
                ids.append(item_id)
                self.save_shops()
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Error al agregar item a tienda: {e}")
            return False
    
    def remove_item_from_shop(self, shop_name: str, item_id: int) -> bool:
        """
        Remueve un item de una tienda
        
        Args:
            shop_name: Nombre de la tienda
            item_id: ID del item a remover
            
        Returns:
            True si se removió correctamente
        """
        try:
            if shop_name in self.shops_data:
                ids = self.shops_data[shop_name][0]["IDs"]
                if item_id in ids:
                    ids.remove(item_id)
                    self.save_shops()
                    return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Error al remover item de tienda: {e}")
            return False
    
    def save_shops(self) -> bool:
        """
        Guarda la configuración de tiendas en JSON
        
        Returns:
            True si se guardó correctamente
        """
        try:
            os.makedirs(os.path.dirname(self.shops_json_path), exist_ok=True)
            
            with open(self.shops_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.shops_data, f, indent=4, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al guardar tiendas: {e}")
            return False
    
    def _create_default_shops_file(self):
        """Crea un archivo de tiendas por defecto"""
        default_shops = {
            "GeneralStore": [
                {
                    "IDs": [1, 10, 20, 30, 40, 50, 51, 53]
                }
            ],
            "WeaponShop": [
                {
                    "IDs": [1, 2, 3, 4]
                }
            ],
            "ArmorShop": [
                {
                    "IDs": [10, 11, 12, 20, 21, 30, 31]
                }
            ],
            "MagicShop": [
                {
                    "IDs": [4, 5, 41, 42, 43, 44, 54, 55]
                }
            ]
        }
        
        self.shops_data = default_shops
        self.save_shops()


# Instancia global
_shop_manager_instance: Optional[ShopManager] = None

def get_shop_manager(shops_path: str = "./Data/DataShops.json") -> ShopManager:
    """Obtiene la instancia global del ShopManager"""
    global _shop_manager_instance
    
    if _shop_manager_instance is None:
        _shop_manager_instance = ShopManager(shops_path)
        _shop_manager_instance.load_shops()
    
    return _shop_manager_instance


def display_shop(shop_name: str, player, item_manager):
    """
    Muestra los items de una tienda y permite comprarlos
    
    Args:
        shop_name: Nombre de la tienda
        player: Objeto del jugador
        item_manager: Instancia del ItemManager
    """
    shop_manager = get_shop_manager()
    item_ids = shop_manager.get_shop_items(shop_name)
    
    if not item_ids:
        print(f"[WARNING] La tienda {shop_name} está vacía")
        return
    
    while True:
        print("\n" + "="*70)
        print(f"{shop_name.upper()}".center(70))
        print("="*70)
        print(f"Tu oro: {player.Gold}")
        print("-"*70)
        
        # Mostrar items disponibles
        items_info = []
        for i, item_id in enumerate(item_ids, 1):
            item_data = item_manager.get_item_by_id(item_id)
            if item_data:
                items_info.append((i, item_id, item_data))
                name = item_data.get("Name", "???")
                cost = item_data.get("Gold_Cost", 0)
                item_type = item_data.get("Type", "???")
                
                # Indicador de si puede comprarlo
                can_afford = "✓" if player.Gold >= cost else "✗"
                
                print(f"{i:2d}. [{can_afford}] {name:30s} - {cost:4d} oro ({item_type})")
        
        print("-"*70)
        print("="*70)

        try:
            menu_options = [(0, "Salir de la tienda")]
            for i, _, item_data in items_info:
                name = item_data.get("Name", "???")
                cost = item_data.get("Gold_Cost", 0)
                can_afford = "✓" if player.Gold >= cost else "✗"
                menu_options.append((i, f"[{can_afford}] {name} - {cost} oro"))

            choice_num = interactive_menu_select(
                title=f"Tienda: {shop_name}",
                subtitle=f"Oro: {player.Gold}",
                options=menu_options,
                prompt="Item: ",
                default_value=1 if len(menu_options) > 1 else 0,
                border_style="yellow",
            )

            if choice_num == 0:
                print("Gracias por tu visita!")
                break
            
            if 1 <= choice_num <= len(items_info):
                _, item_id, item_data = items_info[choice_num - 1]
                
                # Mostrar detalles del item
                print("\n" + "-"*70)
                print(f"ITEM: {item_data.get('Name')}")
                print(f"Tipo: {item_data.get('Type')}")
                print(f"Costo: {item_data.get('Gold_Cost')} oro")
                print(f"Descripción: {item_data.get('Description', 'N/A')}")
                
                # Mostrar stats
                if "DMG" in item_data:
                    dmg = item_data["DMG"]
                    print(f"Daño Físico: {dmg[0] if len(dmg) > 0 else 0}")
                if "Magical_DMG" in item_data:
                    mdmg = item_data["Magical_DMG"]
                    if len(mdmg) > 1 and mdmg[1] > 0:
                        print(f"Daño Mágico: {mdmg[1]}")
                if "Defense" in item_data and item_data["Defense"] > 0:
                    print(f"Defensa: +{item_data['Defense']}")
                if "HealthBoost" in item_data and item_data["HealthBoost"] > 0:
                    print(f"HP Máximo: +{item_data['HealthBoost']}")
                if "DmgBoost" in item_data and item_data["DmgBoost"] > 0:
                    print(f"Daño: +{item_data['DmgBoost']}")
                if "HealthSteal" in item_data and item_data["HealthSteal"] > 0:
                    print(f"Robo de Vida: +{item_data['HealthSteal']}")
                if "HealthRestore" in item_data and item_data["HealthRestore"] > 0:
                    print(f"Restaura HP: {item_data['HealthRestore']}")
                if "ManaRestore" in item_data and item_data["ManaRestore"] > 0:
                    print(f"Restaura MP: {item_data['ManaRestore']}")
                
                print("-"*70)
                
                # Confirmar compra
                cost = item_data.get("Gold_Cost", 0)
                
                if player.Gold < cost:
                    print(f"\n[ERROR] No tienes suficiente oro. Necesitas {cost - player.Gold} más.")
                    wait_for_enter()
                    continue
                
                confirm_choice = interactive_menu_select(
                    title="Confirmar compra",
                    subtitle=f"¿Comprar por {cost} oro?",
                    options=[(1, "Sí"), (0, "No")],
                    prompt="Confirmación: ",
                    default_value=1,
                    border_style="yellow",
                )

                if confirm_choice == 1:
                    # Crear el objeto del item
                    
                    item_obj = item_manager.create_item_object(item_id, cWeapon, cEquippableItems, cObject, cTool)
                    
                    if item_obj:
                        # Descontar oro
                        player.Gold -= cost
                        
                        # Agregar al inventario
                        from Modules.setup import vInventory
                        vInventory.addObject(item_obj)
                        
                        print(f"\n[SUCCESS] ¡Has comprado {item_data.get('Name')}!")
                        print(f"Oro restante: {player.Gold}")
                        wait_for_enter()
                    else:
                        print("[ERROR] No se pudo crear el item")
                        wait_for_enter()
                else:
                    print("Compra cancelada.")
                    wait_for_enter()
            else:
                print("[ERROR] Opción inválida")
                wait_for_enter()
                
        except ValueError:
            print("[ERROR] Entrada inválida")
            wait_for_enter()
        except Exception as e:
            print(f"[ERROR] {e}")
            wait_for_enter()

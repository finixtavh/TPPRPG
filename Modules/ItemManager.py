import json
import os
from typing import Dict, List, Optional, Any, Union


class ItemManager:
    """Gestor de items que carga y maneja todos los objetos desde JSON"""
    
    def __init__(self, items_json_path: str = "./Data/DataItems.json"):
        """
        Inicializa el gestor de items
        
        Args:
            items_json_path: Ruta al archivo JSON de items
        """
        self.items_json_path = items_json_path
        self.items_data: Dict = {}
        self.items_by_id: Dict[int, Dict] = {}
        self.items_by_name: Dict[str, Dict] = {}
        
    def load_items(self) -> bool:
        """
        Carga todos los items desde el archivo JSON
        
        Returns:
            True si se cargó correctamente, False si hubo error
        """
        try:
            if not os.path.exists(self.items_json_path):
                print(f"[WARNING] Archivo {self.items_json_path} no encontrado. Creando uno nuevo...")
                self._create_default_items_file()
            
            with open(self.items_json_path, 'r', encoding='utf-8') as f:
                self.items_data = json.load(f)
            
            # Crear índices para búsqueda rápida
            self._build_indexes()
            
            print(f"[SUCCESS] {len(self.items_by_id)} items cargados desde JSON")
            return True
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Error al parsear JSON: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Error al cargar items: {e}")
            return False
    
    def _build_indexes(self):
        """Construye índices de búsqueda por ID y nombre"""
        self.items_by_id.clear()
        self.items_by_name.clear()
        
        for category, items in self.items_data.items():
            if category.startswith("TYPE:"):
                for item_key, item_data in items.items():
                    item_id = item_data.get("STATIC_ID")
                    item_name = item_data.get("Name")
                    
                    if item_id is not None:
                        self.items_by_id[item_id] = {
                            **item_data,
                            "category": category,
                            "key": item_key
                        }
                    
                    if item_name:
                        self.items_by_name[item_name.lower()] = {
                            **item_data,
                            "category": category,
                            "key": item_key
                        }
    
    def get_item_by_id(self, item_id: Union[int, str]) -> Optional[Dict]:
        """
        Obtiene los datos de un item por su ID
        
        Args:
            item_id: ID del item
            
        Returns:
            Dict con los datos del item o None si no existe
        """
        return self.items_by_id.get(item_id)
    
    def get_item_by_name(self, name: str) -> Optional[Dict]:
        """
        Obtiene los datos de un item por su nombre
        
        Args:
            name: Nombre del item (case-insensitive)
            
        Returns:
            Dict con los datos del item o None si no existe
        """
        return self.items_by_name.get(name.lower())
    
    def get_items_by_type(self, item_type: str) -> List[Dict]:
        """
        Obtiene todos los items de un tipo específico
        
        Args:
            item_type: Tipo de item (Weapon, Armor, Helmet, etc.)
            
        Returns:
            Lista de items del tipo especificado
        """
        category_key = f"TYPE:{item_type}"
        if category_key in self.items_data:
            return [
                {**item_data, "key": key} 
                for key, item_data in self.items_data[category_key].items()
            ]
        return []
    
    def create_item_object(self, item_id: Union[int, str], cWeapon=None, cEquippableItems=None, cObject=None, cTool=None, cMaterial=None):
        """
        Crea un objeto de item (cWeapon, cEquippableItems, cObject, cTool o cMaterial) desde JSON
        
        Args:
            item_id: ID del item a crear
            cWeapon: Clase cWeapon importada
            cEquippableItems: Clase cEquippableItems importada
            cObject: Clase cObject importada
            cTool: Clase cTool importada
            cMaterial: Clase cMaterial importada
            
        Returns:
            Objeto del tipo apropiado o None si no existe
        """
        item_data = self.get_item_by_id(item_id)
        
        if not item_data:
            print(f"[ERROR] Item con ID {item_id} no encontrado")
            return None
        
        item_type = item_data.get("Type")
        
        try:
            if item_type == "Weapon":
                return self._create_weapon(item_data, cWeapon)
            elif item_type in ["Armor", "Helmet", "Boots", "Ring"]:
                return self._create_equippable(item_data, cEquippableItems)
            elif item_type == "Consumable":
                return self._create_consumable(item_data, cObject)
            elif item_type == "Tool":
                return self._create_tool(item_data, cTool)
            elif item_type == "Material":
                if cMaterial is None:
                    # Intentar importar si no se pasó
                    from Modules.GatheringMasterySystem import cMaterial
                return self._create_material(item_data, cMaterial)

            else:
                print(f"[ERROR] Tipo de item desconocido: {item_type}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Error al crear item {item_id}: {e}")
            return None
    
    def _create_weapon(self, item_data: Dict, cWeapon):
        """
        Creates a cWeapon via Json
        
        DEF and DMG Arrays:
        DMG: [Physical, Thermal, Earth, Electric, Deep]
        DMG_min: [Physical, Thermal, Earth, Electric] (Deep is always max dmg)
        """
        # DMG Array
        dmg = item_data.get("DMG", [0, 0, 0, 0, 0])
        dmg_min = item_data.get("DMG_min", [0, 0, 0, 0])
        return cWeapon(
            ID=item_data.get("STATIC_ID"),
            name=item_data.get("Name"),
            DMG=dmg,
            DMG_min=dmg_min,
            Gold_Cost=item_data.get("Gold_Cost", 0),
            Description=item_data.get("Description", "")
        )
    
    def _create_equippable(self, item_data: Dict, cEquippableItems):
        """
        Crea un objeto cEquippableItems desde datos JSON
        
        Nuevo formato:
        Defense: [Physical, Thermal, Earth, Electric, Deep]
        """
        # DEF Array
        defense = item_data.get("Defense", [0, 0, 0, 0, 0])

        
        return cEquippableItems(
            ID=item_data.get("STATIC_ID"),
            name=item_data.get("Name"),
            Defense=defense,
            HealthBoost=item_data.get("HealthBoost", 0),
            HealthSteal=item_data.get("HealthSteal", 0),
            DmgBoost=item_data.get("DmgBoost", 0),
            Gold_Cost=item_data.get("Gold_Cost", 0),
            Description=item_data.get("Description", ""),
            objectcheck=item_data.get("Type")
        )
    
    def _create_consumable(self, item_data: Dict, cObject):
        """Crea un objeto cObject (consumible) desde datos JSON"""
        return cObject(
            ID=item_data.get("STATIC_ID"),
            name=item_data.get("Name"),
            HealthRestore=item_data.get("HealthRestore", 0),
            ManaRestore=item_data.get("ManaRestore", 0),
            Gold_Cost=item_data.get("Gold_Cost", 0),
            Description=item_data.get("Description", "")
        )
    
    def _create_tool(self, item_data: Dict, cTool):
        """Crea una Herramienta cTool"""
        return cTool(
            ID=item_data.get("STATIC_ID"),
            TypeStr=item_data.get("Tool_Type"),
            Name=item_data.get("Name"),
            Desc=item_data.get("Desc"),
            Efficiency=item_data.get("Efficiency"),
            Gold_Cost=item_data.get("Gold_Cost"),
            MaxStack=item_data.get("MaxStack"),
            Enchantments=item_data.get("Enchantments")
        )

    def _create_material(self, item_data: Dict, cMaterial):
        """Crea un Material cMaterial"""
        return cMaterial(
            MATERIAL_ID=item_data.get("MATERIAL_ID", item_data.get("STATIC_ID")),
            TypeStr=item_data.get("Material_Type", "Unknown"),
            Name=item_data.get("Name"),
            Hardness=item_data.get("Hardness", 10),
            SkillName=item_data.get("SkillName", "mining"),
            Description=item_data.get("Description", "Sin descripción"),
            MaxStack=item_data.get("MaxStack", 99),
            Rarity=item_data.get("Rarity", "Common"),
            Level_Req=item_data.get("Level_Req", None)
        )

    def add_item(self, item_type: str, item_key: str, item_data: Dict) -> bool:
        """
        Agrega un nuevo item al JSON
        
        Args:
            item_type: Tipo de item (Weapon, Armor, etc.)
            item_key: Clave única del item en el JSON
            item_data: Datos del item
            
        Returns:
            True si se agregó correctamente
        """
        try:
            category_key = f"TYPE:{item_type}"
            
            # Crear categoría si no existe
            if category_key not in self.items_data:
                self.items_data[category_key] = {}
            
            # Agregar item
            self.items_data[category_key][item_key] = item_data
            
            # Guardar cambios
            self.save_items()
            
            # Reconstruir índices
            self._build_indexes()
            
            print(f"[SUCCESS] Item {item_key} agregado a {item_type}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al agregar item: {e}")
            return False
    
    def modify_item(self, item_id: int, updates: Dict) -> bool:
        """
        Modifica un item existente
        
        Args:
            item_id: ID del item a modificar
            updates: Dict con los campos a actualizar
            
        Returns:
            True si se modificó correctamente
        """
        try:
            item_info = self.items_by_id.get(item_id)
            
            if not item_info:
                print(f"[ERROR] Item con ID {item_id} no encontrado")
                return False
            
            category = item_info.get("category")
            key = item_info.get("key")
            
            # Actualizar campos
            for field, value in updates.items():
                self.items_data[category][key][field] = value
            
            # Guardar cambios
            self.save_items()
            
            # Reconstruir índices
            self._build_indexes()
            
            print(f"[SUCCESS] Item ID {item_id} modificado")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al modificar item: {e}")
            return False
    
    def delete_item(self, item_id: int) -> bool:
        """
        Elimina un item del JSON
        
        Args:
            item_id: ID del item a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            item_info = self.items_by_id.get(item_id)
            
            if not item_info:
                print(f"[ERROR] Item con ID {item_id} no encontrado")
                return False
            
            category = item_info.get("category")
            key = item_info.get("key")
            
            # Eliminar item
            del self.items_data[category][key]
            
            # Guardar cambios
            self.save_items()
            
            # Reconstruir índices
            self._build_indexes()
            
            print(f"[SUCCESS] Item ID {item_id} eliminado")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al eliminar item: {e}")
            return False
    
    def save_items(self) -> bool:
        """
        Guarda los items actuales en el archivo JSON
        
        Returns:
            True si se guardó correctamente
        """
        try:
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.items_json_path), exist_ok=True)
            
            with open(self.items_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.items_data, f, indent=4, ensure_ascii=False)
            
            print(f"[SUCCESS] Items guardados en {self.items_json_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al guardar items: {e}")
            return False
    
    def _create_default_items_file(self):
        """Crea un archivo de items por defecto si no existe"""
        default_data = {
            "TYPE:Weapons": {
                "wooden_sword": {
                    "STATIC_ID": 1,
                    "Name": "Espada de Madera",
                    "Type": "Weapon",
                    "DMG": [10, 0, 0, 0, 0],
                    "DMG_min": [5, 0, 0, 0],
                    "Gold_Cost": 10,
                    "Description": "Una simple espada de madera"
                }
            },
            "TYPE:Armor": {
                "leather_armor": {
                    "STATIC_ID": 10,
                    "Name": "Armadura de Cuero",
                    "Type": "Armor",
                    "Defense": [5, 2, 2, 2, 1],
                    "HealthBoost": 10,
                    "HealthSteal": 0,
                    "DmgBoost": 0,
                    "Gold_Cost": 30,
                    "Description": "Armadura ligera de cuero"
                }
            }
        }
        
        self.items_data = default_data
        self.save_items()
    
    def list_all_items(self, detailed: bool = False):
        """
        Muestra todos los items disponibles
        
        Args:
            detailed: Si es True, muestra información detallada
        """
        print("\n" + "="*70)
        print("ITEMS DISPONIBLES".center(70))
        print("="*70)
        
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        for category, items in self.items_data.items():
            if category.startswith("TYPE:"):
                category_name = category.replace("TYPE:", "")
                print(f"\n[{category_name}]")
                print("-" * 70)
                
                for item_key, item_data in items.items():
                    item_id = item_data.get("STATIC_ID", "?")
                    item_name = item_data.get("Name", item_key)
                    item_cost = item_data.get("Gold_Cost", 0)
                    
                    if detailed:
                        print(f"  ID: {item_id} | {item_name}")
                        print(f"    Costo: {item_cost} oro")
                        print(f"    Descripción: {item_data.get('Description', 'N/A')}")
                        
                        # Mostrar stats específicos según el tipo
                        if "DMG" in item_data:
                            dmg = item_data["DMG"]
                            if isinstance(dmg, list):
                                print("    Daño Máximo:")
                                for i, val in enumerate(dmg):
                                    if val > 0 and i < len(damage_type_names):
                                        print(f"      - {damage_type_names[i]}: {val}")
                            else:
                                print(f"    Daño Físico: {dmg}")
                        
                        if "DMG_min" in item_data:
                            dmg_min = item_data["DMG_min"]
                            if isinstance(dmg_min, list):
                                print("    Daño Mínimo:")
                                for i, val in enumerate(dmg_min):
                                    if val > 0 and i < len(damage_type_names) - 1:  # -1 porque no hay Deep min
                                        print(f"      - {damage_type_names[i]}: {val}")
                            else:
                                print(f"    Daño Físico Mín: {dmg_min}")
                        
                        if "Defense" in item_data:
                            defense = item_data["Defense"]
                            if isinstance(defense, list):
                                print("    Defensa:")
                                for i, val in enumerate(defense):
                                    if val > 0 and i < len(damage_type_names):
                                        print(f"      - {damage_type_names[i]}: +{val}")
                            elif defense > 0:
                                print(f"    Defensa: +{defense}")
                        
                        if "HealthBoost" in item_data and item_data["HealthBoost"] > 0:
                            print(f"    HP: +{item_data['HealthBoost']}")
                        if "DmgBoost" in item_data and item_data["DmgBoost"] > 0:
                            print(f"    Daño: +{item_data['DmgBoost']}")
                        if "HealthSteal" in item_data and item_data["HealthSteal"] > 0:
                            print(f"    Robo de Vida: +{item_data['HealthSteal']}")
                        if "HealthRestore" in item_data and item_data["HealthRestore"] > 0:
                            print(f"    Restaura HP: {item_data['HealthRestore']}")
                        if "ManaRestore" in item_data and item_data["ManaRestore"] > 0:
                            print(f"    Restaura MP: {item_data['ManaRestore']}")
                        print()
                    else:
                        print(f"  {item_id:3d} - {item_name:30s} ({item_cost} oro)")
        
        print("="*70)


# Función helper para obtener una instancia global del ItemManager
_item_manager_instance: Optional[ItemManager] = None

def get_item_manager(items_path: str = "./Data/DataItems.json") -> ItemManager:
    """
    Obtiene la instancia global del ItemManager (patrón Singleton)
    
    Args:
        items_path: Ruta al archivo JSON de items
        
    Returns:
        Instancia del ItemManager
    """
    global _item_manager_instance
    
    if _item_manager_instance is None:
        _item_manager_instance = ItemManager(items_path)
        _item_manager_instance.load_items()
    
    return _item_manager_instance


# Funciones de conveniencia para usar en el juego
def load_item_by_id(item_id: Union[int, str], cWeapon=None, cEquippableItems=None, cObject=None, cTool=None, cMaterial=None):
    """
    Carga un item por ID y devuelve el objeto creado
    
    Args:
        item_id: ID del item
        cWeapon, cEquippableItems, cObject, cTool, cMaterial: Clases de items
        
    Returns:
        Objeto del item o None
    """
    manager = get_item_manager()
    return manager.create_item_object(item_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)


def load_items_by_type(item_type: str, cWeapon, cEquippableItems, cObject) -> List:
    """
    Carga todos los items de un tipo específico
    
    Args:
        item_type: Tipo de item (Weapon, Armor, etc.)
        cWeapon, cEquippableItems, cObject: Clases de items
        
    Returns:
        Lista de objetos de items
    """
    manager = get_item_manager()
    items_data = manager.get_items_by_type(item_type)
    
    items = []
    for item_data in items_data:
        item = manager.create_item_object(item_data["STATIC_ID"], cWeapon, cEquippableItems, cObject)
        if item:
            items.append(item)
    
    return items


def search_item_by_name(name: str) -> Optional[Dict]:
    """
    Busca un item por nombre
    
    Args:
        name: Nombre del item
        
    Returns:
        Datos del item o None
    """
    manager = get_item_manager()
    return manager.get_item_by_name(name)
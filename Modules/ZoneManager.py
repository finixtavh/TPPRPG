from typing import Dict, List, Tuple
from Modules.Loader import Read


class ZoneManager:
    """Gestor dinámico de zonas que carga desde JSON y mods"""
    
    def __init__(self, datastats_path: str = "./Data/DataStats.json"):
        self.datastats_path = datastats_path
        self.zones_cache = {}
    
    def get_all_zones(self) -> Dict[str, Dict]:
        """
        
        Returns:
            Dict con formato: {
                "ZoneName": {
                    "name": "Nombre mostrado",
                    "desc": "Descripción",
                    "color": "verde",
                    "enemies": [...],
                    "source": "base" o mod_name
                }
            }
        """
        zones = {}
        
        # 1. Cargar zonas del JSON base
        base_zones = self._load_zones_from_json()
        zones.update(base_zones)
        
        # 2. Cargar zonas de mods (desde ModAPI)
        mod_zones = self._load_zones_from_mods()
        zones.update(mod_zones)
        
        return zones
    
    def _load_zones_from_json(self) -> Dict[str, Dict]:
        """Lee todas las zonas del DataStats.json"""
        zones = {}
        
        try:
            # Leer TODO el JSON
            all_data = Read(self.datastats_path, None, None)
            
            if not all_data:
                return zones
            
            # Iterar sobre todas las keys del JSON
            for zone_key, zone_data in all_data.items():
                # Saltar si no es una zona válida
                if not isinstance(zone_data, list) or len(zone_data) == 0:
                    continue
                
                # Extraer información de la zona
                zone_info = self._extract_zone_info(zone_key, zone_data[0], "base")
                
                if zone_info:
                    zones[zone_key] = zone_info
        
        except Exception as e:
            print(f"[ERROR] No se pudieron cargar zonas del JSON: {e}")
        
        return zones
    
    def _load_zones_from_mods(self) -> Dict[str, Dict]:
        """
        Lee zonas desde los datos de mods cargados en ModAPI
        Las zonas ya están procesadas y listas en stats_injections
        """
        zones = {}
        
        try:
            from Modules.ModLoader import get_mod_api
            mod_api = get_mod_api()
            
            # Obtener zonas inyectadas por mods desde stats_injections
            # stats_injections tiene formato: {zone_name: zone_data_array}
            mod_zone_data = mod_api.get_all_zones()
            
            for zone_key, zone_data_array in mod_zone_data.items():
                if isinstance(zone_data_array, list) and len(zone_data_array) > 0:
                    # Extraer info de la zona
                    zone_info = self._extract_zone_info(zone_key, zone_data_array[0], "mod")
                    
                    if zone_info:
                        zones[zone_key] = zone_info
        
        except Exception as e:
            # No hay problema si los mods no están cargados
            pass
        
        return zones
    
    def _extract_zone_info(self, zone_key: str, zone_data: Dict, source: str) -> Dict:
        """
        Extrae información relevante de una zona
        
        Args:
            zone_key: Clave de la zona (ej: "Forest", "ShadowRealm")
            zone_data: Diccionario con datos de la zona
            source: "base" o "mod"
        """
        try:
            # Buscar el objeto "Strings"
            strings = zone_data.get("Strings", {})
            
            if not strings:
                return None
            
            # Extraer enemigos (todas las keys que no sean "Strings" ni "Gathering")
            enemies = []
            for key, value in zone_data.items():
                if key not in ["Strings", "Gathering"] and isinstance(value, dict):
                    if "NAME" in value:  # Es un enemigo
                        enemies.append(value)
            
            return {
                "name": strings.get("name", zone_key),
                "desc": strings.get("desc", "Sin descripción"),
                "exit": strings.get("exit", f"Saliendo de {zone_key}"),
                "color": strings.get("color", "white"),
                "enemies": enemies,
                "gathering": zone_data.get("Gathering", {}),
                "source": source
            }
        
        except Exception as e:
            print(f"[ERROR] Error extrayendo info de {zone_key}: {e}")
            return None
    
    def get_zone_by_key(self, zone_key: str) -> Dict:
        """Obtiene información de una zona específica"""
        all_zones = self.get_all_zones()
        return all_zones.get(zone_key, None)
    
    def get_zone_enemies(self, zone_key: str) -> List:
        """Obtiene los enemigos de una zona"""
        zone_info = self.get_zone_by_key(zone_key)
        if zone_info:
            return zone_info.get("enemies", [])
        return []
    
    def get_zones_list(self) -> List[Tuple[str, str, str]]:
        """
        Obtiene lista de zonas para el selector
        
        Returns:
            List de tuplas: [(zone_key, zone_name, zone_color), ...]
        """
        all_zones = self.get_all_zones()
        zones_list = []
        
        for zone_key, zone_info in all_zones.items():
            zones_list.append((
                zone_key,
                zone_info["name"],
                zone_info["color"]
            ))
        
        return zones_list


# Singleton global
_zone_manager_instance = None

def get_zone_manager(datastats_path: str = "./Data/DataStats.json"):
    """Obtiene la instancia global del ZoneManager"""
    global _zone_manager_instance
    
    if _zone_manager_instance is None:
        _zone_manager_instance = ZoneManager(datastats_path)
    
    return _zone_manager_instance


# Funciones helper
def get_all_zones() -> Dict[str, Dict]:
    """Obtiene todas las zonas disponibles"""
    manager = get_zone_manager()
    return manager.get_all_zones()


def get_zones_for_selector() -> List[Tuple[str, str, str]]:
    """Obtiene lista de zonas para mostrar en el selector"""
    manager = get_zone_manager()
    return manager.get_zones_list()


def get_zone_info(zone_key: str) -> Dict:
    """Obtiene información de una zona específica"""
    manager = get_zone_manager()
    return manager.get_zone_by_key(zone_key)

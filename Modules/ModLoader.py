import os
import sys
import importlib
import importlib.util
import json
import inspect
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import logging

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ModuleNotFoundError:
    Console = None
    Panel = None
    Table = None

logger = logging.getLogger('TPPRPG.ModLoader')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _handler = logging.FileHandler('tpprpg_mods.log', mode='a', encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)
    logger.propagate = False

if Console is not None:
    console = Console()
else:
    class _FallbackConsole:
        def print(self, *args, **kwargs):
            print(*args)
    console = _FallbackConsole()


class ModAPI:
    """API para que los mods interactúen con el juego"""

    def __init__(self):
        self.registered_items = {}
        self.registered_enemies = {}
        self.registered_zones = {}
        self.event_handlers = {}
        self.custom_commands = {}
        self.registered_shops = {}
        self.player_attributes = {}
        self.item_injections = {}
        self.stats_injections = {}
        self.shop_injections = {}
        self.enchantment_injections = {}
        
        # NUEVO: Almacenar datos crudos de JSONs de mods
        self.mod_data_files = {}  # {mod_name: json_data}
    
    # =========================================================================
    # CARGA DE DATOS DE MOD
    # =========================================================================
    
    def load_mod_data(self, mod_name: str, json_path: str) -> Dict:
        """
        Carga el archivo JSON de datos de un mod
        
        Args:
            mod_name: Nombre del mod
            json_path: Ruta al archivo .json del mod
            
        Returns:
            Dict con los datos del mod
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.mod_data_files[mod_name] = data
            logger.info(f"Datos del mod '{mod_name}' cargados desde {json_path}")
            
            return data
        
        except FileNotFoundError:
            logger.warning(f"Archivo de datos no encontrado para mod '{mod_name}': {json_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON del mod '{mod_name}': {e}")
            return {}
        except Exception as e:
            logger.error(f"Error cargando datos del mod '{mod_name}': {e}")
            return {}
    
    def get_mod_data(self, mod_name: str) -> Dict:
        """
        Obtiene los datos cargados de un mod
        
        Args:
            mod_name: Nombre del mod
            
        Returns:
            Dict con los datos del mod o {} si no existe
        """
        return self.mod_data_files.get(mod_name, {})
    
    # =========================================================================
    # INYECCIÓN AUTOMÁTICA DESDE JSON DEL MOD
    # =========================================================================
    
    def auto_inject_from_mod_data(self, mod_name: str):
        """
        Inyecta automáticamente items, zonas y tiendas desde el JSON del mod
        
        Args:
            mod_name: Nombre del mod
        """
        mod_data = self.get_mod_data(mod_name)
        
        if not mod_data:
            logger.warning(f"No hay datos para auto-inyectar del mod '{mod_name}'")
            return
        
        # Inyectar items
        if "items" in mod_data:
            for item_type, items in mod_data["items"].items():
                if item_type not in self.item_injections:
                    self.item_injections[item_type] = {}
                
                for item_key, item_data in items.items():
                    self.item_injections[item_type][item_key] = item_data
                    logger.info(f"[{mod_name}] Item auto-inyectado: {item_type}.{item_key}")
        
        # Inyectar zonas
        if "zones" in mod_data:
            for zone_name, zone_data in mod_data["zones"].items():
                self.stats_injections[zone_name] = zone_data
                logger.info(f"[{mod_name}] Zona auto-inyectada: {zone_name}")
        
        # Inyectar tiendas
        if "shops" in mod_data:
            for shop_name, shop_data in mod_data["shops"].items():
                self.shop_injections[shop_name] = shop_data
                logger.info(f"[{mod_name}] Tienda auto-inyectada: {shop_name}")
        
        # Inyectar encantamientos
        if "enchantments" in mod_data:
            for ench_key, ench_data in mod_data["enchantments"].items():
                self.enchantment_injections[ench_key] = ench_data
                logger.info(f"[{mod_name}] Encantamiento auto-inyectado: {ench_key}")
    
    # =========================================================================
    # REGISTRO DE ITEMS (mantenido para compatibilidad)
    # =========================================================================
    
    def register_item(self, item_or_class, item_data: Dict):
        """Registra un item manualmente"""
        item_id = item_data.get('id', f'mod_item_{len(self.registered_items)}')
        item_class = item_or_class if inspect.isclass(item_or_class) else item_or_class.__class__
        self.registered_items[item_id] = {
            'class': item_class,
            'instance': None if inspect.isclass(item_or_class) else item_or_class,
            'data': item_data
        }
        logger.info(f"Item registrado: {item_id}")
    
    def inject_item_to_json(self, item_type: str, item_key: str, item_data: Dict):
        """Inyecta un item al sistema"""
        if item_type not in self.item_injections:
            self.item_injections[item_type] = {}
        
        self.item_injections[item_type][item_key] = item_data
        logger.info(f"Item inyectado a {item_type}: {item_key}")
    
    # =========================================================================
    # REGISTRO DE ENEMIGOS Y ZONAS (mantenido para compatibilidad)
    # =========================================================================
    
    def register_enemy(self, enemy_or_class, enemy_data: Dict):
        """Registra un enemigo"""
        enemy_id = enemy_data.get('id', f'mod_enemy_{len(self.registered_enemies)}')
        enemy_class = enemy_or_class if inspect.isclass(enemy_or_class) else enemy_or_class.__class__
        self.registered_enemies[enemy_id] = {
            'class': enemy_class,
            'instance': None if inspect.isclass(enemy_or_class) else enemy_or_class,
            'data': enemy_data
        }
        logger.info(f"Enemigo registrado: {enemy_id}")
    
    def register_zone(self, zone_name: str, zone_data: Dict):
        """Registra una zona"""
        self.registered_zones[zone_name] = zone_data
        logger.info(f"Zona registrada: {zone_name}")
    
    def inject_zone_to_json(self, zone_name: str, zone_data: List[Dict]):
        """Inyecta una zona al DataStats.json virtual"""
        self.stats_injections[zone_name] = zone_data
        logger.info(f"Zona inyectada a DataStats: {zone_name}")
    
    # =========================================================================
    # REGISTRO DE TIENDAS
    # =========================================================================
    
    def register_shop(self, shop_name: str, shop_data: Dict):
        """Registra una tienda"""
        self.registered_shops[shop_name] = shop_data
        logger.info(f"Tienda registrada: {shop_name}")
    
    def inject_shop_to_json(self, shop_name: str, item_ids: List[int]):
        """Inyecta una tienda al DataShops.json virtual"""
        self.shop_injections[shop_name] = [{"IDs": item_ids}]
        logger.info(f"Tienda inyectada: {shop_name}")
    
    # =========================================================================
    # ATRIBUTOS PERSONALIZADOS DEL JUGADOR
    # =========================================================================
    
    def register_player_attribute(self, attr_name: str, default_value: Any, 
                                   description: str = ""):
        """Registra un atributo personalizado para el jugador"""
        self.player_attributes[attr_name] = {
            'default': default_value,
            'description': description
        }
        logger.info(f"Atributo de jugador registrado: {attr_name}")
    
    def apply_player_attributes(self, player):
        """Aplica todos los atributos personalizados al jugador"""
        for attr_name, attr_data in self.player_attributes.items():
            if not hasattr(player, attr_name):
                setattr(player, attr_name, attr_data['default'])
                logger.info(f"Atributo '{attr_name}' agregado al jugador: {attr_data['default']}")
    
    # =========================================================================
    # EVENTOS
    # =========================================================================
    
    def register_event_handler(self, event_name: str, handler_func: Callable):
        """Registra un manejador de eventos"""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler_func)
        logger.info(f"Event handler registrado para: {event_name}")
    
    def fire_event(self, event_name: str, *args, **kwargs):
        """Dispara un evento"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error en event handler {handler.__name__}: {e}")
    
    # =========================================================================
    # COMANDOS PERSONALIZADOS
    # =========================================================================
    
    def register_command(self, command_name: str, handler_func: Callable, 
                        description: str = ""):
        """Registra un comando personalizado"""
        self.custom_commands[command_name] = {
            'handler': handler_func,
            'description': description
        }
        logger.info(f"Comando registrado: {command_name}")
    
    # =========================================================================
    # INTEGRACIÓN CON MANAGERS
    # =========================================================================
    
    def integrate_with_item_manager(self, item_manager):
        """Integra items de mods con ItemManager"""
        for item_type, items in self.item_injections.items():
            if item_type not in item_manager.items_data:
                item_manager.items_data[item_type] = {}
            
            for item_key, item_data in items.items():
                item_manager.items_data[item_type][item_key] = item_data
                logger.info(f"Item integrado: {item_type}.{item_key}")
        
        console.print(f"[green]✓ {len(self.item_injections)} tipos de items integrados[/green]")
    
    def integrate_with_shop_manager(self, shop_manager):
        """Integra tiendas de mods con ShopManager"""
        for shop_name, shop_data in self.shop_injections.items():
            shop_manager.shops_data[shop_name] = shop_data
            logger.info(f"Tienda integrada: {shop_name}")
        
        console.print(f"[green]✓ {len(self.shop_injections)} tiendas integradas[/green]")
    
    def integrate_with_enchantment_system(self):
        """Integra encantamientos interactuando con EnchantmentSystem"""
        try:
            from Modules.EnchantmentSystem import register_enchantment, load_enchantment_from_json
            count = 0
            for ench_key, ench_data in self.enchantment_injections.items():
                ench_instance = load_enchantment_from_json(ench_data)
                register_enchantment(ench_instance)
                logger.info(f"Encantamiento integrado: {ench_key}")
                count += 1
            if count > 0:
                logger.info(f"{count} encantamientos integrados.")
        except ImportError:
            logger.warning("No se pudo cargar EnchantmentSystem para la integración de encantamientos")
    
    def get_all_items(self) -> Dict:
        """Retorna todos los items inyectados"""
        return self.item_injections
    
    def get_all_zones(self) -> Dict:
        """Retorna todas las zonas inyectadas"""
        return self.stats_injections
    
    def get_all_shops(self) -> Dict:
        """Retorna todas las tiendas inyectadas"""
        return self.shop_injections


class ModInfo:
    """Información sobre un mod"""
    def __init__(self, mod_name: str, file_path: Path):
        self.mod_name = mod_name
        self.file_path = file_path
        self.py_file = file_path / f"{mod_name}.py"
        self.json_file = file_path / f"{mod_name}.json"
        self.loaded = False
        self.enabled = True
        
        # Metadata del JSON
        self.version = "1.0.0"
        self.author = "Unknown"
        self.description = ""


class ModLoader:
    """Cargador de mods con sistema de archivos por mod"""
    
    def __init__(self, mods_directory="mods"):
        base_dir = Path(__file__).resolve().parent.parent
        self.mods_directory = (base_dir / mods_directory) if not Path(mods_directory).is_absolute() else Path(mods_directory)
        self.loaded_mods = {}
        self.mod_api = ModAPI()
        
        self.mods_directory.mkdir(exist_ok=True, parents=True)

    
    def discover_mods(self) -> Dict[str, ModInfo]:
        """
        Descubre mods en el directorio de mods
        Busca carpetas con archivos .py y .json del mismo nombre
        """
        discovered_mods = {}
        
        for mod_dir in self.mods_directory.iterdir():
            if not mod_dir.is_dir():
                continue
            
            # Buscar archivos .py en el directorio
            py_files = list(mod_dir.glob("*.py"))
            
            for py_file in py_files:
                mod_name = py_file.stem
                json_file = mod_dir / f"{mod_name}.json"
                
                # Verificar que exista el JSON correspondiente
                if not json_file.exists():
                    logger.warning(f"Mod {mod_name}: falta archivo {mod_name}.json")
                    continue
                
                mod_info = ModInfo(mod_name, mod_dir)
                discovered_mods[mod_name] = mod_info
                logger.info(f"Mod descubierto: {mod_name}")
        
        return discovered_mods
    
    def load_mod(self, mod_info: ModInfo) -> bool:
        """Carga un mod específico"""
        try:
            mod_name = mod_info.mod_name
            
            # 1. Cargar datos del JSON
            mod_data = self.mod_api.load_mod_data(mod_name, str(mod_info.json_file))
            
            # 2. Auto-inyectar datos del JSON
            self.mod_api.auto_inject_from_mod_data(mod_name)
            
            # 3. Cargar código Python
            spec = importlib.util.spec_from_file_location(
                f"mod_{mod_name}",
                mod_info.py_file
            )
            
            if spec is None or spec.loader is None:
                logger.error(f"No se pudo crear spec para {mod_name}")
                return False
            
            mod_module = importlib.util.module_from_spec(spec)
            sys.modules[f"mod_{mod_name}"] = mod_module
            spec.loader.exec_module(mod_module)
            
            # 4. Llamar init_mod con API y datos
            if hasattr(mod_module, 'init_mod'):
                mod_module.init_mod(self.mod_api, mod_data)
            
            mod_info.loaded = True
            self.loaded_mods[mod_name] = {
                'info': mod_info,
                'module': mod_module,
                'data': mod_data
            }
            
            logger.info(f"Mod cargado exitosamente: {mod_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando mod {mod_info.mod_name}: {e}", exc_info=True)
            console.print(f"[red]✗ Error cargando {mod_info.mod_name}: {e}[/red]")
            return False
    
    def load_all_mods(self):
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        discovered_mods = self.discover_mods()
        
        if not discovered_mods:
            console.print("[yellow]No se encontraron mods para cargar.[/yellow]")
            return
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Cargando Mods...", total=len(discovered_mods))
            
            loaded_count = 0
            for mod_name, mod_info in discovered_mods.items():
                if mod_info.enabled and self.load_mod(mod_info):
                    loaded_count += 1
                progress.advance(task)
        
        console.print(Panel(f"[bold green]✓ Carga Completada[/bold green]\nMods activos: {loaded_count} de {len(discovered_mods)}", style="cyan"))
    
    def unload_mod(self, mod_name: str) -> bool:
        """Descarga un mod"""
        if mod_name not in self.loaded_mods:
            return False
        
        mod_data = self.loaded_mods[mod_name]
        mod_module = mod_data['module']
        
        if hasattr(mod_module, 'cleanup_mod'):
            try:
                mod_module.cleanup_mod()
            except Exception as e:
                logger.error(f"Error en cleanup de {mod_name}: {e}")
        
        if f"mod_{mod_name}" in sys.modules:
            del sys.modules[f"mod_{mod_name}"]
        
        del self.loaded_mods[mod_name]
        console.print(f"[yellow]Mod descargado: {mod_name}[/yellow]")
        return True
    
    def get_loaded_mods_info(self) -> List:
        """Retorna información de mods cargados"""
        return [mod_data['info'] for mod_data in self.loaded_mods.values()]
    
    def display_mods_info(self):
        """Muestra información de mods cargados"""
        if not self.loaded_mods:
            console.print("[yellow]No hay mods cargados[/yellow]")
            return

        if Table is None:
            console.print("Mods Cargados:")
            for mod_name in self.loaded_mods.keys():
                console.print(f"- {mod_name}")
            return

        table = Table(title="Mods Cargados")
        table.add_column("Nombre", style="cyan")
        table.add_column("Archivo", style="green")

        for mod_name, mod_data in self.loaded_mods.items():
            table.add_row(mod_name, f"{mod_name}.py + {mod_name}.json")

        console.print(table)


# Singleton
mod_loader: Optional[ModLoader] = None

def get_mod_api():
    """Retorna la instancia de ModAPI"""
    return get_mod_loader().mod_api

def get_mod_loader():
    """Retorna la instancia del ModLoader"""
    global mod_loader
    if mod_loader is None:
        mod_loader = ModLoader()
    return mod_loader

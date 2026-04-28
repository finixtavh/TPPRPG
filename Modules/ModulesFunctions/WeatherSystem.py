import random
import time
from typing import Dict, Any

class WeatherType:
    def __init__(self, id_name: str, name: str, icon: str, description: str, 
                 player_enemy_mods: Dict[str, float], guild_mods: Dict[str, float], probability: int):
        self.id = id_name
        self.name = name
        self.icon = icon
        self.description = description
        
        # Multiplicadores para combate de Jugador/Enemigo/Compañeros
        # Ej: {"attack": 0.9, "defense": 0.95, "magic_def": 0.8, "agi": 1.0, "counter": 1.0, "evasion": 1.0}
        self.combat_mods = {
            "attack": 1.0,
            "defense": 1.0,
            "magic_def": 1.0,
            "agi": 1.0,
            "counter": 1.0,
            "evasion": 1.0
        }
        self.combat_mods.update(player_enemy_mods)
        
        # Multiplicadores para Guilds
        # Ej: {"attack": 0.9, "defense": 0.95}
        self.guild_mods = {
            "attack": 1.0,
            "defense": 1.0
        }
        self.guild_mods.update(guild_mods)
        
        self.probability = probability

class WeatherManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WeatherManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
        
    def _init(self):
        self.weathers = {
            "viento_suave": WeatherType(
                "viento_suave", "Viento Suave", "🍃", "Un clima perfecto para viajar y pelear.",
                player_enemy_mods={},
                guild_mods={},
                probability=40
            ),
            "soleado": WeatherType(
                "soleado", "Soleado", "☀️", "El sol brilla, inspirando ferocidad en combate.",
                player_enemy_mods={"attack": 1.05},
                guild_mods={"attack": 1.05},
                probability=25
            ),
            "extra_caluroso": WeatherType(
                "extra_caluroso", "Extra Caluroso", "🔥", "El calor agobia, debilitando el ataque y las defensas.",
                player_enemy_mods={"attack": 0.90, "defense": 0.95, "magic_def": 0.80},
                guild_mods={"attack": 0.90, "defense": 0.90},
                probability=10
            ),
            "tormenta": WeatherType(
                "tormenta", "Tormenta Fuerte", "⛈️", "Rayos y truenos dificultan los movimientos rápidos.",
                player_enemy_mods={"agi": 0.50, "counter": 0.75},
                guild_mods={"attack": 0.80, "defense": 1.10},
                probability=10
            ),
            "niebla": WeatherType(
                "niebla", "Niebla Densa", "🌫️", "Es imposible ver más allá de unos metros.",
                player_enemy_mods={"attack": 0.85, "evasion": 1.30},
                guild_mods={"attack": 0.70, "defense": 1.20},
                probability=10
            ),
            "nevada": WeatherType(
                "nevada", "Nevada Intensa", "❄️", "El frío ralentiza a las tropas y entumece los músculos.",
                player_enemy_mods={"agi": 0.80, "defense": 0.90},
                guild_mods={"attack": 0.80, "defense": 1.05},
                probability=5
            )
        }
        self.current_weather = self.weathers["viento_suave"]
        self.last_change_time = time.time()
        self.change_interval = 600  # Cambia cada 10 minutos (600 segundos) de juego real
        
    def check_and_update_weather(self) -> bool:
        """Verifica si es hora de cambiar el clima. Retorna True si cambió."""
        if time.time() - self.last_change_time > self.change_interval:
            self._roll_new_weather()
            return True
        return False
        
    def _roll_new_weather(self):
        choices = list(self.weathers.values())
        weights = [w.probability for w in choices]
        self.current_weather = random.choices(choices, weights=weights, k=1)[0]
        self.last_change_time = time.time()
        
    def get_current_weather(self) -> WeatherType:
        self.check_and_update_weather()
        return self.current_weather

    def register_weather(self, weather_data: Dict[str, Any]):
        """Registra un nuevo tipo de clima."""
        id_name = weather_data.get("id")
        if not id_name:
            return
        
        self.weathers[id_name] = WeatherType(
            id_name=id_name,
            name=weather_data.get("name", id_name),
            icon=weather_data.get("icon", "❓"),
            description=weather_data.get("description", ""),
            player_enemy_mods=weather_data.get("player_enemy_mods", {}),
            guild_mods=weather_data.get("guild_mods", {}),
            probability=weather_data.get("probability", 10)
        )

def get_weather_manager() -> WeatherManager:
    return WeatherManager()

def apply_weather_combat_mods(base_val: float, mod_key: str) -> float:
    """Aplica el multiplicador del clima actual a un stat de combate."""
    wm = get_weather_manager()
    w = wm.get_current_weather()
    return base_val * w.combat_mods.get(mod_key, 1.0)

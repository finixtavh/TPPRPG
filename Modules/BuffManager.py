import json
import os
from typing import List, Dict, Optional, Any
from copy import deepcopy


class Buff:
    """Representa un buff o debuff individual aplicado a una entidad"""
    
    def __init__(self, buff_id: str, data: Dict, source: str = "skill", 
                 permanent: bool = False, buff_after_unequip: int = 0):
        """
        Inicializa un buff/debuff
        
        Args:
            buff_id: ID del buff (ej: "1_buff", "5_debuff")
            data: Datos del buff desde JSON
            source: Origen del buff ("skill", "item", "potion")
            permanent: Si es True, dura mientras el item esté equipado
            buff_after_unequip: Turnos que dura después de desequipar
        """
        self.buff_id = buff_id
        self.name = data.get("Name", "Unknown")
        self.description = data.get("Description", "")
        self.duration_base = data.get("Duration", 3)
        self.duration_current = self.duration_base if not permanent else 9999
        self.type = data.get("Type", "flat")
        self.effects = data.get("Effects", {})
        self.icon = data.get("Icon", "✨")
        self.source = source
        self.permanent = permanent
        self.buff_after_unequip = buff_after_unequip
        self.is_debuff = "_debuff" in buff_id
        
        # Para tracking de aplicación
        self.applied = False
        self.stack_penalty = 1.0  # Penalización por stacking (1.0 = 100%)
    
    def tick(self) -> bool:
        """
        Reduce la duración en 1 turno
        
        Returns:
            True si el buff sigue activo, False si expiró
        """
        if self.permanent:
            return True
        
        self.duration_current -= 1
        return self.duration_current > 0
    
    def get_display_name(self) -> str:
        """Obtiene el nombre para mostrar con icono"""
        turns_left = f"({self.duration_current}T)" if not self.permanent else "(∞)"
        penalty_str = f" [{int(self.stack_penalty * 100)}%]" if self.stack_penalty < 1.0 else ""
        return f"{self.icon} {self.name} {turns_left}{penalty_str}"
    
    def copy(self):
        """Crea una copia del buff"""
        new_buff = Buff(self.buff_id, {
            "Name": self.name,
            "Description": self.description,
            "Duration": self.duration_base,
            "Type": self.type,
            "Effects": deepcopy(self.effects),
            "Icon": self.icon
        }, self.source, self.permanent, self.buff_after_unequip)
        new_buff.duration_current = self.duration_current
        new_buff.applied = self.applied
        new_buff.stack_penalty = self.stack_penalty
        return new_buff


class BuffManager:
    """Gestor central del sistema de buffs/debuffs"""
    
    # Penalties por stacking (diminishing returns)
    STACK_PENALTIES = {
        1: 1.00,  # 100%
        2: 0.75,  # 75%
        3: 0.35,  # 35%
        4: 0.09,  # 9%
        5: 0.03,  # 3% (y más)
    }
    
    def __init__(self, buffs_json_path: str = "./Data/DataBuffs.json"):
        """Inicializa el gestor de buffs"""
        self.buffs_json_path = buffs_json_path
        self.buffs_data = {}
        self.debuffs_data = {}
        self.load_buffs()
    
    def load_buffs(self) -> bool:
        """Carga los buffs y debuffs desde JSON"""
        try:
            if not os.path.exists(self.buffs_json_path):
                print(f"[WARNING] {self.buffs_json_path} no encontrado")
                return False
            
            with open(self.buffs_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.buffs_data = data.get("BUFFS", {})
            self.debuffs_data = data.get("DEBUFFS", {})
            
            print(f"[SUCCESS] {len(self.buffs_data)} buffs y {len(self.debuffs_data)} debuffs cargados")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al cargar buffs: {e}")
            return False
    
    def create_buff(self, buff_id: str, source: str = "skill", 
                    permanent: bool = False, buff_after_unequip: int = 0) -> Optional[Buff]:
        """
        Crea una instancia de buff/debuff
        
        Args:
            buff_id: ID del buff (ej: "1_buff", "5_debuff")
            source: Origen del buff
            permanent: Si dura mientras esté equipado
            buff_after_unequip: Turnos extra después de desequipar
            
        Returns:
            Instancia de Buff o None si no existe
        """
        # Buscar en buffs o debuffs
        if "_buff" in buff_id:
            data = self.buffs_data.get(buff_id)
        else:
            data = self.debuffs_data.get(buff_id)
        
        if not data:
            print(f"[WARNING] Buff/Debuff {buff_id} no encontrado")
            return None
        
        return Buff(buff_id, data, source, permanent, buff_after_unequip)
    
    def apply_buffs_to_entity(self, entity, active_buffs: List[Buff]) -> Dict[str, float]:
        """
        Aplica todos los buffs activos a una entidad
        
        Args:
            entity: El jugador o enemigo
            active_buffs: Lista de buffs activos
            
        Returns:
            Dict con los modificadores totales aplicados
        """
        if not active_buffs:
            return {}
        
        # Agrupar buffs por tipo de efecto para aplicar penalties
        effects_by_stat = self._group_buffs_by_stat(active_buffs)
        
        # Aplicar penalties de stacking
        self._apply_stacking_penalties(effects_by_stat, active_buffs)
        
        # Calcular modificadores totales
        total_modifiers = {}
        
        for buff in active_buffs:
            if buff.applied:
                continue
            
            for effect_name, effect_value in buff.effects.items():
                # Aplicar penalty de stacking
                modified_value = effect_value * buff.stack_penalty
                
                # Acumular en modificadores totales
                if effect_name not in total_modifiers:
                    total_modifiers[effect_name] = 0
                total_modifiers[effect_name] += modified_value
            
            buff.applied = True
        
        return total_modifiers
    
    def _group_buffs_by_stat(self, buffs: List[Buff]) -> Dict[str, List[Buff]]:
        """
        Agrupa buffs por stat que modifican
        
        Returns:
            Dict donde key = stat name, value = lista de buffs que lo modifican
        """
        grouped = {}
        
        for buff in buffs:
            for effect_name in buff.effects.keys():
                if effect_name not in grouped:
                    grouped[effect_name] = []
                grouped[effect_name].append(buff)
        
        return grouped
    
    def _apply_stacking_penalties(self, effects_by_stat: Dict[str, List[Buff]], 
                                   all_buffs: List[Buff]):
        """
        Aplica penalties de stacking a buffs que modifican el mismo stat
        
        PARA BUFFS: El que da más va primero (100%), luego 75%, 35%, 9%, 3%
        PARA DEBUFFS: El que quita más va primero (100%), luego 75%, 35%, 9%, 3%
        """
        for stat, buffs_for_stat in effects_by_stat.items():
            if len(buffs_for_stat) <= 1:
                # Solo un buff afecta este stat, sin penalty
                continue
            
            # Ordenar buffs por valor absoluto (mayor primero)
            buffs_for_stat.sort(
                key=lambda b: abs(b.effects.get(stat, 0)),
                reverse=True
            )
            
            # Aplicar penalties
            for idx, buff in enumerate(buffs_for_stat, 1):
                # Obtener penalty según posición
                penalty_key = min(idx, 5)  # Máximo 5
                penalty = self.STACK_PENALTIES[penalty_key]
                
                # Aplicar la penalty más restrictiva si el buff afecta múltiples stats
                buff.stack_penalty = min(buff.stack_penalty, penalty)
    
    def remove_buffs_from_entity(self, entity, buffs_to_remove: List[Buff]) -> Dict[str, float]:
        """
        Remueve los efectos de buffs de una entidad
        
        Args:
            entity: El jugador o enemigo
            buffs_to_remove: Lista de buffs a remover
            
        Returns:
            Dict con los modificadores que se removieron
        """
        removed_modifiers = {}
        
        for buff in buffs_to_remove:
            if not buff.applied:
                continue
            
            for effect_name, effect_value in buff.effects.items():
                # Usar el valor con penalty aplicado
                modified_value = effect_value * buff.stack_penalty
                
                if effect_name not in removed_modifiers:
                    removed_modifiers[effect_name] = 0
                removed_modifiers[effect_name] += modified_value
            
            buff.applied = False
        
        return removed_modifiers
    
    def tick_buffs(self, active_buffs: List[Buff]) -> List[Buff]:
        """
        Reduce la duración de todos los buffs en 1 turno
        
        Args:
            active_buffs: Lista de buffs activos
            
        Returns:
            Lista de buffs que expiraron
        """
        expired = []
        
        for buff in active_buffs:
            if not buff.tick():
                expired.append(buff)
        
        return expired
    
    def list_all_buffs(self, detailed: bool = False):
        """Muestra todos los buffs disponibles"""
        print("\n" + "="*70)
        print("BUFFS DISPONIBLES".center(70))
        print("="*70)
        
        for buff_id, buff_data in self.buffs_data.items():
            name = buff_data.get("Name", buff_id)
            duration = buff_data.get("Duration", "?")
            icon = buff_data.get("Icon", "✨")
            
            if detailed:
                print(f"\n{icon} {name} (ID: {buff_id})")
                print(f"   Duración: {duration} turnos")
                print(f"   Descripción: {buff_data.get('Description', 'N/A')}")
                print(f"   Efectos:")
                for effect, value in buff_data.get("Effects", {}).items():
                    print(f"      - {effect}: +{value}")
            else:
                print(f"  {icon} {name} ({duration}T) - {buff_id}")
        
        print("\n" + "="*70)
        print("DEBUFFS DISPONIBLES".center(70))
        print("="*70)
        
        for debuff_id, debuff_data in self.debuffs_data.items():
            name = debuff_data.get("Name", debuff_id)
            duration = debuff_data.get("Duration", "?")
            icon = debuff_data.get("Icon", "⚠️")
            
            if detailed:
                print(f"\n{icon} {name} (ID: {debuff_id})")
                print(f"   Duración: {duration} turnos")
                print(f"   Descripción: {debuff_data.get('Description', 'N/A')}")
                print(f"   Efectos:")
                for effect, value in debuff_data.get("Effects", {}).items():
                    print(f"      - {effect}: {value}")
            else:
                print(f"  {icon} {name} ({duration}T) - {debuff_id}")
        
        print("="*70)


# Instancia global
_buff_manager_instance: Optional[BuffManager] = None

def get_buff_manager(buffs_path: str = "./Data/DataBuffs.json") -> BuffManager:
    """Obtiene la instancia global del BuffManager (Singleton)"""
    global _buff_manager_instance
    
    if _buff_manager_instance is None:
        _buff_manager_instance = BuffManager(buffs_path)
    
    return _buff_manager_instance


def apply_buff_to_player(player, buff_id: str, source: str = "skill",
                         permanent: bool = False, buff_after_unequip: int = 0):
    """
    Función helper para aplicar un buff a un jugador
    
    Args:
        player: Objeto del jugador
        buff_id: ID del buff
        source: Origen del buff
        permanent: Si es permanente
        buff_after_unequip: Turnos después de desequipar
    """
    manager = get_buff_manager()
    buff = manager.create_buff(buff_id, source, permanent, buff_after_unequip)
    
    if buff:
        # Inicializar lista de buffs si no existe
        if not hasattr(player, 'active_buffs'):
            player.active_buffs = []
        
        player.active_buffs.append(buff)
        print(f"[SUCCESS] {buff.get_display_name()} aplicado a {player.name}")
        
        return True
    return False


def remove_buff_from_player(player, buff_id: str):
    """
    Remueve un buff específico del jugador
    
    Args:
        player: Objeto del jugador
        buff_id: ID del buff a remover
    """
    if not hasattr(player, 'active_buffs'):
        return False
    
    for i, buff in enumerate(player.active_buffs):
        if buff.buff_id == buff_id:
            player.active_buffs.pop(i)
            print(f"[INFO] {buff.name} removido de {player.name}")
            return True
    
    return False


def process_turn_buffs(player):
    """
    Procesa buffs al final de cada turno (reduce duración y remueve expirados)
    
    Args:
        player: Objeto del jugador
    """
    if not hasattr(player, 'active_buffs') or not player.active_buffs:
        return
    
    manager = get_buff_manager()
    
    # Tick todos los buffs
    expired = manager.tick_buffs(player.active_buffs)
    
    # Remover buffs expirados
    for buff in expired:
        player.active_buffs.remove(buff)
        print(f"[INFO] {buff.name} ha expirado")

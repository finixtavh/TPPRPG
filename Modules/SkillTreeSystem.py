import json
import os
from typing import Dict, Any
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel

console = Console()

class SkillTreeNode:
    def __init__(self, node_id: str, data: Dict[str, Any]):
        self.node_id = node_id
        self.name = data.get("name", "Unknown Node")
        self.desc = data.get("desc", "")
        self.base_cost = data.get("cost", 1)
        self.cost_increment = data.get("cost_increment", 0)
        self.max_level = data.get("max_level", 1)
        self.requires = data.get("requires", [])
        self.effects = data.get("effects", {})

    def get_current_cost(self, current_level: int) -> int:
        return self.base_cost + (current_level * self.cost_increment)

class SkillTreeManager:
    def __init__(self):
        self.nodes = {}
        self.load_tree()

    def load_tree(self):
        path = os.path.join("Data", "DataSkillTree.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for node_id, node_data in data.get("nodes", {}).items():
                    self.nodes[node_id] = SkillTreeNode(node_id, node_data)
        except Exception as e:
            console.print(f"[red]Error loading DataSkillTree.json: {e}[/red]")

    def build_rich_tree(self, player) -> Tree:
        # Encontrar el root node
        root_ids = [nid for nid, n in self.nodes.items() if not n.requires]
        if not root_ids:
            return Tree("[red]Error: Árbol corrupto, sin raíces.[/red]")
        
        main_tree = Tree(f"🌱 [bold green]Árbol de Habilidades de {player.name}[/bold green]")
        
        # Función recursiva para añadir ramas
        def add_branches(parent_node_id, current_tree):
            children = [nid for nid, n in self.nodes.items() if parent_node_id in n.requires]
            for child_id in children:
                node = self.nodes[child_id]
                
                # Estado del nodo
                current_level = player.skills_purchased.get(child_id, 0)
                is_maxed = current_level >= node.max_level
                is_unlockable = all(req in player.skills_purchased for req in node.requires)
                
                cost = node.get_current_cost(current_level)
                
                if is_maxed:
                    label = f"❇️  [bold yellow]{node.name}[/] [dim](Máx Nv.{current_level})[/]\n  [dim italic]└ {node.desc}[/]"
                elif current_level > 0:
                    if player.lvlPoints >= cost:
                        label = f"🔼 [bold green]{node.name}[/] [green](Nv.{current_level}/{node.max_level} - Mejora Costo: {cost} pts)[/]\n  [dim italic]└ {node.desc}[/]"
                    else:
                        label = f"🔴 [dim]{node.name} (Nv.{current_level}/{node.max_level} - Mejora Costo: {cost} pts) - Pts insuficientes[/]\n  [dim italic]└ {node.desc}[/]"
                elif is_unlockable:
                    if player.lvlPoints >= cost:
                        label = f"🟢 [bold cyan]{node.name}[/] [cyan](Costo: {cost} pts)[/]\n  [dim italic]└ {node.desc}[/]"
                    else:
                        label = f"🔴 [dim]{node.name} (Costo: {cost} pts) - Pts. Insuficientes[/]\n  [dim italic]└ {node.desc}[/]"
                else:
                    label = f"🔒 [dim]{node.name} (Bloqueado)[/]\n  [dim italic]└ Requiere ramificación previa.[/]"
                
                branch = current_tree.add(label)
                add_branches(child_id, branch)

        for root_id in root_ids:
            node = self.nodes[root_id]
            label = f"🌟 [bold magenta]{node.name}[/] [dim](Origen)[/]"
            root_branch = main_tree.add(label)
            
            # Garantizar que las raices siempre estén poseidas
            if root_id not in player.skills_purchased:
                player.skills_purchased[root_id] = 1
                
            add_branches(root_id, root_branch)
            
        return main_tree

    def apply_node_effects(self, player, node: SkillTreeNode):
        """Aplica los efectos de un nodo de forma permanente."""
        for stat, value in node.effects.items():
            if stat == "Health_max":
                player.Health_max += value
                if value > 0:
                    player.Health += value
            elif stat == "Mana_max":
                player.Mana_max += value
                if value > 0:
                    player.Mana += value
            elif stat == "DEF":
                for i in range(5):
                    player.DEF[i] += value[i]
            elif stat == "DefensePercentage":
                for i in range(5):
                    player.DefensePercentage[i] += value[i]
            elif hasattr(player, stat):
                actual = getattr(player, stat)
                setattr(player, stat, actual + value)

    def open_menu(self, player):
        from Modules.input_utils import interactive_menu_select
        
        # Asegurarse que el tracking exista (retrocompatibilidad a dict)
        if hasattr(player, "skills_purchased") and isinstance(player.skills_purchased, list):
            new_dict = {}
            for item in player.skills_purchased:
                new_dict[item] = 1
            player.skills_purchased = new_dict
        elif not hasattr(player, "skills_purchased"):
            player.skills_purchased = {}
            
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            console.clear()
            tree_vis = self.build_rich_tree(player)
            console.print(Panel(tree_vis, border_style="green", title=f" Puntos Disponibles: [bold yellow]{player.lvlPoints}[/] "))
            
            available_options = []
            available_options.append((0, "Salir del Menú de Habilidades"))
            
            # Create a map to link integer logic to node ID
            idx_to_nid = {}
            current_opt_idx = 1
            
            for nid, node in self.nodes.items():
                current_level = player.skills_purchased.get(nid, 0)
                if current_level >= node.max_level:
                    continue
                    
                can_unlock = all(req in player.skills_purchased for req in node.requires)
                        
                if can_unlock:
                    cost = node.get_current_cost(current_level)
                    txt = f"Mejorar {node.name} a Nv.{current_level+1} (Cuesta {cost} pts)" if current_level > 0 else f"Desbloquear {node.name} (Cuesta {cost} pts)"
                    if player.lvlPoints < cost:
                        txt += " [red](Puntos Insuficientes)[/]"
                    available_options.append((current_opt_idx, txt))
                    idx_to_nid[current_opt_idx] = nid
                    current_opt_idx += 1
                    
            if len(available_options) == 1:
                console.print("\n[dim]Ya completaste todas las ramas o no hay puntos suficientes para nada.[/dim]")
            
            eleccion = interactive_menu_select(
                title="Desbloqueo de Habilidades",
                subtitle="Elige tu camino",
                options=available_options,
                prompt="Selección: ",
                default_value=0
            )
            
            if eleccion == 0:
                break
                
            selected_nid = idx_to_nid.get(eleccion)
            node = self.nodes.get(selected_nid) if selected_nid else None
            
            if node:
                current_level = player.skills_purchased.get(node.node_id, 0)
                cost = node.get_current_cost(current_level)
                if player.lvlPoints >= cost:
                    player.lvlPoints -= cost
                    player.skills_purchased[node.node_id] = current_level + 1
                    self.apply_node_effects(player, node)
                    console.print(f"\n[bold green]¡Has mejorado: {node.name} a Nivel {current_level+1}![/]")
                    import time; time.sleep(1)
                else:
                    console.print(f"\n[bold red]Puntos insuficientes. Necesitas {cost}.[/]")
                    import time; time.sleep(1.5)

# Instancia global pre-cargada
skill_tree_manager = SkillTreeManager()

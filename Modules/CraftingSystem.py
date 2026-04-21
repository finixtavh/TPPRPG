import json
import os
import time
from rich.console import Console
from rich.panel import Panel

console = Console()

class cRecipe:
    def __init__(self, data: dict):
        self.recipe_id = data.get("recipe_id")
        self.name = data.get("name")
        self.result_item_id = data.get("result_item_id")
        self.result_item_type = data.get("result_item_type")  # e.g., Weapon, Tool, Object
        self.materials_required = data.get("materials_required", {})
        self.description = data.get("description", "")
        self.gold_cost = data.get("gold_cost", 0)

class CraftingManager:
    def __init__(self):
        self.recipes = []
        self.load_recipes()

    def load_recipes(self):
        path = os.path.join("Data", "DataRecipes.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r_data in data.get("recipes", []):
                    self.recipes.append(cRecipe(r_data))
        except Exception as e:
            console.print(f"[red]Error loading DataRecipes.json: {e}[/red]")

    def count_material(self, vInventory, material_name: str) -> int:
        count = 0
        for item in vInventory.Objects:
            name = getattr(item, "Name", getattr(item, "name", ""))
            if name.lower() == material_name.lower():
                count += 1
        return count

    def consume_materials(self, vInventory, material_name: str, amount: int):
        consumed = 0
        items_to_remove = []
        for item in vInventory.Objects:
            name = getattr(item, "Name", getattr(item, "name", ""))
            if name.lower() == material_name.lower():
                items_to_remove.append(item)
                consumed += 1
                if consumed >= amount:
                    break
                    
        for item in items_to_remove:
            vInventory.remove_item(item, 1)

def open_crafting_menu(player, vInventory):
    from Modules.input_utils import interactive_menu_select
    from Modules.ItemManager import get_item_manager
    item_manager = get_item_manager()
    cm = CraftingManager()
    
    while True:
        console.clear()
        console.print(Panel("[yellow]⚒  Yunque de Crafteo ⚒[/]", style="bold bright_black", subtitle=f"Oro: {int(player.Gold)}g"))
        
        options = [(0, "Salir de la Mesa de Crafteo")]
        for idx, recipe in enumerate(cm.recipes, 1):
            req_texts = []
            can_craft = True
            for mat_name, amount in recipe.materials_required.items():
                in_inv = cm.count_material(vInventory, mat_name)
                color = "green" if in_inv >= amount else "red"
                req_texts.append(f"[{color}]{mat_name} ({in_inv}/{amount})[/]")
                if in_inv < amount:
                    can_craft = False
                    
            if player.Gold < recipe.gold_cost:
                can_craft = False
                
            req_str = ", ".join(req_texts)
            estado_oro = f"[green]{recipe.gold_cost}g[/]" if player.Gold >= recipe.gold_cost else f"[red]{recipe.gold_cost}g[/]"
            
            label = f"[bold cyan]{recipe.name}[/]\n      └ Costo: {estado_oro} | {req_str}"
            options.append((idx, label))
            
        choice = interactive_menu_select(
            title="Recetas Disponibles",
            subtitle="Selecciona qué deseas forjar",
            options=options,
            prompt="Selección: ",
            default_value=0,
            border_style="yellow"
        )
        
        if choice == 0:
            break
            
        selected_recipe = cm.recipes[choice-1]
        
        if player.Gold < selected_recipe.gold_cost:
            console.print(f"[bold red]No tienes oro suficiente para fabricar {selected_recipe.name}.[/]")
            time.sleep(1.5)
            continue
            
        has_all_mats = True
        for mat_name, amount in selected_recipe.materials_required.items():
            if cm.count_material(vInventory, mat_name) < amount:
                has_all_mats = False
                break
                
        if not has_all_mats:
            console.print(f"[bold red]No tienes los materiales requeridos para fabricar {selected_recipe.name}.[/]")
            time.sleep(1.5)
            continue
            
        player.Gold -= selected_recipe.gold_cost
        for mat_name, amount in selected_recipe.materials_required.items():
            cm.consume_materials(vInventory, mat_name, amount)
            
        cat_item = item_manager.get_item_by_id(selected_recipe.result_item_id)
        if cat_item:
            from Modules.setup import cWeapon, cEquippableItems, cObject, cTool
            from Modules.GatheringMasterySystem import cMaterial
            new_item = item_manager.create_item_object(selected_recipe.result_item_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)
            if new_item:
                vInventory.addObject(new_item)
                console.print(f"\n[green]¡Exito! Has forjado un(a) [bold]{selected_recipe.name}[/].[/]")
                time.sleep(2)
            else:
                console.print(f"\n[red]Error al instanciar el item para la receta.[/]")
                time.sleep(1.5)
        else:
            console.print(f"\n[bold red]Error: No se encontró el item ID {selected_recipe.result_item_id} en los registros.[/]")
            time.sleep(2.5)

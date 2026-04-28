import os

files = ["Modules/GuildMenu.py", "Modules/GuildSkillTree.py"]

for fname in files:
    with open(fname, "r") as f:
        content = f.read()
    
    # Force immediate refresh on state change to remove perceived input lag
    content = content.replace("live.update(_render())", "live.update(_render(), refresh=True)")
    
    with open(fname, "w") as f:
        f.write(content)
print("Done")

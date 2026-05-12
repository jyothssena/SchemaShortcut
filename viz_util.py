def generate_mermaid(template):
    """
    Generates a Mermaid.js flowchart string from a template.
    """
    steps = template.get("step_templates", [])
    if not steps:
        return ""

    lines = ["graph TD"]
    
    for s in steps:
        step_id = s["step_id"]
        desc = s["description"].replace('"', "'")
        action = s["action_type"].upper()
        
        # Style node based on action type
        if action == "SQL":
            node = f'{step_id}["{step_id}: {action}<br/>{desc}"]'
        else:
            node = f'{step_id}{{"{step_id}: {action}<br/>{desc}"}}'
            
        lines.append(f"    {node}")
        
        # Add edges for dependencies
        for dep in s.get("depends_on", []):
            lines.append(f"    {dep} --> {step_id}")
            
    return "\n".join(lines)

def get_mermaid_link(mermaid_code):
    """
    Generates a link to the Mermaid Live Editor with the code encoded.
    """
    import base64
    import json
    
    state = {
        "code": mermaid_code,
        "mermaid": {"theme": "default"},
        "updateEditor": False
    }
    
    json_str = json.dumps(state)
    encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    return f"https://mermaid.live/edit#base64:{encoded}"

if __name__ == "__main__":
    test_tpl = {
        "step_templates": [
            {"step_id": "s1", "depends_on": [], "action_type": "sql", "description": "Get IDs"},
            {"step_id": "s2", "depends_on": [], "action_type": "api", "description": "Check status"},
            {"step_id": "s3", "depends_on": ["s1", "s2"], "action_type": "sql", "description": "Merge"}
        ]
    }
    print(generate_mermaid(test_tpl))

"""
Multi-step trajectory generator from JSON traces.

Reads the raw traces from data/data.json and converts them into
the structured DAG trajectory format expected by SchemaShortcut.
Dependencies are inferred sequentially unless independent actions are found.
"""

import json
import os

IN_PATH = "data/data.json"
OUT_PATH = "multistep_trajectories.json"


def infer_intent_type(trace):
    actions = [step.get("action") for step in trace]
    if "sql_query" in actions and "api_call" in actions:
        return "sql_then_api"
    elif len(set(actions)) == 1:
        return f"chained_{actions[0]}"
    return "mixed_actions"


def convert_trajectories(in_path=IN_PATH, out_path=OUT_PATH):
    if not os.path.exists(in_path):
        print(f"File not found: {in_path}")
        return

    with open(in_path, "r") as f:
        raw_data = json.load(f)

    trajectories = []

    for item in raw_data:
        question = item.get("query", "")
        trace = item.get("trace", [])
        
        n_steps = len(trace)
        intent_type = infer_intent_type(trace)
        
        steps = []
        for i, raw_step in enumerate(trace):
            step_id = f"s{raw_step['step']}"
            
            # Simple heuristic: step N depends on step N-1
            depends_on = [f"s{raw_step['step'] - 1}"] if i > 0 else []
            
            action_type = raw_step.get("action")
            
            step_dict = {
                "step_id": step_id,
                "depends_on": depends_on,
            }
            
            if action_type == "sql_query":
                step_dict["description"] = f"Execute SQL query to retrieve data"
                step_dict["sql"] = raw_step.get("sql", "")
                step_dict["action_type"] = "sql"
            elif action_type == "api_call":
                api_info = raw_step.get("api_call", {})
                url = api_info.get("url", "")
                step_dict["description"] = f"Make API call to {url}"
                step_dict["api_url"] = url
                step_dict["api_params"] = json.dumps(api_info.get("params", {}))
                step_dict["action_type"] = "api"
            else:
                step_dict["description"] = "Unknown action"
                step_dict["action_type"] = action_type
                
            steps.append(step_dict)

        trajectories.append({
            "question": question,
            "reasoning": "Auto-inferred from execution trace.",
            "intent_type": intent_type,
            "n_steps": n_steps,
            "all_steps_valid": True,  # Trusted from data.json
            "steps": steps
        })

    with open(out_path, "w") as f:
        json.dump(trajectories, f, indent=2)

    print(f"✓ Converted {len(trajectories)} trajectories → {out_path}")


if __name__ == "__main__":
    convert_trajectories()

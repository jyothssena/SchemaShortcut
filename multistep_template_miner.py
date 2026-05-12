"""
Multi-step template miner.
Extracts the DAG shape from each trajectory — which steps are independent
(parallel candidates) vs sequential — and saves a template library.
"""

import json
from collections import defaultdict

IN_PATH  = "multistep_trajectories.json"
OUT_PATH = "multistep_templates.json"

SLOT_VALUES = {
    "campaign_name": ["Birthday Message", "Gold Tier Welcome Email"],
    "state": ["deployed", "redeployed", "created", "updated", "live", "failed", "enabled"],
    "destination": ["SMS Opt-In", "amazon-s3"],
    "segment_name": ["Gender: Male"],
    "limit": ["50", "10", "5"],
    "date": ["2026-03-31", "2026-03-29", "2026-04-14"]
}


def dag_shape(steps):
    """
    Classify the DAG as:
      linear     — each step depends on the previous (pure ReAct chain)
      fork       — one step feeds multiple independent branches
      merge      — multiple independent steps feed one final step
      mixed      — combination
    """
    ids = [s["step_id"] for s in steps]
    dep_map = {s["step_id"]: s["depends_on"] for s in steps}

    roots    = [sid for sid, deps in dep_map.items() if not deps]
    leaves   = [sid for sid in ids if not any(sid in dep_map[o] for o in ids)]
    parallel = [sid for sid in ids if not dep_map[sid]]  # no dependencies = can run first

    if len(roots) > 1:
        shape = "merge"       # multiple independent starts joining later
    elif len(leaves) > 1:
        shape = "fork"        # one root fans out
    elif all(len(dep_map[sid]) <= 1 for sid in ids):
        shape = "linear"
    else:
        shape = "mixed"

    return {
        "shape":    shape,
        "roots":    roots,
        "leaves":   leaves,
        "parallel_candidates": parallel,
        "n_parallel": len(parallel),
    }


def parameterize(text):
    if not isinstance(text, str):
        return text
    for slot, values in SLOT_VALUES.items():
        for val in values:
            text = text.replace(val, f"{{{slot}}}")
    return text


def mine(in_paths=[IN_PATH, "learned_trajectories.json"], out_path=OUT_PATH):
    all_trajectories = []
    for path in in_paths:
        if os.path.exists(path):
            with open(path) as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_trajectories.extend(data)
                except:
                    continue

    templates = []
    by_type = defaultdict(list)

    for t in all_trajectories:
        # Convert steps to match the expected format if needed
        steps = t.get("steps") or t.get("step_templates")
        if not steps:
            continue
            
        shape = dag_shape(steps)
        q_template = parameterize(t["question"] if "question" in t else t.get("example_question", ""))

        step_templates = []
        for s in steps:
            tpl_step = {
                "step_id":    s["step_id"],
                "depends_on": s["depends_on"],
                "description": parameterize(s["description"]),
                "can_parallel": len(s["depends_on"]) == 0,
                "action_type": s.get("action_type", "unknown")
            }
            
            if "sql" in s or "sql_template" in s:
                tpl_step["sql_template"] = parameterize(s.get("sql") or s.get("sql_template"))
            if "api_url" in s or "api_url_template" in s:
                tpl_step["api_url_template"] = parameterize(s.get("api_url") or s.get("api_url_template"))
            if "api_params" in s or "api_params_template" in s:
                tpl_step["api_params_template"] = parameterize(s.get("api_params") or s.get("api_params_template"))
                
            step_templates.append(tpl_step)

        tpl = {
            "template_id":         f"mtpl_{len(templates)+1:03d}",
            "intent_type":         t.get("intent_type", "adhoc"),
            "n_steps":             len(steps),
            "dag_shape":           shape["shape"],
            "n_parallel_steps":    shape["n_parallel"],
            "question_template":   q_template,
            "step_templates":      step_templates,
            "example_question":    t.get("question") or t.get("example_question", ""),
            "react_turn_cost":     len(steps) * 2,
            "schemaShortcut_turns": 2 + (1 if shape["n_parallel"] < len(steps) else 0),
        }
        templates.append(tpl)

    with open(out_path, "w") as f:
        json.dump(templates, f, indent=2)

    return len(templates)


if __name__ == "__main__":
    mine()

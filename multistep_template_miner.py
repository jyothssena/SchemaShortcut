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


def mine(in_path=IN_PATH, out_path=OUT_PATH):
    with open(in_path) as f:
        trajectories = json.load(f)

    templates = []
    by_type = defaultdict(list)

    for t in trajectories:
        if not t.get("all_steps_valid"):
            continue

        shape = dag_shape(t["steps"])
        q_template = parameterize(t["question"])

        step_templates = []
        for s in t["steps"]:
            tpl_step = {
                "step_id":    s["step_id"],
                "depends_on": s["depends_on"],
                "description": parameterize(s["description"]),
                "can_parallel": len(s["depends_on"]) == 0,
                "action_type": s.get("action_type", "unknown")
            }
            
            if "sql" in s:
                tpl_step["sql_template"] = parameterize(s["sql"])
            if "api_url" in s:
                tpl_step["api_url_template"] = parameterize(s["api_url"])
            if "api_params" in s:
                tpl_step["api_params_template"] = parameterize(s["api_params"])
                
            step_templates.append(tpl_step)

        tpl = {
            "template_id":         f"mtpl_{len(templates)+1:03d}",
            "intent_type":         t["intent_type"],
            "n_steps":             t["n_steps"],
            "dag_shape":           shape["shape"],
            "n_parallel_steps":    shape["n_parallel"],
            "question_template":   q_template,
            "step_templates":      step_templates,
            "example_question":    t["question"],
            "react_turn_cost":     t["n_steps"] * 2,       # think+act per step
            "schemaShortcut_turns": 2 + (1 if shape["n_parallel"] < t["n_steps"] else 0),
        }
        templates.append(tpl)
        by_type[t["intent_type"]].append(tpl)

    with open(out_path, "w") as f:
        json.dump(templates, f, indent=2)

    print(f"✓ {len(templates)} templates → {out_path}\n")
    print(f"{'Template':10s} {'Type':22s} {'Steps':6s} {'DAG':8s} {'Parallel':9s} {'ReAct turns':12s} {'SS turns'}")
    print("-" * 85)
    for t in templates:
        print(f"{t['template_id']:10s} {t['intent_type']:22s} {t['n_steps']:6d} "
              f"{t['dag_shape']:8s} {t['n_parallel_steps']:9d} "
              f"{t['react_turn_cost']:12d} {t['schemaShortcut_turns']}")

    print(f"\nTurn savings summary:")
    total_react = sum(t["react_turn_cost"] for t in templates)
    total_ss    = sum(t["schemaShortcut_turns"] for t in templates)
    print(f"  ReAct total turns:         {total_react}")
    print(f"  SchemaShortcut total turns: {total_ss}")
    print(f"  Reduction:                 {round((1 - total_ss/total_react)*100, 1)}%")


if __name__ == "__main__":
    mine()

import asyncio
import os
import getpass
from planner import Planner, GeminiPlanner
from executor import DAGExecutor

async def main():
    print("🚀 SchemaShortcut Engine Initializing...")
    planner = Planner()
    executor = DAGExecutor()
    gemini_planner = None
    
    print("\nWelcome! Enter your natural language query (or 'exit' to quit).")
    print("Example: 'When was the journey Birthday Message published?'")
    
    while True:
        query = input("\nQuery > ").strip()
        if query.lower() in ["exit", "quit"]:
            break
            
        if not query:
            continue
            
        # 1. Planning
        print(f"Planning execution for: '{query}'...")
        template, slots = planner.plan(query)
        
        if not template:
            print("🔍 No local template match. Falling back to Gemini AI Planning...")
            
            # Initialize Gemini if needed
            if not gemini_planner:
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    print("⚠️  GOOGLE_API_KEY environment variable not found.")
                    api_key = getpass.getpass("Please enter your Google AI API Key: ").strip()
                
                try:
                    gemini_planner = GeminiPlanner(api_key=api_key)
                except Exception as e:
                    print(f"❌ Gemini Initialization Failed: {e}")
                    continue
            
            template = gemini_planner.plan(query)
            slots = {} # Gemini plan is usually ad-hoc and doesn't need slots
            is_new_plan = True if template else False

        if not template:
            print("❌ Error: Could not generate a plan for this query.")
            continue
            
        print(f"✅ Plan Generated: {template['template_id']} ({template['intent_type']})")
        if slots:
            print(f"🛠  Inferred Slots: {slots}")
        
        # 1.5 Visualization
        from viz_util import generate_mermaid, get_mermaid_link
        mermaid_code = generate_mermaid(template)
        print("\n📊 Execution Plan Visualization (Mermaid):")
        print("-" * 40)
        print(mermaid_code)
        print("-" * 40)
        print(f"🔗 View Live DAG: {get_mermaid_link(mermaid_code)}")
        
        # 2. Execution Loop with Self-Correction
        max_retries = 1
        for attempt in range(max_retries + 1):
            print(f"\n--- Starting Parallel Execution (Attempt {attempt + 1}) ---")
            try:
                results = await executor.run(template, slots)
                print("--- Execution Complete ---\n")
                
                # If it was a new plan from Gemini, save it for the future
                if is_new_plan:
                    print("💾 Saving new plan to learned_trajectories.json...")
                    learned_path = "learned_trajectories.json"
                    learned_data = []
                    if os.path.exists(learned_path):
                        with open(learned_path, "r") as f:
                            try:
                                learned_data = json.load(f)
                            except:
                                learned_data = []
                    
                    template["example_question"] = query
                    learned_data.append(template)
                    
                    with open(learned_path, "w") as f:
                        json.dump(learned_data, f, indent=2)
                    
                    from multistep_template_miner import mine
                    count = mine()
                    print(f"🔄 Template library refreshed. Total templates: {count}")

                # 3. Final Summary
                for step_id, res in results.items():
                    print(f"Step {step_id} Result Preview: {str(res)[:200]}...")
                break # Success!
                
            except Exception as e:
                print(f"❌ Execution Error: {e}")
                if attempt < max_retries and gemini_planner:
                    print("🔄 Attempting Self-Correction with Gemini...")
                    new_template = gemini_planner.fix_plan(query, template, str(e))
                    if new_template:
                        template = new_template
                        print("✨ Gemini provided a corrected plan. Retrying...")
                    else:
                        print("❌ Gemini failed to provide a correction.")
                        break
                else:
                    break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

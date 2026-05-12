import asyncio
import duckdb
import json
import time
from datetime import datetime

class DAGExecutor:
    def __init__(self, db_path="data/DBSnapshot/*.parquet"):
        self.conn = duckdb.connect()
        # Create views for all parquet files
        import glob
        for f in glob.glob("data/DBSnapshot/*.parquet"):
            table_name = f.split("/")[-1].replace(".parquet", "")
            try:
                self.conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM '{f}'")
            except Exception as e:
                print(f"⚠️ Warning: Skipping {f} due to error: {e}")

    def resolve_placeholders(self, text, slots, results_cache):
        if not isinstance(text, str):
            return text
            
        # 1. Resolve local slots {slot}
        for k, v in slots.items():
            text = text.replace(f"{{{k}}}", str(v))
            
        # 2. Resolve parent results {{s1.column}}
        import re
        placeholders = re.findall(r'\{\{(s\d+)\.(\w+)\}\}', text)
        for step_id, col_name in placeholders:
            parent_result = results_cache.get(step_id)
            if parent_result and hasattr(parent_result, "result"):
                data = parent_result.result()
                if isinstance(data, list) and len(data) > 0:
                    # If it's a list of dicts, get the column from the first row
                    # Or collect all if it's a list
                    if col_name in data[0]:
                        values = [str(row[col_name]) for row in data if col_name in row]
                        # If multiple values, join with commas for SQL IN clauses
                        replacement = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in values])
                        text = text.replace(f"{{{{{step_id}.{col_name}}}}}", replacement)
        return text

    async def execute_task(self, task, slots, results_cache):
        # Wait for dependencies
        if task["depends_on"]:
            await asyncio.gather(*(results_cache[dep] for dep in task["depends_on"]))

        task_id = task["step_id"]
        action_type = task["action_type"]
        
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Starting {task_id} ({action_type})")
        
        start_time = time.time()
        result = None
        
        if action_type == "sql":
            sql = self.resolve_placeholders(task.get("sql_template") or task.get("sql"), slots, results_cache)
            
            await asyncio.sleep(0.5) 
            try:
                # Use fetchdf() to get column names easily
                df = self.conn.execute(sql).fetchdf()
                result = df.to_dict('records')
            except Exception as e:
                raise RuntimeError(f"Step {task_id} SQL failed: {e}")
                
        elif action_type == "api":
            url = self.resolve_placeholders(task.get("api_url_template") or task.get("api_url"), slots, results_cache)
            params_str = self.resolve_placeholders(task.get("api_params_template") or task.get("api_params"), slots, results_cache)
            
            await asyncio.sleep(1.0) 
            # Simulated API failure condition for testing
            if "fail" in url:
                raise RuntimeError(f"Step {task_id} API failed for {url}")
            result = {"status": "success", "data": f"Mocked API Response for {url} with params {params_str}"}

        duration = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Finished {task_id} in {duration:.2f}s")
        return result

    async def run(self, template, slots):
        tasks = template["step_templates"]
        results_cache = {}
        
        # Initialize futures
        for t in tasks:
            results_cache[t["step_id"]] = asyncio.Future()

        # Launch all tasks
        execution_tasks = []
        for t in tasks:
            execution_tasks.append(self.wrap_execution(t, slots, results_cache))

        await asyncio.gather(*execution_tasks)
        
        # Collect final results
        final_results = {}
        for tid, fut in results_cache.items():
            final_results[tid] = fut.result()
        return final_results

    async def wrap_execution(self, task, slots, results_cache):
        res = await self.execute_task(task, slots, results_cache)
        results_cache[task["step_id"]].set_result(res)

if __name__ == "__main__":
    # Test runner
    async def test():
        with open("multistep_templates.json") as f:
            templates = json.load(f)
        exe = DAGExecutor()
        # Find a template with 2+ steps to show parallel potential if any
        # Actually most are linear, let's find a complex one or just run mtpl_001
        print("Running mtpl_001...")
        res = await exe.run(templates[0], {"campaign_name": "Birthday Message", "state": "deployed", "limit": 10})
        print("Results:", res)

    asyncio.run(test())

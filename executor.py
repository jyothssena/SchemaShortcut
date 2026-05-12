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
            sql = task["sql_template"]
            for k, v in slots.items():
                sql = sql.replace(f"{{{k}}}", str(v))
            
            # Simulate some processing delay to show parallelization
            await asyncio.sleep(0.5) 
            try:
                rel = self.conn.execute(sql)
                result = rel.fetchall()
            except Exception as e:
                result = f"Error: {e}"
                
        elif action_type == "api":
            # Mocking API call
            url = task["api_url_template"]
            await asyncio.sleep(1.0) # Network latency simulation
            result = {"status": "success", "data": "Mocked API Response for " + url}

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

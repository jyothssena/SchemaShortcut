import asyncio
from executor import DAGExecutor

async def demo_parallel():
    exe = DAGExecutor()
    
    # Manually define a parallel plan
    # s1 and s2 are independent (both roots)
    # s3 depends on both s1 and s2
    parallel_plan = {
        "template_id": "demo_parallel",
        "step_templates": [
            {
                "step_id": "s1",
                "depends_on": [],
                "action_type": "sql",
                "sql_template": "SELECT count(*) FROM dim_campaign",
                "description": "Counting campaigns"
            },
            {
                "step_id": "s2",
                "depends_on": [],
                "action_type": "api",
                "api_url_template": "https://api.example.com/v1/status",
                "description": "Checking API status"
            },
            {
                "step_id": "s3",
                "depends_on": ["s1", "s2"],
                "action_type": "sql",
                "sql_template": "SELECT name FROM dim_campaign LIMIT 1",
                "description": "Final verification"
            }
        ]
    }
    
    print("🚀 Starting Parallel Demo...")
    print("Expected: s1 and s2 should start at the same time.")
    print("          s3 should wait for both.")
    
    results = await exe.run(parallel_plan, {})
    
    print("\n✅ Demo Complete.")
    print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(demo_parallel())

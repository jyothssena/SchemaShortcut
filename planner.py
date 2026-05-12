import json
import re
import os
import google.generativeai as genai
from schema_util import get_schema_summary

TEMPLATES_PATH = "multistep_templates.json"

class GeminiPlanner:
    def __init__(self, api_key=None):
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found. Please set it in your environment or pass it to the constructor.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.schema_context = get_schema_summary()

    def plan(self, query):
        prompt = f"""
        You are a SQL and API query planner. Given a user question and a database schema, break the question into a sequence of steps (SQL or API).
        
        DATABASE SCHEMA:
        {self.schema_context}
        
        AVAILABLE TOOLS:
        - sql: Use this for database queries.
        - api: Use this for external service calls. 
        Note: The platform has an Adobe Journey Optimizer API at 'https://platform.adobe.io/ajo/journey'.
        
        OUTPUT FORMAT (JSON):
        Return ONLY a JSON object with the following structure:
        {{
            "template_id": "gemini_generated",
            "intent_type": "adhoc_plan",
            "step_templates": [
                {{
                    "step_id": "s1",
                    "depends_on": [],
                    "description": "Short description",
                    "action_type": "sql",
                    "sql_template": "SELECT ... FROM ..."
                }},
                {{
                    "step_id": "s2",
                    "depends_on": ["s1"],
                    "description": "Short description",
                    "action_type": "api",
                    "api_url_template": "https://...",
                    "api_params_template": "{{\\"param\\": \\"value\\"}}"
                }}
            ]
        }}
        
        Ensure steps that can run in parallel have empty 'depends_on' lists.
        
        QUESTION: {query}
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Extract JSON from response text (handle markdown blocks)
            text = response.text
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                plan_json = json.loads(match.group(0))
                return plan_json
            return None
        except Exception as e:
            print(f"❌ Gemini Planning Error: {e}")
            return None

class Planner:
    def __init__(self, templates_path=TEMPLATES_PATH):
        with open(templates_path, "r") as f:
            self.templates = json.load(f)

    def plan(self, query):
        """
        Matches the query to the best template.
        Extracts slot values (entities) from the query.
        """
        best_template = None
        best_score = -1
        
        query_words = set(re.findall(r'\w+', query.lower()))
        
        for tpl in self.templates:
            example_words = set(re.findall(r'\w+', tpl["example_question"].lower()))
            intersection = query_words.intersection(example_words)
            score = len(intersection) / len(example_words) if example_words else 0
            
            if score > best_score:
                best_score = score
                best_template = tpl
        
        if best_score < 0.5: # Higher threshold to trigger Gemini fallback
            return None, {}

        # Extract slot values
        slots = {}
        from multistep_template_miner import SLOT_VALUES
        for slot, values in SLOT_VALUES.items():
            for val in values:
                if val.lower() in query.lower():
                    slots[slot] = val
                    
        return best_template, slots

if __name__ == "__main__":
    p = Planner()
    tpl, slots = p.plan("When was the journey 'Birthday Message' published?")
    print(f"Matched: {tpl['template_id']} with slots: {slots}")

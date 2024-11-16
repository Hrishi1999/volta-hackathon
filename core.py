import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

import anthropic
import httpx
import marqo
from pydantic import BaseModel


class TaskStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"
    CANCELED = "canceled"


class ActionExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    



class MarqoDatabase:
    def __init__(self, url: str = 'http://localhost:8882'):
        self.client = marqo.Client(url=url)
        self.actions_index = "automation-actions"
        self.flows_index = "automation-flows"
        self.executions_index = "automation-executions"
        self.blocks_index = "automation-blocks"
        # self.init_db()

    def init_db(self):
        # Create indices if they don't exist
        for index_name in [self.blocks_index, self.actions_index, self.flows_index, self.executions_index]:
            try:
                self.client.create_index(index_name)
            except Exception:
                # Index already exists
                pass

    async def store_block(self, block_data: Dict) -> str:
        block_id = str(uuid.uuid4())
        document = {
            "_id": block_id,
            "name": block_data["name"],
            "type": block_data["type"],
            "url": block_data["url"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        self.client.index(self.blocks_index).add_documents(
            [document], tensor_fields=["url"])
        return block_id

    async def search_blocks(self, url: str) -> List[Dict]:
        results = self.client.index(self.blocks_index).search(
            q=f'with {url}',
        )
        return [result for result in results["hits"]]

    async def store_action(self, action_data: Dict) -> str:
        action_id = str(uuid.uuid4())
        document = {
            "_id": action_id,
            "block_id": action_data["block_id"],
            "name": action_data["name"],
            "navigation_goal": action_data["navigation_goal"],
            "data_extraction_goal": action_data["data_extraction_goal"],
            "required_inputs": json.dumps(action_data["required_inputs"]),
            "output_schema": json.dumps(action_data["output_schema"]),
            "url": action_data["url"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        self.client.index(self.actions_index).add_documents(
            [document], tensor_fields=["url", "navigation_goal", "data_extraction_goal"])
        return action_id

    async def get_action(self, action_id: str) -> Optional[Dict]:
        try:
            result = self.client.index(
                self.actions_index).get_document(action_id)
            if result:
                return {
                    **result,
                    "required_inputs": json.loads(result["required_inputs"]),
                    "output_schema": json.loads(result["output_schema"])
                }
        except Exception:
            return None

    async def store_flow(self, flow_data: Dict) -> str:
        flow_id = str(uuid.uuid4())
        document = {
            "_id": flow_id,
            "name": flow_data["name"],
            "description": flow_data["description"],
            "actions": json.dumps(flow_data["actions"]),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        self.client.index(self.flows_index).add_documents(
            [document], tensor_fields=["name", "description"])
        return flow_id

    async def store_execution(self, execution_data: Dict) -> str:
        execution_id = str(uuid.uuid4())
        document = {
            "_id": execution_id,
            "flow_id": execution_data.get("flow_id", ""),
            "initial_inputs": json.dumps(execution_data.get("initial_inputs", {})),
            "action_executions": json.dumps(execution_data.get("action_executions", [])),
            "status": execution_data.get("status", ""),
            "started_at": execution_data.get("started_at", datetime.now().isoformat()),
            "completed_at": execution_data.get("completed_at", "")
        }

        self.client.index(self.executions_index).add_documents(
            [document], tensor_fields=["flow_id", "initial_inputs"])
        return execution_id

    async def search_actions(self, query: str) -> List[Dict]:
        results = self.client.index(self.actions_index).search(
            q=query,
            # searchable_attributes=[
            #     "name", "navigation_goal", "data_extraction_goal"]
        )
        return [result for result in results["hits"]]


class FlowExecution:
    def __init__(self, id: str, flow_id: str, initial_inputs: Dict, action_executions: List):
        self.id = id
        self.flow_id = flow_id
        self.initial_inputs = initial_inputs
        self.action_executions = action_executions

    def to_dict(self):
        return {
            "id": self.id,
            "flow_id": self.flow_id,
            "initial_inputs": self.initial_inputs,
            "action_executions": self.action_executions
        }


class LLMService:
    """Service for interacting with Claude."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        
    async def createAppJsx(self, prompt: str, unstructured_data: str) -> str:
        prompt = f"""
        This was the original prompt: {prompt}, use information from that to structure the data
        Given this unstructured data: {unstructured_data}
        Create a modern React App.jsx component that displays this data in a clean, organized way.
        Use modern React patterns, hooks if needed, and proper jsx types.
        Return only the complete App.jsx code, nothing else. JUST RAW CODE"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text


    async def analyze_website(self, url: str, actions: str) -> Dict:
        """Use LLM to analyze website and suggest possible actions."""
        prompt = f"""Given this website URL: {url}
        Suggest possible automation actions that could be performed on this website.
        Consider common user flows and data extraction needs.
        For each action, provide:
        1. Name (short, descriptive)
        2. Navigation goal (specific instructions for Skyvern)
        3. Data to extract (specific data points to collect)
        4. Required user inputs (fields needed from the user)
        5. Output schema (structure of extracted data)
        
        We also have existing actions suggested by the user.
        These are:
        {actions}

        Only give JSON output, no additional text.
        Format your response as JSON with this structure:
        {{
            "actions": [
                {{
                    "name": "action_name",
                    "navigation_goal": "detailed goal",
                    "data_extraction_goal": "what to extract",
                    "required_inputs": ["input1", "input2"],
                    "output_schema": {{
                        "field1": "description1",
                        "field2": "description2"
                    }}
                }}
            ]
        }}"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

    async def generate_sql_query(self, natural_language_query: str) -> str:
        prompt = f"""Given this SQLite database schema:
        - blocks: id, name, type, url, created_at, updated_at
        - actions: id, block_id, name, navigation_goal, data_extraction_goal, required_inputs, output_schema, url, created_at, updated_at
        - flows: id, name, description, actions, created_at, updated_at
        - executions: id, flow_id, initial_inputs, action_executions, status, started_at, completed_at

        Output only the SQL query, nothing else.
        Generate a SQL query for this request: {natural_language_query}
        Return only the SQL query, nothing else."""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content.strip()
    
    
class ReactWriter:
    def __init__(self, llm: LLMService):
        self.llm = llm
        self.app_path = Path("cra/src/App.js")

    async def write_app_jsx(self, prompt: str, unstructured_data: str) -> None:
        # Generate React code using LLM
        react_code = await self.llm.createAppJsx(prompt, unstructured_data)
        
        # Create directories if they don't exist
        self.app_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the generated code to App.js
        with open(self.app_path, "w") as f:
            f.write(react_code)



class SkyvernService:
    """Service for interacting with Skyvern API."""

    def __init__(self, api_key: str, base_url: str = "https://api.skyvern.com/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }

    async def create_task(self, url: str, navigation_goal: str,
                          data_extraction_goal: str,
                          navigation_payload: Optional[Dict] = None) -> Dict:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        
        json = {
            "url": url,
            "navigation_goal": navigation_goal,
            "data_extraction_goal": data_extraction_goal,
            "navigation_payload": navigation_payload or {},
            "proxy_location": "RESIDENTIAL"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks/",
                headers=self.headers,
                json=json
            )
            response.raise_for_status()
            return response.json()

    async def get_task_status(self, task_id: str) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def wait_for_completion(self, task_id: str,
                                  polling_interval: int = 10,
                                  timeout: int = 3000) -> Dict:
        start_time = datetime.now()
        while True:
            if (datetime.now() - start_time).seconds > timeout:
                raise TimeoutError(
                    f"Task {task_id} did not complete within {timeout} seconds")

            status = await self.get_task_status(task_id)
            if status["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED,
                                    TaskStatus.TERMINATED, TaskStatus.CANCELED]:
                return status

            await asyncio.sleep(polling_interval)


class WebsiteBlockManager:
    def __init__(self, db: MarqoDatabase, llm: LLMService):
        self.db = db
        self.llm = llm

    async def create_block(self, name: str, url: str, acts: str) -> Dict:
        block_data = {
            "name": name,
            "type": "website_based",
            "url": url,
            "actions": acts
        }
        block_id = await self.db.store_block(block_data)
        suggestions = await self.llm.analyze_website(url, acts)

        actions = []
        for action_info in suggestions["actions"]:
            action_data = {
                "block_id": block_id,
                "name": action_info["name"],
                "navigation_goal": action_info["navigation_goal"],
                "data_extraction_goal": action_info["data_extraction_goal"],
                "required_inputs": action_info["required_inputs"],
                "output_schema": action_info["output_schema"],
                "url": url
            }
            action_id = await self.db.store_action(action_data)
            actions.append(action_id)

        return {
            "id": block_id,
            "name": name,
            "type": "website_based",
            "url": url,
            "actions": actions
        }

    async def get_action(self, action_id: str) -> Dict:
        return await self.db.get_action(action_id)


class ActionExecution:
    """Tracks the execution of an action."""

    def __init__(self, action_id: str, inputs: Dict):
        self.id = str(uuid.uuid4())
        self.action_id = action_id
        self.inputs = inputs
        self.status = ActionExecutionStatus.PENDING
        self.skyvern_task_id = None
        self.output = None
        self.error = None
        self.started_at = None
        self.completed_at = None
        self.output = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "inputs": self.inputs,
            "status": self.status,
            "skyvern_task_id": self.skyvern_task_id,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output": self.output
        }


class FlowExecution:
    """Tracks the execution of a flow."""

    def __init__(self, flow_id: str, initial_inputs: Dict):
        self.id = str(uuid.uuid4())
        self.flow_id = flow_id
        self.initial_inputs = initial_inputs
        self.action_executions: List[ActionExecution] = []
        self.status = ActionExecutionStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.outputs = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "flow_id": self.flow_id,
            "initial_inputs": self.initial_inputs,
            "action_executions": [ae.to_dict() for ae in self.action_executions],
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outputs": self.outputs
        }


class WebsiteFlowManager:
    def __init__(self, db: MarqoDatabase, block_manager: WebsiteBlockManager, skyvern: SkyvernService, llm: LLMService):
        self.db = db
        self.block_manager = block_manager
        self.skyvern = skyvern
        self.llm = llm
        
    async def continue_flow_execution(self, flow_id: str, additional_inputs: Dict) -> FlowExecution:
        # Get flow from Marqo
        flow_result = self.db.client.index(self.db.flows_index).get_document(flow_id)
        if not flow_result:
            raise ValueError(f"Flow {flow_id} not found")
            
        # Update document in Marqo
        self.db.client.index(self.db.flows_index).update_documents([{
            "_id": flow_id,
            "status": ActionExecutionStatus.RUNNING
        }])
        
        # Continue flow execution with new inputs
        return await self.execute_flow(flow_id, additional_inputs)

    async def execute_flow(self, flow_id: str, initial_inputs: Dict) -> FlowExecution:
        flow_execution = FlowExecution(flow_id, initial_inputs or {})
        flow_execution.started_at = datetime.now().isoformat()
        flow_execution.status = ActionExecutionStatus.RUNNING
        flow_execution.outputs = {}

        # Get flow details
        flow_result = self.db.client.index(self.db.flows_index).get_document(flow_id)
        flow_actions = json.loads(flow_result["actions"])
        
        current_inputs = initial_inputs or {}
        accumulated_outputs = {}

        for action_config in flow_actions:
            action = await self.block_manager.get_action(action_config["id"])
            
            task_inputs = dict(current_inputs)
            if accumulated_outputs:
                task_inputs.update(accumulated_outputs)
            
            task = await self.skyvern.create_task(
                url=action["url"],
                navigation_goal=action["navigation_goal"],
                data_extraction_goal=action["data_extraction_goal"],
                navigation_payload=task_inputs
            )

            # Create action execution record
            action_execution = ActionExecution(action_config["id"], task_inputs)
            action_execution.started_at = datetime.now().isoformat()
            action_execution.status = ActionExecutionStatus.RUNNING
            action_execution.skyvern_task_id = task["task_id"]
            
            # Wait for task completion
            task_result = await self.skyvern.wait_for_completion(task["task_id"])
            
            # Update action execution with results
            action_execution.completed_at = datetime.now().isoformat()
            action_execution.status = ActionExecutionStatus.COMPLETED
            
            # Safely extract output
            output = task_result.get("extracted_information", {}) if task_result else {}
            action_execution.output = output
            flow_execution.outputs[action_execution.id] = output
            
            # Safely accumulate outputs
            # if output:
            #     accumulated_outputs.update(output)
            
            flow_execution.action_executions.append(action_execution)
            await self.db.store_execution(flow_execution.to_dict())

        flow_execution.completed_at = datetime.now().isoformat()
        flow_execution.status = ActionExecutionStatus.COMPLETED
        await self.db.store_execution(flow_execution.to_dict())

        return flow_execution


    async def create_flow_from_prompt(self, prompt: str, initial_inputs: Dict = None) -> Dict:
        analysis_prompt = f"""
            Given this user request: {prompt}
            Determine the sequence of actions needed to accomplish this task.
            For each action, specify:
            1. Website URL
            2. Action name
            3. Navigation goal
            4. Data extraction goal
            5. Required inputs
            For navigation goals, don't click buttons like "Find Me" to find location
            and other similar actions which will lead nowhere. For example, instead of find me
            just use already provided address. Close popups which are not required 
            but try to stick close to our main goal.
            
            Just give me the JSON output, no other text
            Return as JSON with this structure:
            {{
                "flow_name": "name",
                "flow_description": "description",
                "actions": [
                    {{
                        "url": "website_url",
                        "name": "action_name",
                        "navigation_goal": "goal",
                        "data_extraction_goal": "goal",
                        "required_inputs": ["input1", "input2"]
                    }}
                ]
            }}
            """

        response = self.llm.client.messages.create(
            max_tokens=4096,
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        flow_plan = json.loads(response.content[0].text)

        action_configs = []
        found_actions = []

        for action_plan in flow_plan["actions"]:
            blocks_search = await self.db.search_blocks(action_plan["url"])

            if blocks_search and len(blocks_search) > 0:
                search_query = f"{action_plan['name']} {action_plan['navigation_goal']} {action_plan['data_extraction_goal']}"
                existing_actions = await self.db.search_actions(search_query)

                if existing_actions and len(existing_actions) > 0:
                    best_match = existing_actions[0]
                    action_configs.append({"id": best_match["_id"]})
                    found_actions.append(best_match)
                    continue
            else:
                block = await self.block_manager.create_block(
                    name=f"Block for {action_plan['name']}",
                    url=action_plan["url"],
                    acts=''
                )
                action = await self.block_manager.get_action(block["actions"][0])
                action_configs.append({"id": block["actions"][0]})
                found_actions.append(action)

        # Validate if found actions are sufficient
        validation_prompt = f"""
        Given this user request: {prompt}
        And these existing actions we found:
        {json.dumps(found_actions, indent=2)}
        
        Evaluate if these actions are truly relevant and sufficient for the request.
        RETURN ONLY THE JSON OUTPUT, NO OTHER TEXT.
        Return JSON in this format:
        {{
            "is_sufficient": boolean,
            "missing_capabilities": [
                {{
                    "url": "website_url",
                    "name": "action_name",
                    "navigation_goal": "goal",
                    "data_extraction_goal": "goal",
                    "required_inputs": ["input1", "input2"]
                }}
            ]
        }}
        """

        validation_response = self.llm.client.messages.create(
            max_tokens=4096,
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": validation_prompt}]
        )
        validation_result = json.loads(validation_response.content[0].text)

        if not validation_result["is_sufficient"]:
            for new_action in validation_result["missing_capabilities"]:
                blocks_search = await self.db.search_blocks(new_action["url"])
                
                if blocks_search and len(blocks_search) > 0:
                    block_id = blocks_search[0]["_id"]
                    action_data = {
                        "block_id": block_id,
                        "name": new_action["name"],
                        "navigation_goal": new_action["navigation_goal"],
                        "data_extraction_goal": new_action["data_extraction_goal"],
                        "required_inputs": new_action["required_inputs"],
                        "output_schema": {},
                        "url": new_action["url"]
                    }
                    action_id = await self.db.store_action(action_data)
                    action_configs.append({"id": action_id})
                    action = await self.block_manager.get_action(action_id)
                    found_actions.append(action)
                else:
                    block = await self.block_manager.create_block(
                        name=f"Block for {new_action['name']}",
                        url=new_action["url"],
                        acts=json.dumps([new_action])
                    )
                    action = await self.block_manager.get_action(block["actions"][0])
                    action_configs.append({"id": block["actions"][0]})
                    found_actions.append(action)

        optimization_prompt = f"""
        Given this user request: {prompt}
        And these available actions:
        {json.dumps(found_actions, indent=2)}
        
        Determine the optimal sequence of actions to achieve the goal.
        Only include the actions that are really reqquired for the request.
        Consider:
        1. Dependencies between actions
        2. Data flow between actions
        3. Logical order of operations
        
        Return only a JSON array of action IDs in the optimal order:
        DO NOT REUTNRN ANY OTHER TEXT.
        ["action_id1", "action_id2", ...]
        """

        optimization_response = self.llm.client.messages.create(
            max_tokens=4096,
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": optimization_prompt}]
        )

        optimized_action_ids = json.loads(optimization_response.content[0].text)
        final_action_configs = [{"id": action_id} for action_id in optimized_action_ids]
        final_action_configs = list({v['id']: v for v in final_action_configs}.values())

        flow = await self.create_flow(
            name=flow_plan["flow_name"],
            description=flow_plan["flow_description"],
            action_configs=final_action_configs
        )

        missing_inputs = await self.check_missing_inputs(flow["id"], initial_inputs or {})
        if missing_inputs:
            input_extraction_prompt = f"""
            From this user request: {prompt}
            I need to find values for these inputs: {missing_inputs}
            
            If you can find any values in the request for these inputs, return them as JSON.
            Don't include any other extra text, just return the JSON.
            
            Format:
            {{"input_name": "extracted_value"}}
            
            If no values can be found, return empty object {{}}
            """
            
            extraction_response = self.llm.client.messages.create(
                max_tokens=1000,
                model="claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": input_extraction_prompt}]
            )
            
            extracted_inputs = json.loads(extraction_response.content[0].text)
            
            if initial_inputs is None:
                initial_inputs = {}
            initial_inputs.update(extracted_inputs)
            
            missing_inputs = await self.check_missing_inputs(flow["id"], initial_inputs)
            if missing_inputs:
                raise ValueError(f"Missing required inputs: {missing_inputs}")

        return flow


    async def create_flow(self, name: str, description: str, action_configs: List[Dict]) -> Dict:
        """Create a new flow with specified actions."""
        flow_data = {
            "name": name,
            "description": description,
            "actions": action_configs
        }

        flow_id = await self.db.store_flow(flow_data)

        return {
            "id": flow_id,
            "name": name,
            "description": description,
            "actions": action_configs
        }

    async def check_missing_inputs(self, flow_id: str, provided_inputs: Dict) -> List[str]:
        flow_result = self.db.client.index(
            self.db.flows_index).get_document(flow_id)
        actions = json.loads(flow_result["actions"])

        missing_inputs = set()
        for action_config in actions:
            action = await self.block_manager.get_action(action_config["id"])
            required_inputs = set(action["required_inputs"])
            missing = required_inputs - set(provided_inputs.keys())
            missing_inputs.update(missing)

        return list(missing_inputs)
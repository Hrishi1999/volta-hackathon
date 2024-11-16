import json
import os
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from core import (LLMService, MarqoDatabase, ReactWriter, SkyvernService,
                  WebsiteBlockManager, WebsiteFlowManager)

app = FastAPI()

# Initialize services with SQLite
db = MarqoDatabase(url='http://localhost:8882')
llm = LLMService(api_key=os.getenv("ANTHROPIC_API_KEY"))
skyvern = SkyvernService(api_key=os.getenv("SKYVERN_API_KEY"))
block_manager = WebsiteBlockManager(db, llm)
flow_manager = WebsiteFlowManager(db, block_manager, skyvern, llm)
react_writer = ReactWriter(llm)

# Request/Response Models
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins during development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"]   # Allows all headers
)


class BlockCreate(BaseModel):
    name: str
    url: str
    actions: str


class FlowCreate(BaseModel):
    name: str
    description: str
    action_configs: List[Dict]


class FlowExecute(BaseModel):
    initial_inputs: Dict


class FlowPrompt(BaseModel):
    prompt: str
    initial_inputs: Dict | None = None

# Block endpoints


@app.post("/blocks/")
async def create_block(block_data: BlockCreate):
    block = await block_manager.create_block(
        name=block_data.name,
        url=block_data.url,
        acts=block_data.actions
    )
    return block


@app.get("/blocks/{block_id}")
def get_block(block_id: str):
    result = db.client.index(db.blocks_index).get_document(block_id)
    if not result:
        raise HTTPException(status_code=404, detail="Block not found")
    return result


@app.get("/blocks/")
def list_blocks():
    results = db.client.index(db.blocks_index).search(
        q="*",
        limit=100
    )
    return [hit for hit in results["hits"]]

# Action endpoints


@app.get("/actions/{action_id}")
def get_action(action_id: str):
    result = db.client.index(db.actions_index).get_document(action_id)
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return result

# get actions by block id


@app.get("/actions/")
def list_actions():
    results = db.client.index(db.actions_index).search(
        q="*",
        limit=100
    )
    return [hit for hit in results["hits"]]

# Flow endpoints


@app.post("/flows/")
def create_flow(flow_data: FlowCreate):
    flow = flow_manager.create_flow(
        name=flow_data.name,
        description=flow_data.description,
        action_configs=flow_data.action_configs
    )
    return flow


@app.get("/flows/{flow_id}")
def get_flow(flow_id: str):
    result = db.client.index(db.flows_index).get_document(flow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    result["actions"] = json.loads(result["actions"])
    return result


@app.get("/flows/")
def list_flows():
    results = db.client.index(db.flows_index).search(
        q="*",
        limit=100
    )
    return [{**hit, "actions": json.loads(hit["actions"])} for hit in results["hits"]]


@app.post("/flows/{flow_id}/execute")
async def execute_flow(flow_id: str, execution_data: FlowExecute):
    try:
        flow_execution = await flow_manager.execute_flow(
            flow_id=flow_id,
            initial_inputs=execution_data.initial_inputs
        )
        return flow_execution.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/executions/{execution_id}")
def get_execution(execution_id: str):
    result = db.client.index(db.executions_index).get_document(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    result["initial_inputs"] = json.loads(result["initial_inputs"])
    result["action_executions"] = json.loads(result["action_executions"])
    return result


@app.get("/executions/")
def list_executions():
    results = db.client.index(db.executions_index).search(
        q="*",
        limit=100
    )
    return [{
        **hit,
        "initial_inputs": json.loads(hit["initial_inputs"]),
        "action_executions": json.loads(hit["action_executions"])
    } for hit in results["hits"]]


@app.post("/flows/from-prompt")
async def create_flow_from_prompt(flow_data: FlowPrompt):
    flow = await flow_manager.create_flow_from_prompt(
        prompt=flow_data.prompt,
        initial_inputs=flow_data.initial_inputs
    )
    return flow


@app.post("/flows/new/from-prompt/execute")
async def create_and_execute_flow_from_prompt(flow_data: FlowPrompt):
    flow = await flow_manager.create_flow_from_prompt(
        prompt=flow_data.prompt,
        initial_inputs=flow_data.initial_inputs
    )
    flow_execution = await flow_manager.execute_flow(
        flow_id=flow["id"],
        initial_inputs=flow_data.initial_inputs
    )
    
    # Combine execution outputs with original prompt for React code generation
    execution_dict = flow_execution.to_dict()
    action_outputs = {}
    
    for action_execution in execution_dict["action_executions"]:
        if "outputs" in action_execution:
            action_outputs.update(action_execution["outputs"])
    
    await react_writer.write_app_jsx(
        prompt=flow_data.prompt,
        unstructured_data=action_outputs
    )
    
    return flow_execution.to_dict()


@app.get("/flows/pending")
async def get_pending_flows():
    # Query Marqo for pending flows
    results = db.client.index(db.flows_index).search(
        q="pending_input",
        filter_expression="status = 'pending_input'"
    )

    if results["hits"]:
        pending_flow = results["hits"][0]
        return {
            "flowId": pending_flow["_id"],
            "missingInputs": json.loads(pending_flow["missing_inputs"])
        }
    return {}


@app.post("/flows/{flow_id}/continue")
async def continue_flow(flow_id: str, inputs: Dict):
    flow_execution = await flow_manager.continue_flow_execution(
        flow_id=flow_id,
        additional_inputs=inputs
    )
    return flow_execution.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

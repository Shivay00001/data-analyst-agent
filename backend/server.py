import os
import sys
import asyncio
import uuid
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Form, Request, Response, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from dotenv import load_dotenv
import litellm
from pydantic import BaseModel
from typing import Optional

from database import engine, Base, SessionLocal, get_db
from models import Dataset, ExecutionLog

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    os.makedirs("workspace", exist_ok=True)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("workspace", exist_ok=True)
app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")

def get_api_key(model_id: str, api_keys: dict):
    if model_id.startswith("gpt"):
        return api_keys.get("openai") or os.getenv("OPENAI_API_KEY")
    elif model_id.startswith("claude"):
        return api_keys.get("anthropic") or os.getenv("ANTHROPIC_API_KEY")
    elif model_id.startswith("gemini"):
        return api_keys.get("gemini") or os.getenv("GEMINI_API_KEY")
    elif model_id.startswith("zhipu"):
        return api_keys.get("glm") or os.getenv("ZHIPUAI_API_KEY")
    return None

async def execute_python_isolated(task_id: str, code: str) -> str:
    """Executes Python code safely in a subprocess with a strict timeout and isolated folder."""
    task_dir = os.path.join("workspace", task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    script_path = os.path.join(task_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)
        
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=task_dir
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        
        output = stdout.decode('utf-8')
        if stderr:
            output += f"\n[STDERR]\n{stderr.decode('utf-8')}"
        return output
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except:
            pass
        return "Execution Error: Process timed out after 60 seconds."
    except Exception as e:
        return f"Execution Error: {e}"

async def process_bi_job(task_id: str, prompt: str, provider: str, dataset_filepath: str, api_keys: dict):
    async with SessionLocal() as db:
        try:
            result = await db.execute(select(ExecutionLog).where(ExecutionLog.task_id == task_id))
            log = result.scalar_one()
            log.status = "running"
            await db.commit()
            
            api_key = get_api_key(provider, api_keys)
            api_base = "http://localhost:11434" if provider.startswith("ollama") else None
            
            abs_dataset_path = os.path.abspath(dataset_filepath)
            
            system_prompt = (
                "You are an autonomous Business Intelligence Data Analyst AI. "
                "You write Python code to analyze datasets, perform SQL-like operations, generate pivot tables, "
                "and build descriptive visualizations (bar charts, line graphs, heatmaps). "
                "DO NOT attempt to build predictive Machine Learning models (no scikit-learn). "
                "Output ONLY valid Python code enclosed in ```python ... ``` blocks. "
                "The dataset is located at the absolute path provided by the user. "
                "CRITICAL INSTRUCTIONS FOR PRODUCTION AUTOMATION: "
                "1. DATA CLEANING: You MUST check for and handle missing values (NaN/null) before applying any formulas to prevent crashes. "
                "2. FORMULA AUDITABILITY: Whenever you calculate a metric (e.g., standard deviation, variance, CAGR, moving average), you MUST explicitly print the exact mathematical formula or statistical logic you applied to stdout before printing the result. "
                "3. ENTERPRISE VISUALIZATIONS: Use `plt.savefig('your_plot_name.png', dpi=300, bbox_inches='tight')`. Do NOT use `plt.show()`. Wrap plotting logic in try/except blocks. "
                "After saving, you MUST print the exact filename of the saved image (e.g. `print('your_plot_name.png')`) so it can be captured."
            )
            
            user_prompt = f"Absolute Dataset path: {abs_dataset_path}\nTask: {prompt}"
            
            response = await litellm.acompletion(
                model=provider,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                api_key=api_key,
                api_base=api_base,
                temperature=0.1
            )
            ai_message = response.choices[0].message.content
            
            code = ai_message
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
                
            log.generated_code = code
            await db.commit()
            
            safe_code = (
                "import pandas as pd\n"
                "import numpy as np\n"
                "import matplotlib.pyplot as plt\n"
                "import seaborn as sns\n"
                "# INJECTED: Enterprise Production Styling\n"
                "sns.set_theme(style='whitegrid', palette='deep')\n"
            ) + code
            execution_output = await execute_python_isolated(task_id, safe_code)
            
            images = []
            for line in execution_output.split('\n'):
                line = line.strip()
                if line.endswith('.png'):
                    images.append(f"http://localhost:8000/workspace/{task_id}/{line}")
            
            log.execution_output = execution_output
            log.images_csv = ",".join(images)
            log.status = "completed"
            await db.commit()

        except Exception as e:
            result = await db.execute(select(ExecutionLog).where(ExecutionLog.task_id == task_id))
            log = result.scalar_one_or_none()
            if log:
                log.status = "failed"
                log.execution_output = str(e)
                await db.commit()

@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    file_id = str(uuid.uuid4())
    filepath = f"workspace/{file_id}_{file.filename}"
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
        
    dataset = Dataset(filename=file.filename, filepath=filepath)
    db.add(dataset)
    await db.commit()
    
    return {"status": "success", "filename": file.filename, "filepath": filepath}

class ExecuteRequest(BaseModel):
    prompt: str
    provider: str 
    dataset_filepath: str

@app.post("/api/execute")
async def enqueue_bi_task(req: ExecuteRequest, background_tasks: BackgroundTasks, request: Request, db: AsyncSession = Depends(get_db)):
    task_id = str(uuid.uuid4())
    
    log = ExecutionLog(
        task_id=task_id,
        prompt=req.prompt,
        model_provider=req.provider,
        status="pending"
    )
    db.add(log)
    await db.commit()
    
    api_keys = {
        "openai": request.headers.get("X-OpenAI-Key"),
        "anthropic": request.headers.get("X-Anthropic-Key"),
        "gemini": request.headers.get("X-Gemini-Key"),
        "glm": request.headers.get("X-GLM-Key")
    }
    
    background_tasks.add_task(process_bi_job, task_id, req.prompt, req.provider, req.dataset_filepath, api_keys)
    
    return {"status": "success", "task_id": task_id}

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExecutionLog).where(ExecutionLog.task_id == task_id))
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Task not found")
        
    images = log.images_csv.split(",") if log.images_csv else []
        
    return {
        "task_id": log.task_id,
        "status": log.status,
        "generated_code": log.generated_code,
        "execution_output": log.execution_output,
        "images": images
    }

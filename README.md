# AI Data Analyst Agent

An intelligent agent designed to autonomously analyze data, generate visualizations, and connect to structured DBs.

## Overview
This repository contains a full-stack implementation of the **AI Data Analyst Agent**. 
- **Backend:** FastAPI (Python), LiteLLM (Multi-LLM Support: OpenAI, Anthropic, Gemini, GLM)
- **Frontend:** Next.js (React, Tailwind CSS)
- **Database:** SQLite / PostgreSQL

## Getting Started

### 1. Backend Setup
\\\ash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --port 8000
\\\

### 2. Frontend Setup
\\\ash
cd frontend
npm install
npm run dev
\\\

## Coordination & Automation
This agent is part of a larger ecosystem. It can be executed natively via its UI, or coordinated as a node in a multi-agent pipeline using the Central Connector System.

## Run it as a managed service

Prefer not to self-host? [VisionQuantech](https://visionquantech.com) deploys AI data analysts like this one as a managed service — see [AI Data Analysis Services](https://visionquantech.com/service-data-analysis) and the [AI Data Analyst employee](https://visionquantech.com/employee-data-analyst) page.

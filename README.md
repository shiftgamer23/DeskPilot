---
title: Ticket Triage Agent
emoji: 🎫
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

FastAPI backend for the Ticket Triage Agent - an agentic ticket-routing system (LangGraph tool-use loop,
Groq/Gemini, hybrid BM25 + vector retrieval, and a deterministic confidence gate). This Space serves the
API only; the frontend is deployed separately on Vercel. See `DEPLOY.md` in the repo for the full
deployment writeup.

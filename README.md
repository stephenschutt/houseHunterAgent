---
title: House Hunter Agent
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
---

# House Hunter Agent

A smolagents `CodeAgent` that answers questions about Zillow for-sale listings saved as
HTML in `agent/files/`.

Set the `ANTHROPIC_API_KEY` secret (and optionally `MODEL_ID`) in the Space settings.

Run locally:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python app.py                                   # Gradio UI
python agent/agent.py "Which homes are under $500k?"   # CLI
```

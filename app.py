"""Hugging Face Space entry point: serves the house hunter agent in a Gradio chat UI."""

from smolagents import CodeAgent, GradioUI, LiteLLMModel

from agent.agent import MODEL_ID, read_listings

agent = CodeAgent(
    tools=[read_listings],
    model=LiteLLMModel(model_id=MODEL_ID),
    additional_authorized_imports=["json", "re", "statistics"],
)

GradioUI(agent).launch()

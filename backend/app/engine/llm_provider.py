import json
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import settings
from app.models.schemas import AgentStep

class BaseLLMProvider(ABC):
    """Abstract Base Class for Provider-Agnostic LLM Interfaces."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def run_investigation_loop(
        self,
        incident_id: str,
        system_prompt: str,
        tools_schema: List[Dict[str, Any]],
        tool_executor_fn: Any
    ) -> Tuple[Optional[Dict[str, Any]], List[AgentStep]]:
        """Executes multi-turn tool-calling loop and returns (parsed_json_report, steps_taken)."""
        pass


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider supporting configurable model names."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.api_key = api_key
        self._model = model_name or "claude-3-5-sonnet-20241022"
        import anthropic
        self.client = anthropic.Anthropic(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def run_investigation_loop(
        self,
        incident_id: str,
        system_prompt: str,
        tools_schema: List[Dict[str, Any]],
        tool_executor_fn: Any
    ) -> Tuple[Optional[Dict[str, Any]], List[AgentStep]]:
        steps: List[AgentStep] = []
        messages = [
            {"role": "user", "content": f"Investigate financial incident with ID: {incident_id}"}
        ]

        # Convert tool schemas to Anthropic format
        anthropic_tools = []
        for t in tools_schema:
            anthropic_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("parameters", t.get("input_schema", {}))
            })

        for turn in range(8):
            response = self.client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=anthropic_tools
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        output = tool_executor_fn(tool_name, tool_input)

                        steps.append(AgentStep(
                            step_number=len(steps) + 1,
                            title=f"LLM Tool Call: {tool_name}",
                            description=f"Executed tool {tool_name} with params: {json.dumps(tool_input)}",
                            tool_name=tool_name,
                            tool_input=tool_input,
                            tool_output=output,
                            timestamp=""
                        ))

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(output)
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                text = "".join([b.text for b in response.content if hasattr(b, "text")])
                s = text.find("{")
                e = text.rfind("}") + 1
                if s != -1 and e != 0:
                    parsed = json.loads(text[s:e])
                    return parsed, steps
                break
        return None, steps


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI-Compatible Provider supporting local models (Ollama, LMStudio, LocalAI, vLLM)
    or OpenAI endpoints.
    """

    def __init__(self, base_url: str, api_key: str = "", model_name: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "local_key"
        self._model = model_name or "llama3.1"

    @property
    def provider_name(self) -> str:
        return "Local/OpenAI-Compatible"

    @property
    def model_name(self) -> str:
        return self._model

    def run_investigation_loop(
        self,
        incident_id: str,
        system_prompt: str,
        tools_schema: List[Dict[str, Any]],
        tool_executor_fn: Any
    ) -> Tuple[Optional[Dict[str, Any]], List[AgentStep]]:
        steps: List[AgentStep] = []
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Investigate financial incident with ID: {incident_id}"}
        ]

        # Convert tool schemas to standard OpenAI format
        openai_tools = []
        for t in tools_schema:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", t.get("input_schema", {}))
                }
            })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                for turn in range(8):
                    body = {
                        "model": self._model,
                        "messages": messages,
                        "tools": openai_tools,
                        "temperature": 0.1
                    }
                    res = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                    if res.status_code != 200:
                        break

                    data = res.json()
                    choice = data["choices"][0]["message"]

                    if choice.get("tool_calls"):
                        messages.append(choice)
                        for tc in choice["tool_calls"]:
                            fn_name = tc["function"]["name"]
                            fn_args = json.loads(tc["function"].get("arguments", "{}"))

                            out = tool_executor_fn(fn_name, fn_args)

                            steps.append(AgentStep(
                                step_number=len(steps) + 1,
                                title=f"Local LLM Tool Call: {fn_name}",
                                description=f"Executed tool {fn_name} with params: {json.dumps(fn_args)}",
                                tool_name=fn_name,
                                tool_input=fn_args,
                                tool_output=out,
                                timestamp=""
                            ))

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(out)
                            })
                    else:
                        text = choice.get("content", "")
                        s = text.find("{")
                        e = text.rfind("}") + 1
                        if s != -1 and e != 0:
                            parsed = json.loads(text[s:e])
                            return parsed, steps
                        break
        except Exception as e:
            print(f"Local LLM execution notice: {e}")
        return None, steps


def get_llm_provider() -> Optional[BaseLLMProvider]:
    """Factory function resolving configured LLM provider or returning None for deterministic fallback."""
    provider_pref = settings.LLM_PROVIDER.lower()

    if provider_pref == "deterministic":
        return None

    # Check Anthropic
    if provider_pref == "anthropic" or (provider_pref == "auto" and settings.ANTHROPIC_API_KEY):
        try:
            return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model_name=settings.LLM_MODEL or None)
        except Exception as e:
            print(f"Anthropic provider init failed: {e}")

    # Check Local / OpenAI-Compatible
    if provider_pref in ["openai_compatible", "local"] or (provider_pref == "auto" and (settings.OPENAI_API_KEY or settings.LLM_API_KEY)):
        key = settings.OPENAI_API_KEY or settings.LLM_API_KEY or "local"
        base_url = settings.LLM_BASE_URL if provider_pref == "local" else (settings.LLM_BASE_URL or "https://api.openai.com/v1")
        return OpenAICompatibleProvider(base_url=base_url, api_key=key, model_name=settings.LLM_MODEL or None)

    return None

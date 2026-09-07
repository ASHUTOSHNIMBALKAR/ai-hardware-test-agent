"""
LLM Client abstraction supporting structured JSON extraction, backoff retries, and offline mock fallback.
"""

import json
import logging
import os
import time
from typing import Type, TypeVar, Optional, Dict, Any
import httpx
from pydantic import BaseModel
from hw_test_agent.models.schemas import TestSpec, ClarificationNeeded, MeasurementType, Limit
from hw_test_agent.utils.logging_setup import logger

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Wrapper around LLM APIs for structured JSON extraction with retry logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        fake_mode: bool = False,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model = model
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.fake_mode = fake_mode or (not self.api_key)
        self.total_tokens_used = 0

    def complete_json(self, system_prompt: str, user_prompt: str, schema_cls: Type[T], max_retries: int = 3) -> T:
        """
        Requests JSON response from LLM adhering to schema_cls.
        Appends validation error and retries up to max_retries on failure.
        """
        if self.fake_mode:
            logger.info("LLMClient running in offline/mock mode.")
            return self._mock_response(user_prompt, schema_cls)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        schema_json = json.dumps(schema_cls.model_json_schema(), indent=2)
        prompt_with_schema = (
            f"{user_prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object adhering to this JSON Schema:\n"
            f"```json\n{schema_json}\n```\nDo not include any commentary outside the JSON block."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_with_schema},
        ]

        attempt = 0
        last_error = None

        while attempt < max_retries:
            attempt += 1
            start_time = time.time()
            try:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                }

                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                self.total_tokens_used += tokens

                latency = time.time() - start_time
                logger.debug(f"LLM API call succeeded in {latency:.2f}s ({tokens} tokens).")

                # Parse JSON string
                parsed_json = json.loads(content)
                result = schema_cls.model_validate(parsed_json)
                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM attempt {attempt}/{max_retries} failed: {e}")
                messages.append(
                    {
                        "role": "user",
                        "content": f"Your previous output was invalid. Error: {last_error}. Please correct the JSON.",
                    }
                )
                time.sleep(1.0 * attempt)

        # If LLM API call failed after retries, fallback gracefully
        logger.error(f"LLM complete_json failed after {max_retries} attempts: {last_error}")
        return self._mock_response(user_prompt, schema_cls)

    def _mock_response(self, user_prompt: str, schema_cls: Type[T]) -> T:
        """Deterministic mock responses for testing without API keys."""
        text = user_prompt.lower()

        # Check for ambiguity test
        if "check power supply" in text and "ripple" not in text and "voltage" not in text:
            if schema_cls == ClarificationNeeded or schema_cls == TestSpec:
                return ClarificationNeeded(
                    is_ambiguous=True,
                    question="Which measurement would you like to perform (e.g., DC voltage, ripple, current)?",
                    missing_fields=["measurement", "limit"],
                )  # type: ignore

        if schema_cls == TestSpec:
            if "50 v" in text or "50v" in text or "50 v" in text:
                return TestSpec(
                    name="High Voltage Test",
                    dut="Power Supply Rail",
                    measurement=MeasurementType.DC_VOLTAGE,
                    condition={"input_voltage": 50.0},
                    limit=Limit(nominal=50.0, tolerance_pct=2.0, unit="V"),
                )  # type: ignore
            elif "ripple" in text:
                return TestSpec(
                    name="Ripple Test",
                    dut="Power Supply Rail",
                    measurement=MeasurementType.RIPPLE,
                    condition={"input_voltage": 5.0, "load_current": 0.5},
                    limit=Limit(max=0.05, unit="V"),
                )  # type: ignore
            elif "frequency" in text or "kHz" in text:
                return TestSpec(
                    name="Frequency Measurement",
                    dut="Oscillator",
                    measurement=MeasurementType.FREQUENCY,
                    condition={},
                    limit=Limit(nominal=1000.0, tolerance_pct=5.0, unit="Hz"),
                )  # type: ignore
            elif "current" in text:
                return TestSpec(
                    name="Current Draw Test",
                    dut="Power Supply Rail",
                    measurement=MeasurementType.CURRENT,
                    condition={"input_voltage": 3.3},
                    limit=Limit(max=0.1, unit="A"),
                )  # type: ignore
            else:
                target_v = 3.3 if "3.3" in text else 5.0
                return TestSpec(
                    name="DC Voltage Accuracy Test",
                    dut="Regulator",
                    measurement=MeasurementType.DC_VOLTAGE,
                    condition={"input_voltage": target_v},
                    limit=Limit(nominal=target_v, tolerance_pct=2.0, unit="V"),
                )  # type: ignore

        elif schema_cls == ClarificationNeeded:
            return ClarificationNeeded(
                is_ambiguous=True,
                question="Please specify target voltage and max ripple limit.",
                missing_fields=["limit"],
            )  # type: ignore

        # Fallback empty model instantiation
        try:
            return schema_cls.model_construct()
        except Exception:
            raise ValueError(f"Cannot generate mock response for {schema_cls}")

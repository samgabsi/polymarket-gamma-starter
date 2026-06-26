from __future__ import annotations

import json
from typing import Any

from .config import APP_VERSION
from .platform_safety import safety_flags

MODEL_FIT_SAFETY_STATEMENT = (
    "Local model recommendations are operational fit guidance only. They are not financial advice, "
    "not trading recommendations, and do not place orders, cancel orders, approve trades, arm live trading, "
    "or disable safety gates."
)

RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "model": "qwen3:8b",
        "provider_runtime": "ollama_openai_compatible",
        "memory_tier": "16gb_apple_silicon",
        "recommended_hardware": ["Mac mini M4 16GB", "Apple Silicon 16GB", "Apple Silicon 24GB+"],
        "intended_use_case": "Default local copilot for summaries, triage, validation explanations, and task-draft reviews.",
        "expected_speed_tier": "medium",
        "quality_tier": "best_default_for_16gb",
        "context_caution": "Keep prompts compact; prefer redacted summaries and staged review packets over raw runtime dumps.",
        "recommended_max_input_chars": 8000,
        "recommended_default_for_mac_mini_m4_16gb": True,
        "recommended_for_16gb_default": True,
        "experimental_for_16gb": False,
        "install_command": "ollama pull qwen3:8b",
        "safety_notes": ["Use through localhost-only Ollama endpoint.", "Keep redaction enabled before every prompt."],
    },
    {
        "model": "qwen3:4b",
        "provider_runtime": "ollama_openai_compatible",
        "memory_tier": "8gb_to_16gb",
        "recommended_hardware": ["Mac mini M4 16GB", "Apple Silicon 8GB+"],
        "intended_use_case": "Faster local fallback for classifications, labels, short summaries, and validation explanations.",
        "expected_speed_tier": "fast",
        "quality_tier": "good_fast_fallback",
        "context_caution": "Use smaller context windows and ask for concise outputs.",
        "recommended_max_input_chars": 6000,
        "recommended_default_for_mac_mini_m4_16gb": False,
        "recommended_for_16gb_default": True,
        "experimental_for_16gb": False,
        "install_command": "ollama pull qwen3:4b",
        "safety_notes": ["Good for dry-run parity tests and quick operator explanations."],
    },
    {
        "model": "gemma3:4b",
        "provider_runtime": "ollama_openai_compatible",
        "memory_tier": "8gb_to_16gb",
        "recommended_hardware": ["Mac mini M4 16GB", "Apple Silicon 8GB+"],
        "intended_use_case": "Privacy-first local summarization and drafting.",
        "expected_speed_tier": "fast",
        "quality_tier": "good_private_drafting",
        "context_caution": "Best for short review drafts rather than large multi-module synthesis.",
        "recommended_max_input_chars": 6000,
        "recommended_default_for_mac_mini_m4_16gb": False,
        "recommended_for_16gb_default": True,
        "experimental_for_16gb": False,
        "install_command": "ollama pull gemma3:4b",
        "safety_notes": ["Still governed by redaction, prompt governance, audit hashes, and human review."],
    },
    {
        "model": "gemma3:12b",
        "provider_runtime": "ollama_openai_compatible",
        "memory_tier": "16gb_tight_or_24gb_plus",
        "recommended_hardware": ["Apple Silicon 24GB+ preferred", "Mac mini M4 16GB experimental"],
        "intended_use_case": "Higher-quality local review mode when memory and latency are acceptable.",
        "expected_speed_tier": "slower",
        "quality_tier": "higher_quality_experimental_on_16gb",
        "context_caution": "May be tight on 16GB; reduce max input chars and avoid background load.",
        "recommended_max_input_chars": 5000,
        "recommended_default_for_mac_mini_m4_16gb": False,
        "recommended_for_16gb_default": False,
        "experimental_for_16gb": True,
        "install_command": "ollama pull gemma3:12b",
        "safety_notes": ["Use only after testing local performance; keep dry-run validation available."],
    },
    {
        "model": "27b_30b_32b_local_models",
        "provider_runtime": "ollama_or_local_openai_compatible",
        "memory_tier": "24gb_plus_or_32gb_plus",
        "recommended_hardware": ["Apple Silicon 32GB+", "high-memory local workstation"],
        "intended_use_case": "Experimental large local model trials only; not a default for 16GB systems.",
        "expected_speed_tier": "slow_or_unavailable_on_16gb",
        "quality_tier": "potentially_higher_but_memory_limited",
        "context_caution": "Not recommended as a Mac mini M4 16GB default due to memory pressure and latency.",
        "recommended_max_input_chars": 3000,
        "recommended_default_for_mac_mini_m4_16gb": False,
        "recommended_for_16gb_default": False,
        "experimental_for_16gb": True,
        "install_command": "not recommended by default on 16GB",
        "safety_notes": ["Treat as experimental; never let model size alter live-trading safety gates."],
    },
]

HARDWARE_PROFILES = [
    {
        "profile_id": "mac_mini_m4_16gb",
        "title": "Mac mini M4 16GB",
        "recommended_default_model": "qwen3:8b",
        "fast_fallback_models": ["qwen3:4b", "gemma3:4b"],
        "experimental_quality_model": "gemma3:12b",
        "not_recommended_default": ["27B", "30B", "32B+"],
        "notes": [
            "Prefer Ollama OpenAI-compatible localhost endpoint at http://127.0.0.1:11434/v1.",
            "Keep LOCAL_LLM_MAX_INPUT_CHARS conservative to avoid memory pressure.",
            "Use mock/dry-run provider for package validation and no-network tests.",
        ],
    },
    {
        "profile_id": "apple_silicon_16gb",
        "title": "Apple Silicon 16GB",
        "recommended_default_model": "qwen3:8b",
        "fast_fallback_models": ["qwen3:4b", "gemma3:4b"],
        "experimental_quality_model": "gemma3:12b",
        "not_recommended_default": ["27B", "30B", "32B+"],
        "notes": ["Same guidance as Mac mini M4 16GB unless local memory pressure is high."],
    },
]


def list_model_recommendations() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "title": "Local LLM model-fit recommendations",
        "recommended_default_for_mac_mini_m4_16gb": "qwen3:8b",
        "items": RECOMMENDATIONS,
        "count": len(RECOMMENDATIONS),
        "hardware_profiles": HARDWARE_PROFILES,
        "safety_statement": MODEL_FIT_SAFETY_STATEMENT,
        "no_live_mutation": True,
        "secret_values_returned": False,
    })


def recommendation_for_model(model: str) -> dict[str, Any]:
    wanted = str(model or "").strip().lower()
    for item in RECOMMENDATIONS:
        if str(item["model"]).lower() == wanted:
            return safety_flags({"version": APP_VERSION, "item": item, "found": True, "safety_statement": MODEL_FIT_SAFETY_STATEMENT})
    return safety_flags({
        "version": APP_VERSION,
        "found": False,
        "item": {},
        "warnings": ["Model is not in the curated local-fit recommendation table."],
        "safety_statement": MODEL_FIT_SAFETY_STATEMENT,
        "no_live_mutation": True,
        "secret_values_returned": False,
    })


def export_markdown() -> str:
    data = list_model_recommendations()
    lines = [f"# Local LLM Model Recommendations - {APP_VERSION}", "", MODEL_FIT_SAFETY_STATEMENT, ""]
    lines.extend(["## Mac mini M4 16GB", "", "Recommended default: `qwen3:8b`", ""])
    for item in data["items"]:
        lines.extend([
            f"### {item['model']}",
            f"- Runtime: `{item['provider_runtime']}`",
            f"- Memory tier: `{item['memory_tier']}`",
            f"- Use case: {item['intended_use_case']}",
            f"- Install: `{item['install_command']}`",
            f"- Recommended default for 16GB: `{item['recommended_default_for_mac_mini_m4_16gb']}`",
            f"- Experimental on 16GB: `{item['experimental_for_16gb']}`",
            "",
        ])
    return "\n".join(lines)


def export_json_text() -> str:
    return json.dumps(list_model_recommendations(), indent=2, sort_keys=True, default=str)

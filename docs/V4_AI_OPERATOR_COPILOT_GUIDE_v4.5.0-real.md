# AI Operator Copilot Guide - v4.5.0-real

The AI Operator Copilot remains a draft-only assistant for summaries, review packets, task suggestions, and safe operator workflow support. v4.5 links Copilot surfaces to AI Edge where relevant so operators can move from a market row to a review packet.

The copilot cannot approve trades, submit orders, cancel orders, modify live trading configuration, disable read-only mode, disable the kill switch, or turn model estimates into executable instructions.


## AI and Web Search Limits

OpenAI web search is disabled by default and can only be used for explicit research packet workflows when configured by the operator. Local LLMs such as Qwen through Ollama do not natively browse the web in this app; they can review app-provided evidence packets only. AI Edge packet output remains draft/review-only and does not become an accepted task, trade, order, or approval without explicit human action in the appropriate safe workflow.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.

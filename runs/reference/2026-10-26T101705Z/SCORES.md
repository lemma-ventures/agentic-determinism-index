| label | provider | model | case | n_ok | errors | distinct | mode_share | first_divergence_char | byte_identical | tool_call_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 4 | 0.5 | 132 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 8 | 2 | 6 | 0.25 | 1288 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 9 | 1 | 5 | 0.5556 | 562 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 5 | 0.5 | 132 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 9 | 1 | 1 | 1.0 | None | True |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 10 | 0 | 8 | 0.3 | 1271 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 9 | 1 | 2 | 0.8889 | 562 | False |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | freeform-short | 10 | 0 | 7 | 0.4 | 51 | False |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | long-generation | 10 | 0 | 10 | 0.1 | 629 | False |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | reasoning-arith | 10 | 0 | 10 | 0.1 | 17 | False |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | freeform-short | 10 | 0 | 5 | 0.4 | 15 | False |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | json-extract | 1 | 9 | 1 | 1.0 | None | True |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | long-generation | 10 | 0 | 7 | 0.3 | 13 | False |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | reasoning-arith | 10 | 0 | 3 | 0.7 | 71 | False |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | freeform-short | 10 | 0 | 4 | 0.4 | 245 | False |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | long-generation | 10 | 0 | 6 | 0.3 | 32 | False |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | reasoning-arith | 10 | 0 | 4 | 0.6 | 345 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | freeform-short | 10 | 0 | 5 | 0.6 | 0 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | long-generation | 10 | 0 | 10 | 0.1 | 60 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | reasoning-arith | 10 | 0 | 9 | 0.2 | 201 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | freeform-short | 10 | 0 | 7 | 0.4 | 55 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | long-generation | 10 | 0 | 10 | 0.1 | 205 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 93 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | freeform-short | 10 | 0 | 4 | 0.6 | 215 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | long-generation | 10 | 0 | 10 | 0.1 | 88 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 3 | False |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 2 | 0.8 | 229 | False |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 10 | 0.1 | 137 | False |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 4 | 0.6 | 275 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 8 | 2 | 2 | 0.875 | 687 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 2 | 0.6 | 407 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 4 | 0.6 | 124 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 2 | 0.9 | 12 | False |  |
| Groq via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| Groq via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Groq via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 1 | 1.0 | None | True |  |
| Groq via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 5 | 0.4 | 296 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 10 | 0.1 | 18 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 10 | 0.1 | 63 | False |  |
| SambaNova Turbo via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| SambaNova Turbo via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| SambaNova Turbo via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | long-generation | 10 | 0 | 1 | 1.0 | None | True |  |
| SambaNova Turbo via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 10 | 0 | 5 | 0.6 | 179 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | long-generation | 10 | 0 | 10 | 0.1 | 129 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | reasoning-arith | 10 | 0 | 6 | 0.3 | 334 | False |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | long-generation | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | freeform-short | 2 | 8 | 2 | 0.5 | 345 | False |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | json-extract | 2 | 8 | 2 | 0.5 | 1 | False |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | long-generation | 1 | 9 | 1 | 1.0 | None | True |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | reasoning-arith | 3 | 7 | 3 | 0.3333 | 206 | False |  |

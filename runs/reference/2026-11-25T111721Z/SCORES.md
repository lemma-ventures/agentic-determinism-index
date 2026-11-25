| label | provider | model | case | n_ok | errors | distinct | mode_share | first_divergence_char | byte_identical | tool_call_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | freeform-short | 10 | 0 | 6 | 0.3 | 51 | False |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | long-generation | 10 | 0 | 7 | 0.3 | 191 | False |  |
| Nebius direct (Qwen3 30B-A3B MoE) | openai_compatible | Qwen/Qwen3-30B-A3B-Instruct-2507 | reasoning-arith | 10 | 0 | 7 | 0.3 | 17 | False |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | freeform-short | 0 | 10 |  |  |  |  |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | json-extract | 0 | 10 |  |  |  |  |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | long-generation | 0 | 10 |  |  |  |  |  |
| Nebius direct (DeepSeek V4 Flash, reasoning) | openai_compatible | deepseek-ai/DeepSeek-V4-Flash-0731 | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | freeform-short | 10 | 0 | 5 | 0.4 | 154 | False |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | long-generation | 10 | 0 | 6 | 0.4 | 32 | False |  |
| Nebius direct (Gemma 3 27B dense) | openai_compatible | google/gemma-3-27b-it | reasoning-arith | 10 | 0 | 4 | 0.4 | 345 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | freeform-short | 10 | 0 | 4 | 0.5 | 159 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | long-generation | 10 | 0 | 10 | 0.1 | 6 | False |  |
| Nebius direct (gpt-oss-120b, vLLM fingerprint) | openai_compatible | openai/gpt-oss-120b | reasoning-arith | 10 | 0 | 8 | 0.2 | 201 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | freeform-short | 10 | 0 | 9 | 0.2 | 55 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | long-generation | 10 | 0 | 10 | 0.1 | 170 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 93 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | freeform-short | 0 | 10 |  |  |  |  |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | json-extract | 0 | 10 |  |  |  |  |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | long-generation | 0 | 10 |  |  |  |  |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 2 | 0.8 | 687 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 3 | 0.5 | 124 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 2 | 0.8 | 12 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 10 | 0 | 7 | 0.3 | 147 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | long-generation | 10 | 0 | 10 | 0.1 | 129 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | reasoning-arith | 10 | 0 | 7 | 0.4 | 334 | False |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | freeform-short | 0 | 10 |  |  |  |  |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | json-extract | 0 | 10 |  |  |  |  |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | long-generation | 0 | 10 |  |  |  |  |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | reasoning-arith | 0 | 10 |  |  |  |  |  |

| label | provider | model | case | n_ok | errors | distinct | mode_share | first_divergence_char | byte_identical | tool_call_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 9 | 1 | 3 | 0.5556 | 132 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 8 | 2 | 6 | 0.25 | 1591 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 10 | 0 | 5 | 0.4 | 562 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 3 | 0.7 | 132 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 8 | 2 | 1 | 1.0 | None | True |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 6 | 4 | 6 | 0.1667 | 390 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 7 | 3 | 4 | 0.4286 | 813 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | freeform-short | 10 | 0 | 7 | 0.3 | 61 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | long-generation | 10 | 0 | 10 | 0.1 | 170 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 93 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | freeform-short | 10 | 0 | 7 | 0.3 | 205 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | long-generation | 10 | 0 | 10 | 0.1 | 71 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 0 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 2 | 0.8 | 687 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 3 | 0.8 | 265 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 5 | 0.4 | 90 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 2 | 0.9 | 1 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 10 | 0.1 | 18 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 10 | 0.1 | 265 | False |  |
| Crusoe via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| Crusoe via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| Crusoe via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| Crusoe via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Nebius via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | freeform-short | 0 | 10 |  |  |  |  |  |
| Nebius via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | json-extract | 0 | 10 |  |  |  |  |  |
| Nebius via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | long-generation | 0 | 10 |  |  |  |  |  |
| Nebius via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | reasoning-arith | 0 | 10 |  |  |  |  |  |
| Together via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | freeform-short | 10 | 0 | 6 | 0.3 | 160 | False |  |
| Together via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Together via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | long-generation | 10 | 0 | 8 | 0.3 | 76 | False |  |
| Together via OpenRouter | openrouter | meta-llama/llama-3.3-70b-instruct | reasoning-arith | 10 | 0 | 8 | 0.3 | 405 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 10 | 0 | 7 | 0.3 | 147 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | long-generation | 10 | 0 | 9 | 0.2 | 129 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | reasoning-arith | 10 | 0 | 5 | 0.4 | 334 | False |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | long-generation | 10 | 0 | 1 | 1.0 | None | True |  |
| Cerebras via OpenRouter (wafer-scale, single SKU) | openrouter | openai/gpt-oss-120b | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | freeform-short | 10 | 0 | 8 | 0.2 | 0 | False |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | long-generation | 5 | 5 | 5 | 0.2 | 6 | False |  |
| Phala via OpenRouter (TEE, attested stack) | openrouter | openai/gpt-oss-120b | reasoning-arith | 10 | 0 | 7 | 0.4 | 0 | False |  |

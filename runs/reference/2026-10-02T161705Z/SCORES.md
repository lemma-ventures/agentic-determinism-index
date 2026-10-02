| label | provider | model | case | n_ok | errors | distinct | mode_share | first_divergence_char | byte_identical | tool_call_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 2 | 0.9 | 132 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 8 | 2 | 1 | 1.0 | None | True |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 10 | 0 | 8 | 0.3 | 390 | False |  |
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 9 | 1 | 1 | 1.0 | None | True |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 4 | 0.4 | 132 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | long-generation | 8 | 2 | 7 | 0.25 | 390 | False |  |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | reasoning-arith | 9 | 1 | 2 | 0.8889 | 1008 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | freeform-short | 10 | 0 | 7 | 0.4 | 55 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | long-generation | 10 | 0 | 10 | 0.1 | 205 | False |  |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 93 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | freeform-short | 10 | 0 | 5 | 0.4 | 159 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | json-extract | 10 | 0 | 2 | 0.9 | 93 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | long-generation | 10 | 0 | 10 | 0.1 | 88 | False |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | reasoning-arith | 10 | 0 | 10 | 0.1 | 3 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 2 | 8 | 1 | 1.0 | None | True |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 6 | 0.5 | 687 | False |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 9 | 1 | 3 | 0.7778 | 494 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 2 | 0.7 | 407 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 4 | 0.3 | 124 | False |  |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 1 | 1.0 | None | True |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 6 | 0.3 | 90 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | long-generation | 10 | 0 | 10 | 0.1 | 169 | False |  |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | reasoning-arith | 10 | 0 | 10 | 0.1 | 63 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 10 | 0 | 7 | 0.4 | 147 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | json-extract | 10 | 0 | 1 | 1.0 | None | True |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | long-generation | 10 | 0 | 10 | 0.1 | 129 | False |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | reasoning-arith | 10 | 0 | 9 | 0.2 | 334 | False |  |

| label | provider | model | case | n_ok | errors | distinct | mode_share | first_divergence_char | byte_identical |
|---|---|---|---|---|---|---|---|---|---|
| NIM hosted + NIM_FORCE_DETERMINISTIC header | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 8 | 2 | 2 | 0.75 | 182 | False |
| NIM hosted (default) | nvidia_nim | meta/llama-3.2-11b-vision-instruct | freeform-short | 10 | 0 | 2 | 0.8 | 132 | False |
| Amazon Bedrock via OpenRouter | openrouter | amazon/nova-lite-v1 | freeform-short | 10 | 0 | 8 | 0.2 | 61 | False |
| Cohere via OpenRouter | openrouter | cohere/command-r-08-2024 | freeform-short | 0 | 10 |  |  |  |  |
| SiliconFlow via OpenRouter | openrouter | deepseek/deepseek-chat-v3.1 | freeform-short | 10 | 0 | 7 | 0.3 | 205 | False |
| Cloudflare via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 0 | 10 |  |  |  |  |
| CoreWeave via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 2 | 0.9 | 369 | False |
| DeepInfra via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 10 | 0 | 2 | 0.6 | 407 | False |
| Groq via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 5 | 5 | 1 | 1.0 | None | True |
| Novita via OpenRouter | openrouter | meta-llama/llama-3.1-8b-instruct | freeform-short | 0 | 10 |  |  |  |  |
| Azure via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 10 | 0 | 7 | 0.3 | 147 | False |
| OpenAI via OpenRouter | openrouter | openai/gpt-4o-mini | freeform-short | 0 | 10 |  |  |  |  |

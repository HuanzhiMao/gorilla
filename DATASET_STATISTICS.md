# Dataset Statistics

## Multi-Turn Category Statistics

### Number of turns in each multi-turn category:

![Multi-Turn Category Turn Statistics](/function-call-leaderboard/assets/multi-turn-turns-statistics.png)


| Category     | Min | Max | Median | Mean | Std Dev |
|--------------|-----|-----|--------|------|---------|
| `base`         | 1   | 7   | 4.0    | 3.72 | 1.29    |
| `long_context` | 1   | 7   | 4.0    | 3.72 | 1.29    |
| `miss_func`    | 2   | 8   | 5.0    | 4.72 | 1.29    |
| `miss_param`   | 2   | 8   | 5.0    | 4.72 | 1.29    |

Here is a histogram of the number of turns in multi-turn `base` (note that other multi-turn categories have same distributions shape, and `miss_func` and `miss_param` are shifted to the right by 1 turn due to the additional turn requiring users to have clarification):

![Multi-Turn Category Turn Statistics](/function-call-leaderboard/assets/multi-turn-base-turn-statistics.png)

### Distribution of tools used in multi-turn `base` category:
Here, we show the histogram of the number of tools used in multi-turn `base` category (note that other multi-turn categories have same distributions, since we "augment" other categories from the `base` entries):
![Multi-Turn Category Tool Statistics](/function-call-leaderboard/assets/multi-turn-tools-distribution.png)

### Distribution of missing functions, missing function turn idx, and number of missing functions in `miss_func` category:
Here, we show the histogram of the number of missing functions, missing function turn idx, and number of missing functions in `miss_func` category:
![Multi-Turn Category Miss Function Statistics](/function-call-leaderboard/assets/multi-turn-miss-function-stats.png)

| Turn ID Statistics | Value |
|-------------------|-------|
| Count | 222.000000 |
| Mean | 1.932432 |
| Std | 1.117501 |
| Min | 1.000000 |
| 25% | 1.000000 |
| 50% | 2.000000 |
| 75% | 3.000000 |
| Max | 6.000000 |

| Missed Functions per Turn Statistics | Value |
|-------------------------------------|-------|
| Count | 222.000000 |
| Mean | 1.234234 |
| Std | 0.537380 |
| Min | 1.000000 |
| 25% | 1.000000 |
| 50% | 1.000000 |
| 75% | 1.000000 |
| Max | 3.000000 |

| Total Missed Functions per Example Statistics | Value |
|---------------------------------------------|-------|
| Count | 200.000000 |
| Mean | 1.110000 |
| Std | 0.372281 |
| Min | 1.000000 |
| 25% | 1.000000 |
| 50% | 1.000000 |
| 75% | 1.000000 |
| Max | 3.000000 |

### Distribution missing parameter turn idx in `miss_param` category:

Here we show the histogram of the missing parameter turn idx in `miss_param` category:

![Multi-Turn Category Miss Parameter Turn ID Statistics](/function-call-leaderboard/assets/multi-turn-miss-param.png)

| Turn ID Statistics | Value |
|-------------------|-------|
| Count | 203.000000 |
| Mean | 1.256158 |
| Std | 1.306268 |
| Min | 0.000000 |
| 25% | 0.000000 |
| 50% | 1.000000 |
| 75% | 2.000000 |
| Max | 6.000000 |

### Distribution of max input tokens in each category:
Here we show the boxplot of the max input tokens in each category.

Since max input token is dependent on the models' max context length and the multi-step and multi-turn behavior. We display the following representative models to show the distribution:

- `gpt-4o-2024-11-20-FC`
- `Qwen_Qwen2.5-72B-Instruct-FC`
- `gemini-2.0-pro-exp-02-05`
- `meta-llama_Llama-3.3-70B-Instruct`

![gpt-4o-2024-11-20-FC](/function-call-leaderboard/assets/max-context-gpt.png)

![Qwen_Qwen2.5-72B-Instruct-FC](/function-call-leaderboard/assets/max-context-qwen.png)

![gemini-2.0-pro-exp-02-05](/function-call-leaderboard/assets/max-context-gemini.png)

![meta-llama_Llama-3.3-70B-Instruct](/function-call-leaderboard/assets/max-context-llama.png)




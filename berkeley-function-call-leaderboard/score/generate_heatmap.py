import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Build full path to the CSV file
csv_path = os.path.join(script_dir, "data_prompt_variation.csv")

# Now read the CSV safely
df = pd.read_csv(csv_path)

# Clean column names
df.columns = df.columns.str.replace("Prompt Variation \(PV\) Overall Acc", "Overall_Acc", regex=True)

# Drop Rank and Overall Accuracy (keep model name as index)
df = df.drop(columns=["Rank", "Overall_Acc"]).set_index("Model")

# Clean up column names for readability
short_columns = [
    f"{fmt[:2]}+{'tool' if 'has_tool_call_tag_True' in col else 'no_tool'}+{out.split('_')[-1]}"
    for col in df.columns
    for fmt in ["py", "xml", "json"] if fmt in col
    for out in ["python", "json", "verbose", "concise"] if out in col
    if 'prompt_format_plaintext' in col
]

# Apply short column names
df.columns = short_columns[:len(df.columns)]

# Rename 'js+no_tool+python' to 'original'
df = df.rename(columns={'js+no_tool+python': 'original'})

# Convert to float (remove % signs if present)
df = df.applymap(lambda x: float(str(x).replace('%', '')))

# Plot heatmap
plt.figure(figsize=(16, 7))
sns.heatmap(df, annot=True, fmt=".1f", cmap="YlGnBu", cbar_kws={'label': 'Accuracy (%)'})
plt.title("LLM Accuracy Heatmap Across Prompt Variations")
plt.ylabel("Model")
plt.xlabel("Prompt Variation")
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)
plt.tight_layout()

# Save heatmap in the same directory
plt.savefig(os.path.join(script_dir, "llm_accuracy_heatmap.png"), dpi=300)

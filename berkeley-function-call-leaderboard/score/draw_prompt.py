import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import math
import numpy as np
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "data_prompt_variation.csv")
df = pd.read_csv(csv_path)
df.columns = df.columns.str.replace("Prompt Variation \(PV\) Overall Acc", "Overall_Acc", regex=True)
# df = df.drop(columns=["Rank", "Overall_Acc"]).set_index("Model")
data_list = df.values.tolist()

print(f"num of models in total: {len(data_list)}")
import matplotlib.pyplot as plt
import numpy as np

# Sample data (replace with your actual data)

model_names = []
for i in range(0, len(data_list)):
    model_names.append(data_list[i][1])

metrics = ['original', 'markdown', 'experimental']  # Your 3 accuracy types
colors = ["#4ECDC4", "#95D568", "#3C83C1"]

# Accuracy values for each LLM (rows) and metric (columns)

all_acc = []
for i in range(0, len(data_list)):
    acc_nums = data_list[i][3:]
    org_acc = float(acc_nums[5].replace('%', ''))
    md_acc = float(acc_nums[24].replace('%', ''))
    exp_acc = float(acc_nums[25].replace('%', ''))

    all_acc.append([org_acc, md_acc, exp_acc])


llms = model_names[18:27]
accuracy_data = np.array(all_acc[18:27])

# Plot setup
fig, ax = plt.subplots(figsize=(14, 6))
ax.margins(x=0.02)
bar_width = 0.20  # Width of individual bars
x = np.arange(len(llms))  # LLM positions on x-axis

# Create clustered bars
for i in range(len(metrics)):
    ax.bar(x + i*bar_width, accuracy_data[:, i], 
           width=bar_width, 
           color=colors[i],
           label=metrics[i])

# Customization
# ax.set_title('LLM Performance Comparison', pad=20, fontsize=14)
# ax.set_xlabel('Large Language Models', labelpad=10)
ax.set_ylabel('Average Accuracy (%)', labelpad=10)
ax.set_xticks(x + (len(metrics)-1)*bar_width/2)
ax.set_xticklabels(llms, rotation=45, ha='right', rotation_mode='anchor', fontsize=8)
ax.legend(title='', bbox_to_anchor=(1.005, 1))
ax.grid(axis='y', linestyle='--', alpha=0.7)

# Add value labels on bars
for i in range(len(llms)):
    for j in range(len(metrics)):
        height = accuracy_data[i, j]
        ax.text(x[i] + j*bar_width, height + 0.5,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=7)

plt.tight_layout()
plt.savefig(os.path.join(script_dir, "sec4.png"), dpi=300)
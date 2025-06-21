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

metrics = ['python', 'json', 'verbose_xml', 'concise_xml']  # Your 3 accuracy types
colors = ["#4ECDC4", "#95D568", "#3C83C1", "#FFD166"]  # Red, Teal, Blue

# Accuracy values for each LLM (rows) and metric (columns)

all_acc = []
for i in range(0, len(data_list)):
    python_acc = 0.0
    json_acc = 0.0
    verbose_xml_acc = 0.0
    concise_xml_acc = 0.0
    acc_nums = data_list[i][3:27]
    for j in range(0, 6):
        python_acc += float(acc_nums[j].replace('%', ''))
    for j in range(6, 12):
        json_acc += float(acc_nums[j].replace('%', ''))
    for j in range(12, 18):
        verbose_xml_acc += float(acc_nums[j].replace('%', ''))
    for j in range(18, 24):
        concise_xml_acc += float(acc_nums[j].replace('%', ''))

    python_acc /= 6.0
    json_acc /= 6.0
    verbose_xml_acc /= 6.0
    concise_xml_acc /= 6.0
    all_acc.append([python_acc, json_acc, verbose_xml_acc, concise_xml_acc])


llms = model_names[18:27]
accuracy_data = np.array(all_acc[18:27])

# Plot setup
fig, ax = plt.subplots(figsize=(14, 6))
ax.margins(x=0.02)
bar_width = 0.16  # Width of individual bars
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
ax.legend(title='return format', bbox_to_anchor=(1.135, 1))
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
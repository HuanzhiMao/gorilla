import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import math
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "data_prompt_variation.csv")
df = pd.read_csv(csv_path)
df.columns = df.columns.str.replace("Prompt Variation \(PV\) Overall Acc", "Overall_Acc", regex=True)
# df = df.drop(columns=["Rank", "Overall_Acc"]).set_index("Model")
data_list = df.values.tolist()

all_score_path = "/net/scratch2/mingxuanl/gorilla-dev/prompt-variations/gorilla/berkeley-function-call-leaderboard/score_all/data_prompt_variation.csv"
df_all = pd.read_csv(all_score_path)
df_all.columns = df_all.columns.str.replace("Prompt Variation \(PV\) Overall Acc", "Overall_Acc", regex=True)
data_list_all = df_all.values.tolist()

x = []
y = []

for i in range(0, len(data_list)):
    model_name = data_list[i][1]
    for j in range(0, len(data_list_all)):
        model_name_all = data_list_all[j][1]
        if model_name == model_name_all:
            print(model_name)
            for k in range(3, len(data_list_all[j])):
                # if isinstance(data_list[i][k], str) and isinstance(data_list_all[j][k], str):
                #     x.append(data_list[i][k])
                #     y.append(data_list_all[j][k])
                x.append(data_list[i][k])
                y.append(data_list_all[j][k])
            break
print(x)
print(y)
x_values = []
y_values = []

for i in range(0, len(x)):
    x_values.append(float(x[i].replace('%', '')))
    try:
        y_values.append(float(y[i].replace('%', '')))
    except:
        print(y[i])

plt.figure(figsize=(8, 6))

plt.scatter(x_values, y_values, 
            color='red', 
            s=100,
            alpha=0.7,
            edgecolor='black')

plt.title("X-Y Relationship Plot", fontsize=14)
plt.xlabel("X Values (%)", fontsize=12)
plt.ylabel("Y Values (%)", fontsize=12)
plt.grid(True, linestyle='--', alpha=0.3)

import numpy as np
z = np.polyfit(x_values, y_values, 1)
p = np.poly1d(z)
plt.plot(x_values, p(x_values), "b--", linewidth=1, label=f'Trend: y={z[0]:.2f}x + {z[1]:.2f}')

plt.legend()
plt.savefig(os.path.join(script_dir, "sec3.png"), dpi=300)
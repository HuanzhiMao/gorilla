import csv
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics.pairwise import cosine_similarity

df_all = pd.read_csv("./score/data_prompt_variation.csv", header=None)
raw_val_all = df_all.iloc[1:, 2:].values

df_200 = pd.read_csv("./score_200/data_prompt_variation.csv", header=None)
raw_val_200 = df_200.iloc[1:, 2:]. values

def percent_str_to_float(x):
    return float(x.strip('%'))

val_all = [[percent_str_to_float(cell) for cell in row] for row in raw_val_all]
val_200 = [[percent_str_to_float(cell) for cell in row] for row in raw_val_200]
val_all = np.array(val_all)
val_200 = np.array(val_200)

flat_all = val_all.flatten()
flat_200 = val_200.flatten()

correlation = np.corrcoef(flat_all, flat_200)[0, 1]
print("Pearson correlation:", correlation)
spearman_corr, _ = spearmanr(flat_all, flat_200)
print(f"Spearman correlation: {spearman_corr}")
cos_sim = cosine_similarity([flat_all], [flat_200])[0, 0]
print(f"cos sim: {cos_sim}")
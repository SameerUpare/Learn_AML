
import pandas as pd
import matplotlib.pyplot as plt

def plot_score_hist(df_scored: pd.DataFrame, col: str = "anomaly_score"):
    plt.figure()
    df_scored[col].hist(bins=50)
    plt.title("Anomaly Score Distribution")
    plt.xlabel(col)
    plt.ylabel("Count")
    return plt.gcf()

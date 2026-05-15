"""All plotting helpers used by the notebook and reports."""
from __future__ import annotations

from typing import Iterable, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_curve,
)


sns.set_theme(style="whitegrid", context="talk")


def plot_training_curves(history: list[dict], save: Optional[str] = None) -> plt.Figure:
    """history: list of {"epoch", "loss", "eval_loss", "eval_f1"} dicts."""
    df = pd.DataFrame(history)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    if "loss" in df:
        axes[0].plot(df["epoch"], df["loss"], label="train loss", marker="o")
    if "eval_loss" in df:
        axes[0].plot(df["epoch"], df["eval_loss"], label="val loss", marker="o")
    axes[0].set_xlabel("epoch"); axes[0].set_ylabel("loss"); axes[0].set_title("Training curves"); axes[0].legend()
    if "eval_f1" in df:
        axes[1].plot(df["epoch"], df["eval_f1"], label="val F1", marker="o", color="C2")
        axes[1].set_xlabel("epoch"); axes[1].set_ylabel("F1"); axes[1].set_title("Validation F1")
        axes[1].set_ylim(0, 1)
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_roc_curves(curves: dict[str, tuple[np.ndarray, np.ndarray]], save: Optional[str] = None) -> plt.Figure:
    """curves: {"model_name": (y_true, y_score_for_class1)}"""
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, (y_true, y_score) in curves.items():
        if len(set(y_true)) < 2:
            continue
        fpr, tpr, _ = roc_curve(y_true, y_score)
        a = auc(fpr, tpr)
        ax.plot(fpr, tpr, label=f"{name} (AUC={a:.3f})", linewidth=2)
    ax.plot([0, 1], [0, 1], "--", color="gray", alpha=0.5)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC — alert classifier comparison"); ax.legend(loc="lower right", fontsize=11)
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_f1_by_model(results: pd.DataFrame, save: Optional[str] = None) -> plt.Figure:
    """results columns: model, f1, precision, recall."""
    df = results.melt(id_vars="model", value_vars=["f1", "precision", "recall"])
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=df, x="model", y="value", hue="variable", ax=ax)
    ax.set_ylim(0, 1); ax.set_ylabel("score"); ax.set_xlabel("")
    ax.set_title("Incremental improvement across stages")
    ax.tick_params(axis="x", rotation=20)
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_confusion(y_true, y_pred, title: str = "Confusion matrix", save: Optional[str] = None) -> plt.Figure:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["FP (pred)", "TP (pred)"], yticklabels=["FP (true)", "TP (true)"], ax=ax)
    ax.set_title(title)
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_tsne_embeddings(
    embeddings: np.ndarray, labels: np.ndarray, epss: Optional[np.ndarray] = None,
    save: Optional[str] = None, sample: int = 1500
) -> plt.Figure:
    from sklearn.manifold import TSNE
    n = min(sample, len(embeddings))
    idx = np.random.default_rng(0).choice(len(embeddings), n, replace=False)
    emb = embeddings[idx]; lbl = labels[idx]
    coords = TSNE(n_components=2, init="pca", learning_rate="auto", random_state=0).fit_transform(emb)
    fig, ax = plt.subplots(figsize=(8, 6))
    palette = {0: "tab:blue", 1: "tab:red"}
    for k in (0, 1):
        m = lbl == k
        ax.scatter(coords[m, 0], coords[m, 1], s=8, alpha=0.6, c=palette[k],
                   label="TRUE_POSITIVE" if k == 1 else "FALSE_POSITIVE")
    ax.set_title("t-SNE of RoBERTa [CLS] embeddings")
    ax.legend(); ax.set_xlabel("t-SNE 1"); ax.set_ylabel("t-SNE 2")
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_cvss_epss_scatter(df: pd.DataFrame, save: Optional[str] = None) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.scatterplot(
        data=df.sample(min(len(df), 3000), random_state=0),
        x="cvss_score", y="epss", hue="label", style="label",
        alpha=0.6, ax=ax, palette={0: "tab:blue", 1: "tab:red"},
    )
    ax.set_yscale("log"); ax.set_ylim(1e-4, 1)
    ax.set_xlabel("CVSS v3 score"); ax.set_ylabel("EPSS (log scale)")
    ax.set_title("CVSS vs EPSS — colored by ground-truth label")
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_f1_by_ecosystem(df_metrics: pd.DataFrame, save: Optional[str] = None) -> plt.Figure:
    """df_metrics columns: ecosystem, f1."""
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df_metrics, x="ecosystem", y="f1", ax=ax, color="C0")
    ax.set_ylim(0, 1); ax.set_title("F1 by ecosystem (full pipeline)")
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def plot_call_graph(
    call_graph, highlight_path: Optional[list[str]] = None, save: Optional[str] = None,
    max_nodes: int = 60,
) -> plt.Figure:
    """Render a small subgraph for the demo."""
    import networkx as nx
    g = call_graph.graph
    if len(g) > max_nodes and highlight_path:
        # subgraph of nodes near the highlight path
        keep = set(highlight_path)
        for n in list(keep):
            keep.update(g.predecessors(n))
            keep.update(g.successors(n))
        g = g.subgraph(keep).copy()
    elif len(g) > max_nodes:
        g = g.subgraph(list(g.nodes)[:max_nodes]).copy()

    pos = nx.spring_layout(g, seed=0, k=0.8)
    fig, ax = plt.subplots(figsize=(10, 7))
    nx.draw_networkx_nodes(g, pos, node_color="#c8d8f0", node_size=600, ax=ax)
    nx.draw_networkx_edges(g, pos, alpha=0.4, arrows=True, ax=ax)
    labels = {n: n.split(".")[-1][:20] for n in g.nodes}
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=8, ax=ax)
    if highlight_path:
        path_edges = list(zip(highlight_path[:-1], highlight_path[1:]))
        nx.draw_networkx_edges(g, pos, edgelist=path_edges, edge_color="red", width=2.5, ax=ax)
        nx.draw_networkx_nodes(g, pos, nodelist=highlight_path, node_color="#f7c8c8", node_size=700, ax=ax)
    ax.set_title("Call graph — vulnerable path highlighted")
    ax.set_axis_off()
    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    return fig


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
    }

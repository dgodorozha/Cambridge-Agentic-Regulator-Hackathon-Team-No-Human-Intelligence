"""Surveillance candidates under test.

Each sentinel observes only prices, returns and order flows (never ground
truth labels) and produces, per scenario:
  - stress_index:  (T,) aggregate market stress series
  - flags:         (N,) bool, agents identified as destabilising (final call)
  - first_alert:   int or None, first step the sentinel raised an alert
  - flags_online:  (T, N) bool, the agents the sentinel had flagged using
                   data up to and including step t. Interventions consume
                   this matrix, so no rule can act on information the
                   sentinel did not have at the time.

Version 3 adds the three herding versus noise candidates of `herding.py`
(buy sell imbalance, Hawkes endogeneity, lead lag ignition), so seven tools
are ranked and Kendall tau takes many more values than it could with four.

The four core candidates span the design space deliberately:
  NaiveThreshold   tracks aggregate volatility almost perfectly (high
                   aggregate fidelity) but cannot localise, so it flags
                   everyone once stress is high (poor decision accuracy).
  CorrClustering   rolling correlation clustering of order flows.
  NetworkSentinel  correlation graph community centrality; localises well
                   but its stress index tracks clusters, not volatility.
  AbsorptionRatio  share of flow variance absorbed by the leading
                   eigenvector (after Kritzman et al., 2011); localises by
                   loading on that eigenvector.
"""

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
import networkx as nx


from ._common import _rolling_vol, _online_matrix  # noqa: F401 (re-exported)


class NaiveThreshold:
    name = "naive_threshold"
    label = "Volatility trigger"

    def __init__(self, k=1.8):
        self.k = k

    def run(self, res):
        vol = _rolling_vol(res.returns)
        base = np.median(vol[vol > 0]) + 1e-9
        stress = vol / base
        alert_ts = np.where(stress > self.k)[0]
        first = int(alert_ts[0]) if len(alert_ts) else None
        T, n = res.flows.shape
        flags = np.zeros(n, dtype=bool)
        events = []
        if first is not None:
            flags[:] = True          # cannot localise: flags every agent
            events.append((first, np.arange(n)))
        return {"stress_index": stress, "flags": flags, "first_alert": first,
                "flags_online": _online_matrix(T, n, events)}


class CorrClustering:
    name = "corr_clustering"
    label = "Correlation clustering"

    def __init__(self, window=80, corr_thresh=0.45, min_size=8, k_stress=1.5,
                 stride=10):
        self.window, self.corr_thresh = window, corr_thresh
        self.min_size, self.k_stress, self.stride = min_size, k_stress, stride

    def _clusters_at(self, flows, t):
        seg = flows[max(0, t - self.window):t]
        if seg.shape[0] < 30:
            return None, None
        C = np.corrcoef(seg.T)
        C = np.nan_to_num(C, nan=0.0)
        d = np.clip(1 - C, 0, 2)
        np.fill_diagonal(d, 0.0)
        d = (d + d.T) / 2
        Z = linkage(squareform(d, checks=False), method="average")
        labels = fcluster(Z, t=1 - self.corr_thresh, criterion="distance")
        return C, labels

    def run(self, res):
        T, n = res.flows.shape
        stress = np.zeros(T)
        flags = np.zeros(n, dtype=bool)
        first = None
        vol = _rolling_vol(res.returns)
        base = np.median(vol[vol > 0]) + 1e-9
        peak_mass, peak_members, events = 0.0, None, []
        for t in range(0, T, self.stride):
            C, labels = self._clusters_at(res.flows, t)
            if C is None:
                continue
            best_mass = 0.0
            best_members = None
            for lab in np.unique(labels):
                members = np.where(labels == lab)[0]
                if len(members) < self.min_size:
                    continue
                sub = C[np.ix_(members, members)]
                intra = (sub.sum() - len(members)) / max(1, len(members) ** 2 - len(members))
                mass = intra * len(members) / n
                if mass > best_mass:
                    best_mass, best_members = mass, members
            stress[t:t + self.stride] = best_mass * 4.0
            if best_members is not None and best_mass * 4.0 > 1.0 \
                    and vol[t] > self.k_stress * base:
                if first is None:
                    first = t
                if best_mass > peak_mass:
                    peak_mass, peak_members = best_mass, best_members
                    events.append((t, best_members))
        if peak_members is not None:
            flags[peak_members] = True
        return {"stress_index": stress, "flags": flags, "first_alert": first,
                "flags_online": _online_matrix(T, n, events)}


class NetworkSentinel:
    name = "network_sentinel"
    label = "Network community sentinel"

    def __init__(self, window=80, edge_thresh=0.5, min_comm=8, stride=10,
                 alert_level=1.25):
        self.window, self.edge_thresh, self.min_comm = window, edge_thresh, min_comm
        self.stride, self.alert_level = stride, alert_level

    def run(self, res):
        T, n = res.flows.shape
        stress = np.zeros(T)
        flags = np.zeros(n, dtype=bool)
        first = None
        peak_mass, peak_members, events = 0.0, None, []
        for t in range(0, T, self.stride):
            seg = res.flows[max(0, t - self.window):t]
            if seg.shape[0] < 30:
                continue
            C = np.nan_to_num(np.corrcoef(seg.T), nan=0.0)
            A = (np.abs(C) > self.edge_thresh).astype(float)
            np.fill_diagonal(A, 0)
            iu = np.triu_indices_from(A, 1)
            hit = A[iu] > 0
            G = nx.Graph()
            G.add_nodes_from(range(n))
            G.add_edges_from(zip(iu[0][hit].tolist(), iu[1][hit].tolist()))
            # Louvain with a fixed seed (version 3): the same community construct as the
            # greedy modularity method of versions 1 and 2, two to three times faster;
            # flags and first alerts were identical on every scenario compared.
            comms = [c for c in nx.community.louvain_communities(G, seed=0)
                     if len(c) >= self.min_comm] if G.number_of_edges() else []
            mass = 0.0
            members = None
            for c in comms:
                c = np.array(sorted(c))
                sub = C[np.ix_(c, c)]
                intra = (np.abs(sub).sum() - len(c)) / max(1, len(c) ** 2 - len(c))
                m = intra * len(c) / n
                if m > mass:
                    mass, members = m, c
            stress[t:t + self.stride] = mass * 4.0
            if members is not None and mass * 4.0 > self.alert_level:
                if first is None:
                    first = t
                if mass > peak_mass:
                    peak_mass, peak_members = mass, members
                    events.append((t, members))
        if peak_members is not None:
            flags[peak_members] = True
        return {"stress_index": stress, "flags": flags, "first_alert": first,
                "flags_online": _online_matrix(T, n, events)}


class AbsorptionRatio:
    """Absorption ratio: the share of total flow variance explained by the
    leading eigenvector of the rolling flow correlation matrix. A rising
    ratio means the market is increasingly driven by one common factor.
    Localisation: agents whose loading on that eigenvector is at least half
    the largest loading."""
    name = "absorption_ratio"
    label = "Absorption ratio"

    def __init__(self, window=80, ar_thresh=0.31, load_frac=0.5, stride=10):
        self.window, self.ar_thresh = window, ar_thresh
        self.load_frac, self.stride = load_frac, stride

    def run(self, res):
        T, n = res.flows.shape
        stress = np.zeros(T)
        flags = np.zeros(n, dtype=bool)
        first = None
        peak, peak_members, events = 0.0, None, []
        for t in range(0, T, self.stride):
            seg = res.flows[max(0, t - self.window):t]
            if seg.shape[0] < 30:
                continue
            C = np.nan_to_num(np.corrcoef(seg.T), nan=0.0)
            w, V = np.linalg.eigh(C)
            ar = float(w[-1] / n)
            stress[t:t + self.stride] = ar / self.ar_thresh
            if ar > self.ar_thresh:
                load = np.abs(V[:, -1])
                members = np.where(load >= self.load_frac * load.max())[0]
                if first is None:
                    first = t
                if ar > peak:
                    peak, peak_members = ar, members
                    events.append((t, members))
        if peak_members is not None:
            flags[peak_members] = True
        return {"stress_index": stress, "flags": flags, "first_alert": first,
                "flags_online": _online_matrix(T, n, events)}


from .herding import HERDING_SENTINELS  # noqa: E402

CORE_SENTINELS = [NaiveThreshold, CorrClustering, NetworkSentinel, AbsorptionRatio]
ALL_SENTINELS = CORE_SENTINELS + HERDING_SENTINELS
SENTINEL_LABELS = {S.name: S.label for S in ALL_SENTINELS}

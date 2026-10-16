"""P4: danh gia tu data/gt_runs.csv -> report/metrics.md + PNG.

python evaluate.py [--csv data/gt_runs.csv] [--out report]
Xuat: (a) MAE/p95 theo z va theo yaw, raw va KF; (b) bieu do loi theo z, theo yaw;
(c) std dung yen raw vs KF; (d) ti le loi thuc nam trong +-2 sigma; (e) latency p50/p95;
cong them ti le nhan dien, phan bo status, va bang so lieu cho tung ca loi.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AXES = [("x", "cm"), ("z", "cm"), ("yaw", "deg")]


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def add_errors(df):
    for ax, _ in AXES:
        for src in ("raw", "kf"):
            e = df[f"est_{src}_{ax}"] - df[f"gt_{ax}"]
            df[f"err_{src}_{ax}"] = wrap_deg(e) if ax == "yaw" else e
    return df


def p95(s):
    s = s.dropna().abs()
    return float(np.percentile(s, 95)) if len(s) else float("nan")


def mae(s):
    return float(s.dropna().abs().mean())


def table_by(df, key):
    rows = []
    for val, g in df.groupby(key):
        r = {key: val, "n": len(g), "found_%": 100 * g["found"].mean()}
        for ax, _ in AXES:
            for src in ("raw", "kf"):
                r[f"MAE_{src}_{ax}"] = mae(g[f"err_{src}_{ax}"])
                r[f"p95_{src}_{ax}"] = p95(g[f"err_{src}_{ax}"])
        rows.append(r)
    return pd.DataFrame(rows)


def static_std(df):
    """Std trong 30 frame cua moi tu the (thẻ dung yen), lay trung vi qua cac tu the."""
    rows = []
    for ax, unit in AXES:
        raw = df.groupby("pose_id")[f"est_raw_{ax}"].std().median()
        kf = df.groupby("pose_id")[f"est_kf_{ax}"].std().median()
        # std ben voi outlier: 1.4826 * MAD (bang std neu nhieu Gaussian)
        robust = df.groupby("pose_id")[f"est_raw_{ax}"].apply(
            lambda s: 1.4826 * (s - s.median()).abs().median()).median()
        rows.append({"truc": f"{ax} ({unit})", "std_raw": raw, "std_raw_MAD": robust, "std_kf": kf,
                     "giam_%": 100 * (1 - kf / raw) if raw > 0 else float("nan")})
    return pd.DataFrame(rows)


def coverage(df, gt_err):
    """Ti le |loi KF| <= 2 sigma. Ban 'co GT' cong them sai so thuoc vao sigma: sqrt(s^2 + gt^2)."""
    rows = []
    for ax, unit in AXES:
        e = df[f"err_kf_{ax}"].abs()
        s = df[f"sigma_{ax}"]
        s_gt = np.sqrt(s ** 2 + gt_err[ax] ** 2)
        rows.append({"truc": f"{ax} ({unit})", "trong_2sigma_%": 100 * (e <= 2 * s).mean(),
                     "trong_2sigma_co_GT_%": 100 * (e <= 2 * s_gt).mean(), "ky_vong_%": 95.4})
    return pd.DataFrame(rows)


def plot_err(df, key, fname, out):
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    for a, (ax, unit) in zip(axs, AXES):
        for src, color in (("raw", "tab:orange"), ("kf", "tab:blue")):
            g = df.groupby(key)[f"err_{src}_{ax}"]
            m = g.apply(lambda s: s.abs().mean())
            q = g.apply(p95)
            a.plot(m.index, m.values, "o-", color=color, label=f"MAE {src}")
            a.plot(q.index, q.values, "x--", color=color, alpha=0.6, label=f"p95 {src}")
        a.set_xlabel(key.replace("gt_", "") + (" (cm)" if key != "gt_yaw" else " (deg)"))
        a.set_ylabel(f"|loi {ax}| ({unit})")
        a.grid(alpha=0.3)
        a.legend(fontsize=8)
    fig.suptitle(f"Loi theo {key.replace('gt_', '')}")
    fig.tight_layout()
    path = os.path.join(out, fname)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def failure_summary(df):
    rows = []
    for case, g in df.groupby("case"):
        rows.append({"case": case, "n": len(g), "found_%": 100 * g["found"].mean(),
                     "ambiguous_%": 100 * g["ambiguous"].mean(),
                     "reproj_med_px": g["reproj_err"].median(),
                     "GOOD_%": 100 * (g["status"] == "GOOD").mean(),
                     "DEGRADED_%": 100 * (g["status"] == "DEGRADED").mean(),
                     "LOST_%": 100 * (g["status"] == "LOST").mean(),
                     "MAE_raw_z": mae(g["err_raw_z"]), "MAE_raw_yaw": mae(g["err_raw_yaw"])})
    return pd.DataFrame(rows)


def md(df):
    """Bang markdown, khong can thu vien tabulate."""
    def cell(v):
        return f"{v:.2f}" if isinstance(v, (float, np.floating)) else str(v)
    lines = ["| " + " | ".join(df.columns) + " |", "|" + " --- |" * len(df.columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/gt_runs.csv")
    ap.add_argument("--out", default="report")
    ap.add_argument("--gt-err-cm", type=float, default=0.2, help="sai so thuoc day (cm)")
    ap.add_argument("--gt-err-deg", type=float, default=2.0, help="sai so thuoc do goc (deg)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    df = add_errors(pd.read_csv(args.csv))
    grid = df[df["case"] == "grid"]
    found = grid[grid["found"] == 1]
    gt_err = {"x": args.gt_err_cm, "z": args.gt_err_cm, "yaw": args.gt_err_deg}
    synthetic = "synthetic" in os.path.basename(args.csv)
    tag = "_synthetic" if synthetic else ""

    lat = df["latency_total_ms"].dropna()
    lat_txt = f"p50 = {np.percentile(lat, 50):.1f} ms, p95 = {np.percentile(lat, 95):.1f} ms (n={len(lat)})" \
        if len(lat) else "khong co du lieu"
    p_z = plot_err(found, "gt_z", f"error_vs_z{tag}.png", args.out)
    p_yaw = plot_err(found, "gt_yaw", f"error_vs_yaw{tag}.png", args.out)

    parts = [f"# Ket qua danh gia ({os.path.basename(args.csv)})", ""]
    if synthetic:
        parts += ["> **DU LIEU GIA** tu synthetic.py, chi de kiem tra pipeline. KHONG dung lam bang chung.", ""]
    parts += [
        f"Tong {len(df)} frame, {grid['pose_id'].nunique()} tu the luoi, ti le nhan dien luoi "
        f"{100 * grid['found'].mean():.1f}%. Sai so GT gia dinh: +-{args.gt_err_cm} cm, +-{args.gt_err_deg} deg.",
        "", "## (a) Loi theo khoang cach z", "", md(table_by(found, "gt_z")),
        "", "## (a) Loi theo yaw", "", md(table_by(found, "gt_yaw")),
        "", "## (b) Bieu do", "", f"![loi theo z]({os.path.basename(p_z)})",
        f"![loi theo yaw]({os.path.basename(p_yaw)})",
        "", "## (c) Do rung dung yen (std trong 30 frame, trung vi qua cac tu the)", "", md(static_std(found)),
        "", "## (d) Sigma cua Kalman co dang tin? (ti le |loi| <= 2 sigma)", "", md(coverage(found, gt_err)),
        "", "Neu ti le thap hon nhieu so voi 95%: sigma qua lac quan (R hoac Q qua nho) hoac co loi he thong "
            "(bias hieu chuan, kich thuoc marker) ma filter khong biet.",
        "", "## (e) Do tre tong (capture -> xong filter)", "", lat_txt,
        "", "## Phan bo status va ca loi", "", md(failure_summary(df)), "",
    ]
    path = os.path.join(args.out, f"metrics{tag}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("\n".join(parts))
    print(f"\nDa ghi {path}, {p_z}, {p_yaw}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Строит все таблицы и графики отчёта из CSV репозитория одной командой.

    python scripts/make_tables.py                # из корня репозитория
    python scripts/make_tables.py --no-figures   # только таблицы

Источники данных (относительно корня репозитория):
  reports/final_report/vlfm_episodes.csv                              VLFM, диагностический повтор (по эпизодам) = опорный прогон
  reports/diagnostics/paired_vlfm_greedy_50ep_diagnostic_only.csv     Greedy frontier на тех же 50 эпизодах
  reports/cafs_50ep_20261103_091737/baseline_vs_cafs.csv              CAFS на тех же 50 эпизодах
  reports/diagnostics/{vlfm,cafs}_moderate_failure_causes.csv         неудачи при умеренном шуме (только неудачные эпизоды)
  reports/repro_snapshot_2026-10-22/vlfm_results.csv                  агрегаты основного прогона VLFM и OracleFBE
  reports/final_report/noise_aggregates.csv                           агрегаты шумовых прогонов (построчных данных нет)
  reports/final_report/oracle_failure_causes.csv                      причины неудач OracleFBE (агрегаты)
  reports/noise/*/episodes.csv                                        (необязательно) построчные результаты прогонов scripts/run_noise_experiment.sh

Статистика: доверительные интервалы Уилсона для SR; точный критерий Макнемара (парные эпизоды); критерий Фишера
(независимые выборки); бутстрап-интервал (10000 повторов, seed 0) для разности средних SPL по парным эпизодам.
Зависимости: numpy; matplotlib нужен только для рисунков.
"""
from __future__ import annotations

import argparse
import csv
import sys
from math import comb, sqrt
from pathlib import Path

import numpy as np

P_VLFM = "reports/final_report/vlfm_episodes.csv"
P_GREEDY = "reports/diagnostics/paired_vlfm_greedy_50ep_diagnostic_only.csv"
P_CAFS = "reports/cafs_50ep_20261103_091737/baseline_vs_cafs.csv"
P_MOD_V = "reports/diagnostics/vlfm_moderate_failure_causes.csv"
P_MOD_C = "reports/diagnostics/cafs_moderate_failure_causes.csv"
P_AGG = "reports/repro_snapshot_2026-10-22/vlfm_results.csv"
P_NOISE = "reports/final_report/noise_aggregates.csv"
P_ORACLE = "reports/final_report/oracle_failure_causes.csv"


# ----------------------------------------------------------------------------- утилиты
def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fb(x) -> bool:
    return str(x).strip().lower() in ("1", "1.0", "true")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def binom_two_sided(k: int, n: int) -> float:
    """Точный двусторонний критерий для p=0.5 (Макнемар по дискордантным парам, знаковый тест)."""
    if n == 0:
        return 1.0
    pk = comb(n, k)
    return min(1.0, sum(comb(n, i) for i in range(n + 1) if comb(n, i) <= pk) / 2**n)


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Точный критерий Фишера для таблицы [[a, b], [c, d]]."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d

    def pmf(x: int) -> float:
        return comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)

    po = pmf(a)
    lo, hi = max(0, r1 - (n - c1)), min(r1, c1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= po * (1 + 1e-9)))


def boot_ci(diff: np.ndarray, boot: int, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(diff, (boot, len(diff))).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def fmt_ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k / n:.2f} [{lo:.2f}; {hi:.2f}]"


# ----------------------------------------------------------------------------- загрузка
def load(root: Path):
    d: dict = {}
    d["vlfm"] = {r["episode_id"]: r for r in read_csv(root / P_VLFM)}
    d["greedy"] = {r["episode"]: r for r in read_csv(root / P_GREEDY)}
    d["cafs"] = {r["episode_id"]: r for r in read_csv(root / P_CAFS)}
    d["mod_v"] = {r["episode_id"]: r for r in read_csv(root / P_MOD_V)}
    d["mod_c"] = {r["episode_id"]: r for r in read_csv(root / P_MOD_C)}
    d["agg"] = read_csv(root / P_AGG)
    d["noise"] = read_csv(root / P_NOISE)
    d["oracle"] = read_csv(root / P_ORACLE)
    d["runs"] = {}
    for p in sorted((root / "reports" / "noise").glob("*/episodes.csv")):
        d["runs"][p.parent.name] = read_csv(p)
    return d


def check_ids(d: dict) -> list[str]:
    msgs, ref = [], set(d["vlfm"])
    for name, ids in (("greedy", set(d["greedy"])), ("cafs", set(d["cafs"]))):
        msgs.append(f"ID: опорный прогон VLFM == {name}: {'OK' if ref == ids else 'НЕ СОВПАДАЕТ'} ({len(ref)} / {len(ids)})")
    for name in ("mod_v", "mod_c"):
        ok = set(d[name]) <= ref
        msgs.append(f"ID: неудачи {name} ⊂ опорный набор: {'OK' if ok else 'НЕТ'}")
    for run, rows in d["runs"].items():
        ids = {str(r["episode_id"]) for r in rows}
        msgs.append(f"ID: прогон {run} == опорный набор: {'OK' if ids == ref else f'НЕ СОВПАДАЕТ ({len(ids)} эп.)'}")
    return msgs


# ----------------------------------------------------------------------------- таблицы
def summarize(rows: list[dict], sk="success", spl="spl", soft="soft_spl", dist="distance_to_goal", det="target_detected", stop="stop_called"):
    n = len(rows)
    k = sum(float(r[sk]) == 1.0 for r in rows)
    mean = lambda key: float(np.mean([float(r[key]) for r in rows]))
    return dict(n=n, k=k, spl=mean(spl), soft=mean(soft), dist=mean(dist),
                det=float(np.mean([fb(r[det]) for r in rows])), stop=float(np.mean([fb(r[stop]) for r in rows])))


def main_table(d: dict):
    entries = []
    for r in d["agg"]:
        if r["method"] == "VLFM" and r["episodes"] == "50":
            entries.append(("VLFM, основной прогон (агрегаты из лога)", int(r["episodes"]), int(r["successes"]), float(r["SPL"]),
                            float(r["SoftSPL"]), float(r["mean_distance_to_goal"]), float(r["target_detected"]), float(r["stop_called"])))
    s = summarize(list(d["vlfm"].values()))
    entries.append(("VLFM, повтор (опорный прогон, по эпизодам)", s["n"], s["k"], s["spl"], s["soft"], s["dist"], s["det"], s["stop"]))
    g = summarize(list(d["greedy"].values()), "success_greedy", "spl_greedy", "soft_spl_greedy", "distance_to_goal_greedy",
                  "target_detected_greedy", "stop_called_greedy")
    entries.append(("Greedy frontier (nearest), по эпизодам", g["n"], g["k"], g["spl"], g["soft"], g["dist"], g["det"], g["stop"]))
    c = summarize(list(d["cafs"].values()), "cafs_success", "cafs_spl", "cafs_soft_spl", "cafs_distance", "cafs_target_detected", "cafs_stop_called")
    entries.append(("CAFS (λ=0.15), по эпизодам", c["n"], c["k"], c["spl"], c["soft"], c["dist"], c["det"], c["stop"]))
    for r in d["agg"]:
        if r["method"] == "OracleFBE":
            entries.append(("OracleFBE (агрегаты из лога)", int(r["episodes"]), int(r["successes"]), float(r["SPL"]),
                            float(r["SoftSPL"]), float(r["mean_distance_to_goal"]), float(r["target_detected"]), float(r["stop_called"])))
    rows = [[n_, n, k, n - k, fmt_ci(k, n), f"{spl:.4f}", f"{soft:.4f}", f"{dist:.2f}", f"{det:.2f}", f"{stop:.2f}"]
            for (n_, n, k, spl, soft, dist, det, stop) in entries]
    header = ["Запуск", "N", "Успехи", "Неудачи", "SR [95% ДИ Уилсона]", "SPL", "SoftSPL", "Ср. расст., м", "Target detected", "Stop called"]
    note = ("\nSPL/SoftSPL greedy и CAFS считаются по значениям, округлённым в исходных CSV до 2 знаков. "
            "Прогон из 5 эпизодов (SR 0.80) в сравнения не входит.")
    return md_table(header, rows) + "\n" + note, entries


def paired_table(d: dict, boot: int):
    ref = d["vlfm"]
    rows = []
    # VLFM (повтор) против greedy
    ids = sorted(set(ref) & set(d["greedy"]))
    a = np.array([float(ref[i]["success"]) for i in ids]); b = np.array([float(d["greedy"][i]["success_greedy"]) for i in ids])
    sa = np.array([float(ref[i]["spl"]) for i in ids]); sb = np.array([float(d["greedy"][i]["spl_greedy"]) for i in ids])
    ta = np.array([float(ref[i]["soft_spl"]) for i in ids]); tb = np.array([float(d["greedy"][i]["soft_spl_greedy"]) for i in ids])
    rows.append(_pair_row("VLFM против Greedy frontier", a, b, sa, sb, ta, tb, boot))
    # baseline (повтор) против CAFS — собственные столбцы файла
    ids = sorted(d["cafs"])
    a = np.array([float(d["cafs"][i]["baseline_success"]) for i in ids]); b = np.array([float(d["cafs"][i]["cafs_success"]) for i in ids])
    sa = np.array([float(d["cafs"][i]["baseline_spl"]) for i in ids]); sb = np.array([float(d["cafs"][i]["cafs_spl"]) for i in ids])
    ta = np.array([float(d["cafs"][i]["baseline_soft_spl"]) for i in ids]); tb = np.array([float(d["cafs"][i]["cafs_soft_spl"]) for i in ids])
    rows.append(_pair_row("VLFM против CAFS", a, b, sa, sb, ta, tb, boot))
    header = ["Сравнение (A против B)", "Общих эп.", "Только A успешен", "Только B успешен", "p (Макнемар, точный)", "ΔSR (B−A)",
              "ΔSPL (B−A) [95% бутстрап]", "ΔSoftSPL (B−A) [95% бутстрап]"]
    return md_table(header, rows)


def _pair_row(name, a, b, sa, sb, ta, tb, boot):
    only_a, only_b = int(((a == 1) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
    p = binom_two_sided(only_a, only_a + only_b)
    d_spl, d_soft = sb - sa, tb - ta
    lo, hi = boot_ci(d_spl, boot); lo2, hi2 = boot_ci(d_soft, boot)
    return [name, len(a), only_a, only_b, f"{p:.3f}", f"{b.mean() - a.mean():+.2f}",
            f"{d_spl.mean():+.4f} [{lo:+.3f}; {hi:+.3f}]", f"{d_soft.mean():+.4f} [{lo2:+.3f}; {hi2:+.3f}]"]


def unpaired_table(entries) -> str:
    fbe = [e for e in entries if e[0].startswith("OracleFBE")]
    rows = []
    if fbe:
        k_f, n_f = fbe[0][2], fbe[0][1]
        for e in entries:
            if e[0].startswith("VLFM"):
                rows.append([f"{e[0]} против OracleFBE", f"{e[2]}/{e[1]}", f"{k_f}/{n_f}", f"{fisher_two_sided(e[2], e[1] - e[2], k_f, n_f - k_f):.4f}"])
    return md_table(["Сравнение (независимые выборки)", "Успехи A", "Успехи B", "p (Фишер)"], rows) + \
        "\n\nСправедливо при допущении независимых выборок эпизодов (ID основного прогона и OracleFBE не сохранены)."


def noise_table(d: dict) -> str:
    rows = []
    prev = None
    for r in d["noise"]:
        n, k = int(r["n"]), int(r["successes"])
        p = "" if prev is None else f"{fisher_two_sided(prev[1], prev[0] - prev[1], k, n - k):.4f}"
        rows.append([r["level"], r["xy_white_m"], r["yaw_white_deg"], r["xy_drift_m_per_step"], r["yaw_drift_deg_per_step"], n,
                     fmt_ci(k, n), r["spl"], r["soft_spl"], r["mean_distance_m"], r["target_detected"], p])
        prev = (n, k)
    header = ["Уровень", "σ xy, м", "σ yaw, °", "дрейф xy, м/шаг", "дрейф yaw, °/шаг", "N", "SR [95% ДИ]", "SPL", "SoftSPL",
              "Ср. расст., м", "Target detected", "p (Фишер) к предыдущему"]
    out = md_table(header, rows)
    if d["runs"]:
        extra = []
        for run, rr in d["runs"].items():
            s = summarize(rr)
            extra.append([run, s["n"], fmt_ci(s["k"], s["n"]), f"{s['spl']:.4f}", f"{s['soft']:.4f}", f"{s['dist']:.2f}", f"{s['det']:.2f}"])
        out += "\n\nПрогоны scripts/run_noise_experiment.sh (по эпизодам):\n\n" + md_table(
            ["Прогон", "N", "SR [95% ДИ]", "SPL", "SoftSPL", "Ср. расст., м", "Target detected"], extra)
    return out


def failure_table(d: dict):
    n = len(d["vlfm"])
    ref = d["vlfm"]
    cols = {}
    cols["VLFM, без шума (повтор)"] = _count([r["failure_cause"] for r in ref.values() if float(r["success"]) != 1.0], n)
    cols["VLFM, умеренный шум"] = _count([r["failure_cause"] for r in d["mod_v"].values()], n)
    cols["CAFS, умеренный шум"] = _count([r["failure_cause"] for r in d["mod_c"].values()], n)
    orc = {r["failure_cause"]: int(r["count"]) for r in d["oracle"]}
    cols["OracleFBE, без шума"] = dict(orc, __n=sum(orc.values()), __succ=n - sum(orc.values()))
    causes = sorted({c for col in cols.values() for c in col if not c.startswith("__")})
    rows = [[c] + [cols[k].get(c, 0) for k in cols] for c in causes]
    rows.append(["**успешных эпизодов**"] + [cols[k]["__succ"] for k in cols])
    rows.append(["**неудач всего**"] + [cols[k]["__n"] for k in cols])
    text = md_table(["Причина (метка логгера)"] + list(cols), rows)
    sv = set(ref) - set(d["mod_v"]); sc = set(ref) - set(d["mod_c"]); nom = {i for i, r in ref.items() if float(r["success"]) == 1.0}
    same = [i for i in set(d["mod_v"]) & set(d["mod_c"]) if d["mod_v"][i]["failure_cause"] == d["mod_c"][i]["failure_cause"]]
    text += (f"\n\nУмеренный шум: успехов VLFM {len(sv)}, CAFS {len(sc)}; общих успешных эпизодов {len(sv & sc)}; "
             f"из успехов VLFM были успешны и без шума {len(sv & nom)}. Метки причин совпали у {len(same)} из "
             f"{len(set(d['mod_v']) & set(d['mod_c']))} общих неудач.")
    return text, cols


def _count(causes, n):
    out: dict = {}
    for c in causes:
        out[c] = out.get(c, 0) + 1
    out["__n"] = len(causes)
    out["__succ"] = n - len(causes)
    return out


# ----------------------------------------------------------------------------- рисунки
def figures(d: dict, entries, cols, out: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"[рисунки пропущены: {e!r}]")
        return
    # 1. сравнение методов
    sel = [e for e in entries if "повтор" in e[0] or e[0].startswith(("Greedy", "CAFS", "OracleFBE"))]
    names = [e[0].split(",")[0].split(" (")[0] for e in sel]
    sr = np.array([e[2] / e[1] for e in sel]); ci = np.array([wilson(e[2], e[1]) for e in sel]); spl = [e[3] for e in sel]
    x = np.arange(len(sel)); fig, ax = plt.subplots(figsize=(7, 4)); w = 0.38
    ax.bar(x - w / 2, sr, w, yerr=[sr - ci[:, 0], ci[:, 1] - sr], capsize=3, label="SR (95% ДИ Уилсона)")
    ax.bar(x + w / 2, spl, w, label="SPL")
    ax.set_xticks(x); ax.set_xticklabels(names); ax.set_ylim(0, 1); ax.set_title("Методы на 50 эпизодах сцены 17DRP5sb8fy"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "fig_methods.png", dpi=150); plt.close(fig)
    # 2. деградация от шума
    lv = d["noise"]; xs = np.arange(len(lv)); srn = np.array([float(r["sr"]) for r in lv]); ks = [int(r["successes"]) for r in lv]
    cin = np.array([wilson(k, int(r["n"])) for k, r in zip(ks, lv)])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(xs, srn, yerr=[srn - cin[:, 0], cin[:, 1] - srn], marker="o", capsize=3, label="SR (95% ДИ)")
    ax.plot(xs, [float(r["spl"]) for r in lv], marker="s", label="SPL")
    ax.set_xticks(xs); ax.set_xticklabels([r["level"] for r in lv]); ax.set_ylim(0, 0.7)
    ax.set_xlabel("Уровень синтетического шума позы"); ax.set_title("Деградация VLFM при шуме локализации"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "fig_noise_degradation.png", dpi=150); plt.close(fig)
    # 3. причины неудач
    keys = list(cols); causes = sorted({c for col in cols.values() for c in col if not c.startswith("__")})
    fig, ax = plt.subplots(figsize=(8, 4)); bottom = np.zeros(len(keys))
    for c in causes:
        v = np.array([cols[k].get(c, 0) for k in keys]); ax.bar(range(len(keys)), v, bottom=bottom, label=c); bottom += v
    ax.set_xticks(range(len(keys))); ax.set_xticklabels([k.replace(", ", "\n") for k in keys], fontsize=8)
    ax.set_ylabel("число неудач"); ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1, 1)); ax.set_title("Причины неудач (метки логгера VLFM)")
    fig.tight_layout(); fig.savefig(out / "fig_failure_causes.png", dpi=150); plt.close(fig)


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=None, help="по умолчанию <root>/reports/final_report/tables")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    root = a.root.resolve(); out = (a.out or root / "reports/final_report/tables"); out.mkdir(parents=True, exist_ok=True)
    try:
        d = load(root)
    except FileNotFoundError as e:
        print(f"Не найден входной файл: {e.filename}\nЗапускайте из корня репозитория или укажите --root.", file=sys.stderr)
        return 2
    checks = check_ids(d)
    main_md, entries = main_table(d)
    fail_md, cols = failure_table(d)
    sections = {
        "main_results": ("Основные результаты", main_md),
        "paired_comparisons": ("Парные сравнения на одних и тех же 50 эпизодах", paired_table(d, a.boot)),
        "unpaired_comparisons": ("Сравнение с OracleFBE (независимые выборки)", unpaired_table(entries)),
        "noise": ("Чувствительность к шуму локализации", noise_table(d)),
        "failure_causes": ("Причины неудач", fail_md),
    }
    allmd = ["# Таблицы отчёта (генерируется scripts/make_tables.py)\n", "## Проверка согласованности ID\n", "\n".join(f"- {m}" for m in checks), ""]
    for key, (title, body) in sections.items():
        (out / f"{key}.md").write_text(body + "\n", encoding="utf-8")
        allmd += [f"## {title}\n", body, ""]
    (out / "ALL_TABLES.md").write_text("\n".join(allmd), encoding="utf-8")
    with open(out / "main_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["run", "n", "successes", "spl", "soft_spl", "mean_distance_m", "target_detected", "stop_called"])
        w.writerows(entries)
    if not a.no_figures:
        figures(d, entries, cols, out)
    print("\n".join(allmd)); print(f"\nФайлы записаны в {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

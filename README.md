# VLFM ObjectNav: репликация, шум локализации и CAFS

Эксперименты по методу **VLFM** (Vision-Language Frontier Maps, Yokoyama et al., ICRA 2024) в Habitat: воспроизведение базового
результата, сравнение с frontier-baseline, чувствительность к ошибкам оценки позы и проверка модификации CAFS.

> Этот репозиторий — **модифицированная копия** [rai-opensource/vlfm](https://github.com/rai-opensource/vlfm)
> (commit `584ed56008754fde7997d904983607def8328322`, лицензия и авторство оригинала сохранены).
> Оригинальный README: [`README_UPSTREAM.md`](README_UPSTREAM.md). Точный список изменений: [`CHANGES.md`](CHANGES.md);
> патч, применимый к оригиналу: [`reports/final_report/source_changes.patch`](reports/final_report/source_changes.patch).

**Отчёт:** [`reports/final_report/REPORT.md`](reports/final_report/REPORT.md) · **Инструкция воспроизведения:**
[`reports/final_report/REPRODUCIBILITY.md`](reports/final_report/REPRODUCIBILITY.md)

## Результаты (одна сцена MP3D `17DRP5sb8fy`, split train, 50 эпизодов на запуск)

| Запуск | SR [95% ДИ] | SPL | Комментарий |
|---|---|---|---|
| VLFM (три независимых запуска) | 0.46 / 0.48 / 0.48 | 0.280 / 0.298 / 0.297 | разброс между запусками 1–2 эпизода |
| Greedy frontier (ближайший frontier, без VLM) | 0.46 [0.33; 0.60] | 0.279 | от VLFM не отличим: Макнемар p = 1.0 |
| CAFS (штраф за низкую локальную уверенность) | 0.40 [0.28; 0.54] | 0.255 | хуже VLFM по SPL (ΔSPL −0.043, интервал не включает 0) |
| VLFM + шум позы: умеренный / сильный | 0.18 / 0.06 | 0.128 / 0.049 | неудачи «цель не обнаружена»: 3 → 27 из 41 |
| OracleFBE (исследование по данным симулятора) | 0.14 [0.07; 0.26] | 0.103 | аномально низкая доля обнаружений, см. отчёт |

Полные таблицы с доверительными интервалами и парными тестами: [`reports/final_report/tables/ALL_TABLES.md`](reports/final_report/tables/ALL_TABLES.md).

**Область применимости.** Это не оценка на validation-наборе HM3D/MP3D и не воспроизведение чисел статьи. Одна сцена и n = 50 дают
доверительный интервал SR около ±0.13. Не выполнено: ≥100 эпизодов HM3D val (доступ к данным не получен), среднее время шага,
малые уровни шума и разбор шума по компонентам, повторы по seed шума (инструмент для них готов, см. ниже).

## Что добавлено к оригиналу

* **Шум оценки позы** (`HabitatMixin._cache_observations`): белый шум + дрейф по x, y и курсу; seed привязан к эпизоду; симулятор получает истинную позу.
* **`GreedyFrontierPolicy`** — ближайший frontier по собственной карте политики, без семантики.
* **`HabitatITMPolicyV2ConfidenceAware`** (CAFS) — штраф `λ·(1 − confidence_local)` к ценности frontier.
* Скрипты запуска, анализа и построения таблиц (`scripts/`), результаты и отчёт (`reports/`).

## Структура

```
vlfm/                      исходный код VLFM + изменения (см. CHANGES.md)
scripts/
  reproduce_vlfm_50ep.sh   VLFM, 50 эпизодов
  reproduce_greedy_50ep.sh Greedy frontier, 50 эпизодов
  run_cafs_50ep.sh         CAFS без шума;  run_cafs_moderate_50ep.sh — CAFS при умеренном шуме
  run_noise_experiment.sh  политика × уровень шума, сохраняет построчные результаты   <- новое
  analyze_vlfm_episodes.py сводка по JSON эпизодов -> CSV
  make_tables.py           все таблицы и графики отчёта из CSV                        <- новое
  update_checksums.sh      пересчёт artifact_checksums.sha256 и video_checksums.sha256 <- новое
reports/
  final_report/            REPORT.md, REPRODUCIBILITY.md, source_changes.patch (полный), vlfm_episodes.csv, tables/,
                           videos/, extra_materials/ (видео, кадры, логи), source_snapshot/ (снимок версий и конфигурации от 22.10), *.sha256
  diagnostics/             парные CSV (VLFM/Greedy), причины неудач при умеренном шуме
  cafs_50ep_*/             результаты CAFS
  repro_snapshot_2026-10-22/  агрегаты основного прогона VLFM и OracleFBE
  reproduction/            environment.yml, requirements-freeze.txt
```

## Быстрый старт

Подробно — в [`REPRODUCIBILITY.md`](reports/final_report/REPRODUCIBILITY.md). Кратко (окружение `vlfm_habitat`, данные и веса на месте):

```bash
conda activate vlfm_habitat
bash scripts/launch_vlm_servers.sh          # в отдельном терминале, дождаться запуска серверов

bash scripts/reproduce_vlfm_50ep.sh         # VLFM
bash scripts/reproduce_greedy_50ep.sh       # Greedy frontier
bash scripts/run_cafs_50ep.sh               # CAFS

# шум локализации: уровень, политика (vlfm|cafs|greedy), число эпизодов
bash scripts/run_noise_experiment.sh moderate vlfm 50
bash scripts/run_noise_experiment.sh strong   vlfm 50
bash scripts/run_noise_experiment.sh small    vlfm 50     # новый малый уровень (ещё не запускался)
DRY_RUN=1 bash scripts/run_noise_experiment.sh strong cafs 20   # только показать команду

python scripts/make_tables.py               # перестроить таблицы и графики отчёта
```

Уровни шума: `nominal`, `small`, `moderate`, `strong`, а также `moderate_xy_only`, `moderate_yaw_only`,
`moderate_white_only`, `moderate_drift_only` (разбор по осям и по типу шума).

## Известные проблемы

* Построчные результаты основного прогона VLFM и прогонов шума nominal/moderate/strong не сохранены; в репозитории только агрегаты.
  Перезапуск через `run_noise_experiment.sh` закрывает пробел.
* Папка `reports/cafs_50ep_20261102_165339` содержит метрики, разобранные из имён видеофайлов, с SR 0.48 (как у VLFM, а не у CAFS, SR 0.40) — проверьте, что это за прогон, и при необходимости переименуйте.
* Видео, ключевые кадры, логи Hydra и tensorboard для 10 эпизодов лежат в `reports/final_report/extra_materials/` (и ещё два видео в `reports/final_report/videos/`). Эти каталоги перечислены в `.gitignore`, поэтому новые артефакты добавляйте через `git add -f`. После правок документов пересчитайте контрольные суммы: `bash scripts/update_checksums.sh`.
* Логи и конфигурации содержат абсолютные пути вида `/home/<пользователь>/...`, а имена tensorboard-файлов — имя машины; при желании их можно обезличить перед публикацией.

## Лицензия и ссылки

Лицензия оригинала (MIT, Boston Dynamics AI Institute) сохранена в `LICENSE`. Статья: Yokoyama et al., *VLFM: Vision-Language Frontier Maps
for Zero-Shot Semantic Navigation*, ICRA 2024, <https://arxiv.org/abs/2312.03275>.

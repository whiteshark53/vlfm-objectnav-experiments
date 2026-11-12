# Изменения относительно оригинального VLFM

Основа: [rai-opensource/vlfm](https://github.com/rai-opensource/vlfm), commit `584ed56008754fde7997d904983607def8328322`
(7 января 2025). Оригинальный README сохранён как [`README_UPSTREAM.md`](README_UPSTREAM.md).

Полный патч исходного кода лежит в [`reports/final_report/source_changes.patch`](reports/final_report/source_changes.patch).
Он проверен: применяется к чистому checkout указанного commit без ошибок и воспроизводит `vlfm/` и `.gitignore`
этого репозитория байт в байт (6 файлов, +200/−11 строк).

```bash
git clone https://github.com/rai-opensource/vlfm.git && cd vlfm
git checkout 584ed56008754fde7997d904983607def8328322
git apply /путь/к/reports/final_report/source_changes.patch
```

## 0. Два патча — какой чем является

| Файл | Что содержит |
|---|---|
| `reports/final_report/source_changes.patch` | **полный** патч относительно оригинала: совместимость, шум позы, Greedy, CAFS, `.gitignore` (проверен, см. выше) |
| `reports/final_report/source_snapshot/source_changes.patch` | снимок от 22 октября: только три правки совместимости (`weights_only=False`, тайм-аут 30 с, ветка HSSD); шум, Greedy и CAFS в него не входят |

Контрольная сумма второго файла в `artifact_checksums.sha256` не совпадала с самим файлом; `scripts/update_checksums.sh` пересчитывает суммы.

## 1. Изменения исходного кода (`vlfm/`)

| Файл | Что изменено | Тип |
|---|---|---|
| `vlfm/policy/utils/pointnav_policy.py` | `torch.load(..., weights_only=False)` в двух местах: в PyTorch ≥ 2.6 значение по умолчанию изменилось, и checkpoint PointNav с конфигурационными объектами не загружается | совместимость |
| `vlfm/vlm/server_wrapper.py` | тайм-аут HTTP-запроса к VLM-серверам 1 с → 30 с (на медленном окружении запросы обрывались) | совместимость; может влиять на завершение медленных запросов |
| `vlfm/policy/habitat_policies.py` | (а) параметры шума в `HabitatMixin.__init__`; (б) в `_cache_observations` поза `gps`/`compass` подменяется оценкой с шумом и дрейфом; (в) в `_reset` — свой seed на каждый эпизод, сброс дрейфа; (г) новые политики `GreedyFrontierPolicy` и `HabitatITMPolicyV2ConfidenceAware`; (д) ветка `hssd-hab` в `from_config` (только smoke-тест, в результатах не используется) | эксперименты |
| `vlfm/policy/base_objectnav_policy.py` | в `VLFMConfig` пять полей: `pose_noise_xy_std`, `pose_noise_yaw_std_deg`, `pose_drift_xy_std_per_step`, `pose_drift_yaw_std_deg_per_step`, `pose_noise_seed`; все по умолчанию 0 | эксперименты |
| `vlfm/policy/itm_policy.py` | класс `ConfidenceAwareITMPolicyV2` (CAFS) | эксперименты |
| `.gitignore` | исключены локальные данные, веса, видео и логи | служебное |

### 1.1. Шум позы (`habitat_policies.py`)

* Шум вносится **только** в позу, которую получают картографирование и планирование (`robot_xy`, `robot_heading`,
  `tf_camera_to_episodic`). Симулятор движет агента по истинной динамике, критерии success/SPL считает по истинной позе.
* Модель: независимый гауссов шум на каждом шаге по x, y и курсу плюс дрейф как случайное блуждание смещения
  (std за шаг задаётся отдельно); дрейф сбрасывается в начале эпизода.
* Seed шума = `pose_noise_seed + номер эпизода` → при одном `pose_noise_seed` разные политики получают одинаковые
  реализации шума на одних и тех же эпизодах (парное сравнение).
* При нулевых параметрах поведение совпадает с оригиналом: преобразование Habitat GPS в эпизодическую систему координат
  сохранено, курс compass лежит в [−π, π] и при нулевом шуме не меняется.
* Шум влияет также на вектор до цели для PointNav (он считается из оценки позы): агент «верит» оценке, а не истине.

### 1.2. `GreedyFrontierPolicy`

Выбирает ближайший по евклидову расстоянию frontier из **собственной карты препятствий политики**
(`compute_frontiers=True` по умолчанию) без семантической оценки; движение к цели и остальная часть конвейера
(обнаружение, карта объектов, остановка, PointNav) общие с VLFM. Это baseline по стратегии выбора frontier внутри одной
архитектуры, а не независимый геометрический агент.

### 1.3. `ConfidenceAwareITMPolicyV2` (CAFS)

`score = semantic_value − λ·(1 − confidence_local)`, λ = 0.15 (`confidence_penalty`); `confidence_local` — среднее
положительных значений карты уверенности value map в круге радиусом 0.5 м вокруг frontier. Это геометрическая
уверенность по проекции depth, а не неопределённость позы и не неопределённость VLM. Значение λ выбрано заранее и не
подбиралось. В лог пишутся смены лидирующего frontier (`CAFS_RANK_CHANGE`).
Результат: гипотеза «CAFS помогает» **не подтвердилась** (см. отчёт).

## 2. Добавленные файлы

| Файл | Назначение |
|---|---|
| `scripts/reproduce_vlfm_50ep.sh`, `reproduce_greedy_50ep.sh`, `run_cafs_50ep.sh`, `run_cafs_moderate_50ep.sh`, `test_cafs_2ep.sh` | запуски VLFM, greedy, CAFS (без шума и при умеренном шуме) и быстрый тест CAFS |
| **`scripts/run_noise_experiment.sh`** | параметризованный запуск «политика × уровень шума» с сохранением построчных результатов |
| `scripts/analyze_vlfm_episodes.py` | сводка по JSON эпизодов и экспорт в CSV |
| **`scripts/make_tables.py`** | строит все таблицы и графики отчёта из CSV |
| **`scripts/update_checksums.sh`** | пересчитывает `artifact_checksums.sha256` и `video_checksums.sha256` |
| `analyze_cafs_run.py`, `make_cafs_contact_sheets.py` | разбор прогона CAFS по именам видео и контактные листы (устаревший путь, см. `make_tables.py`) |
| `reports/**` | результаты, отчёт, инструкция воспроизведения, `source_changes.patch` |

## 3. Что в репозитории НЕ сохранено

(Видео, кадры и логи Hydra для 10 эпизодов сохранены в `reports/final_report/extra_materials/`.)

* Построчные результаты основного прогона VLFM (23/50) и прогонов шума nominal/moderate/strong: сохранены агрегаты
  (`reports/final_report/noise_aggregates.csv`, `reports/repro_snapshot_2026-10-22/vlfm_results.csv`). Для умеренного шума
  есть только списки неудач с метками причин.

Чтобы закрыть этот пробел, перезапустите прогоны через `scripts/run_noise_experiment.sh`: он сохраняет JSON и CSV по
каждому эпизоду, а `make_tables.py` сам подхватит их из `reports/noise/*/episodes.csv`.

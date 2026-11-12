# Инструкция воспроизведения

Область применимости: MP3D ObjectNav, сцена `17DRP5sb8fy`, split `train`, 50 эпизодов на запуск. Конфигурация промежуточной репликации;
она не гарантирует совпадения с числами статьи и побитового повторения (между запусками VLFM наблюдался разброс в 1–2 эпизода).

## 1. Код

```bash
git clone <этот репозиторий> && cd <каталог>
git rev-parse HEAD            # зафиксируйте commit в отчёте о запуске
```

Либо из оригинала с патчем (проверено: применяется к чистому commit без ошибок):

```bash
git clone https://github.com/rai-opensource/vlfm.git && cd vlfm
git checkout 584ed56008754fde7997d904983607def8328322
git apply /путь/к/reports/final_report/source_changes.patch
```

Содержание патча — в `CHANGES.md`. Среди прочего он включает `weights_only=False` в `torch.load` (PyTorch ≥ 2.6) и тайм-аут VLM-серверов 30 с.

## 2. Окружение

Использовалось: Ubuntu 22.04.5 (WSL2), Python 3.9.23, PyTorch 2.8.0+cu128, NumPy 1.26.4, OpenCV 4.5.5, Habitat-Sim 0.2.4,
habitat-lab / habitat-baselines 0.2.420230405, Gym 0.23.0, NVIDIA RTX 5060 Ti 16 ГБ. Полный список: `reports/reproduction/environment.yml`
и `reports/reproduction/requirements-freeze.txt`; снимок от 22 октября — `reports/final_report/source_snapshot/` (`pip_freeze.txt`, `conda_explicit.txt`, `git_commit.txt`, `git_status.txt`, конфигурация эксперимента, `model_checksums.sha256` для весов).

```bash
conda env create -f reports/reproduction/environment.yml   # имя окружения: vlfm_habitat
conda activate vlfm_habitat
```

GPU Blackwell (sm_120) требует PyTorch со сборкой cu128; версии из README оригинала на ней не работают. В WSL2 GPU-рендеринг Habitat (EGL) не
заработал, поэтому используется `habitat.simulator.habitat_sim_v0.gpu_device_id=-1` (программный рендеринг; на метрики влияния нет, время шага не сопоставимо с GPU).

## 3. Данные и веса

| Что | Куда | Откуда |
|---|---|---|
| MP3D ObjectNav v1 (эпизоды) | `data/datasets/objectnav/mp3d/v1/train/train.json.gz` | пакет ObjectNav для MP3D из Habitat |
| Сцена `17DRP5sb8fy` | `data/scene_datasets/` | сцена из набора `mp3d_example` (остальные сцены MP3D выдаёт Matterport по заявке) |
| PointNav | `data/pointnav_weights.pth` | входит в репозиторий оригинала |
| MobileSAM, GroundingDINO, YOLOv7 | `data/mobile_sam.pt`, `data/groundingdino_swint_ogc.pth`, `data/yolov7-e6e.pt` | по инструкции README оригинала (`README_UPSTREAM.md`) |
| Заглушка политики | `data/dummy_policy.pth` | `python -m vlfm.utils.generate_dummy_policy` |

HM3D в экспериментах не использовался (доступ не получен). Проверьте число эпизодов и наличие сцены перед запуском.

## 4. VLM-серверы

```bash
bash scripts/launch_vlm_servers.sh      # отдельный терминал; дождаться загрузки GroundingDINO, BLIP-2 ITM, MobileSAM, YOLOv7
```

## 5. Эксперименты

| Эксперимент | Команда |
|---|---|
| VLFM | `bash scripts/reproduce_vlfm_50ep.sh` |
| Greedy frontier | `bash scripts/reproduce_greedy_50ep.sh` |
| CAFS | `bash scripts/run_cafs_50ep.sh` |
| CAFS при умеренном шуме | `bash scripts/run_cafs_moderate_50ep.sh` |
| Шум: любой уровень × политика | `bash scripts/run_noise_experiment.sh LEVEL [vlfm\|cafs\|greedy] [N]` |

Общие параметры: `habitat.seed=100`, `iterator_options.shuffle=True`, `max_episode_steps=500`, `test_episode_count=50`; параметры шума:

| Уровень | σ xy, м | σ yaw, ° | дрейф xy, м/шаг | дрейф yaw, °/шаг |
|---|---|---|---|---|
| nominal | 0 | 0 | 0 | 0 |
| small (не запускался) | 0.02 | 0.5 | 0.001 | 0.02 |
| moderate | 0.10 | 3.0 | 0.005 | 0.1 |
| strong | 0.25 | 8.0 | 0.015 | 0.3 |

Базовый seed шума `pose_noise_seed = 20261029`; реальный seed эпизода = базовый + номер эпизода.

JSON по эпизодам пишутся в каталог из переменной `ZSOS_LOG_DIR` (`vlfm/utils/log_saver.py`); `run_noise_experiment.sh` задаёт её сам,
для остальных скриптов задайте вручную: `export ZSOS_LOG_DIR=reports/<прогон>/episodes`. Сводка:
`python scripts/analyze_vlfm_episodes.py <каталог с JSON> --out episodes.csv`.

## 6. Проверка результатов и таблицы

```bash
python scripts/make_tables.py
```

Скрипт проверяет совпадение наборов episode ID между прогонами (парность), считает доверительные интервалы Уилсона, точный критерий
Макнемара (парные эпизоды), критерий Фишера (независимые выборки), бутстрап-интервалы для разности SPL и записывает таблицы и рисунки в
`reports/final_report/tables/`. Если есть `reports/noise/*/episodes.csv` (результат `run_noise_experiment.sh`), они добавляются в таблицу шума.

## 7. Что нельзя воспроизвести из репозитория без перезапуска

Построчные данные основного прогона VLFM и шумовых прогонов nominal/moderate/strong (сохранены только агрегаты и списки неудач при умеренном шуме). Среднее время шага не измерялось.

Сохранены: видео, кадры на 25 / 50 / 75 %, логи Hydra и tensorboard для 10 эпизодов — `reports/final_report/extra_materials/`; видео эпизодов 20409 и 37246 — `reports/final_report/videos/`.

## 8. Контрольные суммы

```bash
bash scripts/update_checksums.sh --check   # проверить artifact_checksums.sha256 и video_checksums.sha256
bash scripts/update_checksums.sh           # пересчитать после правок документов
```

Веса моделей проверяются по `reports/final_report/source_snapshot/model_checksums.sha256` (запускать `sha256sum -c` из корня репозитория, веса должны лежать в `data/`).

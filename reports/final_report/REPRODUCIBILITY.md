# VLFM ObjectNav: инструкция воспроизведения

## 1. Область применимости

Инструкция описывает подготовку и повтор диагностического эксперимента VLFM на MP3D ObjectNav:
- сцена `17DRP5sb8fy`;
- split `train`;
- 50 эпизодов;
- политика `HabitatITMPolicyV2`.

Это конфигурация промежуточного воспроизведения. Она не гарантирует совпадение результатов с оригинальной статьёй или точное повторение исторического порядка эпизодов.

## 2. Репозиторий

```bash
git clone https://github.com/rai-opensource/vlfm.git
cd vlfm
git checkout 584ed56008754fde7997d904983607def8328322
```

Если репозиторий уже подготовлен, проверь ревизию:

```bash
git rev-parse HEAD
git status --short
```

В текущем экспериментальном окружении использовались локальные изменения:
- `torch.load(..., weights_only=False)` в `vlfm/policy/utils/pointnav_policy.py`;
- HTTP timeout 30 секунд в `vlfm/vlm/server_wrapper.py`.

Перед повторным запуском необходимо убедиться, что эти изменения присутствуют, если они требуются установленными версиями библиотек и VLM-серверов.

## 3. Программное окружение

Использованное окружение:

```text
Environment: vlfm_habitat
Python: 3.9.23
PyTorch: 2.8.0+cu128
NumPy: 1.26.4
OpenCV: 4.5.5
Habitat-Sim: 0.2.4
Habitat-Lab: 0.2.4
Habitat-Baselines: 0.2.4
Gym: 0.23.0
```

Активировать окружение:

```bash
conda activate vlfm_habitat
```

Проверить версии и CUDA:

```bash
python - <<'PY'
import sys
import torch
import numpy
import cv2
import habitat_sim

print("Python:", sys.version)
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("NumPy:", numpy.__version__)
print("OpenCV:", cv2.__version__)
print("Habitat-Sim:", habitat_sim.__version__)
PY
```

Для фиксации фактического окружения:

```bash
mkdir -p reports/final_report
python -m pip freeze > reports/final_report/pip_freeze.txt
conda list --explicit > reports/final_report/conda_explicit.txt
```

## 4. Данные и веса

Ожидаемый путь к MP3D ObjectNav:

```text
data/datasets/objectnav/mp3d/v1/train/train.json.gz
```

Каталог сцен:

```text
data/scene_datasets/
```

В конфигурации используется сцена:

```text
17DRP5sb8fy
```

Также необходимы веса и компоненты, используемые политикой и VLM-серверами. В текущей установке применялись PointNav, GroundingDINO, MobileSAM, YOLOv7 и BLIP2 ITM компоненты.

Проверь наличие основных файлов и каталогов в соответствии с путями, заданными в `scripts/launch_vlm_servers.sh` и конфигурации проекта. Конкретные пути к весам могут отличаться в зависимости от способа подготовки данных.

HM3D в данном эксперименте не использовался: доступ к необходимым данным Matterport был ограничен.

## 5. Запуск VLM-серверов

В отдельном терминале из корня репозитория:

```bash
conda activate vlfm_habitat
cd ~/vlfm
bash scripts/launch_vlm_servers.sh
```

Дождись запуска серверов и проверь сообщения об ошибках в их логах. Скрипт запускает VLM-компоненты, необходимые политике. Перед evaluation они должны быть доступны.

Не запускай evaluation, если серверы не поднялись или не найдены необходимые веса.

## 6. Запуск оценки на 50 эпизодах

В другом терминале:

```bash
conda activate vlfm_habitat
cd ~/vlfm
bash scripts/reproduce_vlfm_50ep.sh
```

Сценарий:
- создаёт отдельный каталог результатов с временной меткой;
- сохраняет сведения об окружении;
- запускает `vlfm.run`;
- сохраняет stdout/stderr в `run.log`;
- записывает видео эпизодов.

Используемые ключевые параметры:

```text
benchmark/nav/objectnav=objectnav_mp3d
split=train
content_scenes=[17DRP5sb8fy]
gpu_device_id=-1
seed=100
max_episode_steps=500
iterator_options.shuffle=True
evaluate=True
should_load_ckpt=False
policy=HabitatITMPolicyV2
turn_angle=30
num_environments=1
test_episode_count=50
video_option=[disk]
```

Обрати внимание: `should_load_ckpt=False`. Обученный PPO checkpoint не загружается. Dummy policy path используется только как параметр конфигурации evaluation.

## 7. Анализ результатов

После завершения evaluation найди каталог `episodes` с JSON-файлами. Передай его анализатору:

```bash
python scripts/analyze_vlfm_episodes.py \
  reports/diagnostics/vlfm_50ep_rerun/episodes \
  --out reports/final_report/vlfm_episodes.csv
```

Для нового запуска подставь фактический путь к его каталогу `episodes`.

Анализатор:
- считает число JSON-файлов;
- проверяет уникальность `episode_id`;
- рассчитывает SR, средние Success, SPL, SoftSPL и distance to goal;
- считает частоты `failure_cause`;
- выводит список неуспешных эпизодов;
- сохраняет CSV.

## 8. Проверка видеопримеров

В текущий комплект включены:

```text
videos/episode=20409-...mp4
videos/episode=37246-...mp4
```

Контрольные суммы:

```bash
cd reports/final_report
sha256sum -c video_checksums.sha256
```

Если видео заменялись или копировались заново, обнови файл контрольных сумм:

```bash
sha256sum videos/*.mp4 > video_checksums.sha256
```

## 9. Ограничения воспроизводимости

- Результат зависит от версий Habitat, PyTorch, VLM-моделей и их весов.
- Для полного повторения необходимо сохранять все используемые веса и конфигурационные файлы.
- Seed и shuffle сами по себе не доказывают, что два запуска обработали одинаковые episode ID в одинаковом порядке.
- Текущая конфигурация использует одну MP3D-сцену и split `train`.
- Software rendering отличается от полноценного GPU rendering.
- Запуск без обученного PPO checkpoint не эквивалентен оценке обученной политики из оригинальной статьи.
- HM3D в текущем эксперименте не использовался.

Для строгого воспроизведения рекомендуется дополнительно архивировать:
1. полный Git diff;
2. `pip freeze` и `conda list --explicit`;
3. YAML-конфигурацию и CLI-команду;
4. версии и SHA-256 всех весов;
5. точный список episode ID;
6. логи VLM-серверов и evaluation;
7. результаты на нескольких сценах и независимых seed.

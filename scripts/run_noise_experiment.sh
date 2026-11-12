#!/usr/bin/env bash
# Параметризованный эксперимент «шум локализации»: любая политика × любой уровень шума.
#
#   bash scripts/run_noise_experiment.sh LEVEL [POLICY] [N_EPISODES]
#
#   LEVEL   nominal | small | moderate | strong                       (основные уровни)
#           moderate_xy_only | moderate_yaw_only                      (разбор по осям)
#           moderate_white_only | moderate_drift_only                 (разбор по типу шума)
#   POLICY  vlfm (по умолчанию) | cafs | greedy | имя класса политики
#   N       число эпизодов (по умолчанию 50)
#
# Переменные окружения: NOISE_SEED (20261029), SEED (100, seed Habitat), SCENE (17DRP5sb8fy),
#                       GPU_DEVICE_ID (-1 = программный рендеринг), VIDEO (0|1), DRY_RUN (1 = только напечатать команду).
#
# Результат: reports/noise/<policy>_<level>_n<N>_seed<NOISE_SEED>_<время>/
#   environment.txt  параметры и версии      run.log     полный вывод
#   episodes/        JSON по эпизодам        episodes.csv, analysis.txt  таблица и сводка
# Все построчные результаты подхватывает scripts/make_tables.py (reports/noise/*/episodes.csv).
#
# Уровни moderate и strong совпадают с использованными в отчёте; small и разбор по осям/типам — новые (ещё не запускались).
set -Eeuo pipefail
cd "$(dirname "$0")/.."

LEVEL="${1:?Укажите уровень: nominal | small | moderate | strong | moderate_xy_only | moderate_yaw_only | moderate_white_only | moderate_drift_only}"
POLICY_ARG="${2:-vlfm}"
N="${3:-50}"
NOISE_SEED="${NOISE_SEED:-20261029}"
SEED="${SEED:-100}"
SCENE="${SCENE:-17DRP5sb8fy}"
GPU_DEVICE_ID="${GPU_DEVICE_ID:--1}"
VIDEO="${VIDEO:-0}"
DRY_RUN="${DRY_RUN:-0}"

#             xy white (m)  yaw white (deg)  xy drift (m/step)  yaw drift (deg/step)
case "$LEVEL" in
  nominal)             XY=0.0   YAW=0.0  DXY=0.0    DYAW=0.0  ;;
  small)               XY=0.02  YAW=0.5  DXY=0.001  DYAW=0.02 ;;
  moderate)            XY=0.10  YAW=3.0  DXY=0.005  DYAW=0.1  ;;
  strong)              XY=0.25  YAW=8.0  DXY=0.015  DYAW=0.3  ;;
  moderate_xy_only)    XY=0.10  YAW=0.0  DXY=0.005  DYAW=0.0  ;;
  moderate_yaw_only)   XY=0.0   YAW=3.0  DXY=0.0    DYAW=0.1  ;;
  moderate_white_only) XY=0.10  YAW=3.0  DXY=0.0    DYAW=0.0  ;;
  moderate_drift_only) XY=0.0   YAW=0.0  DXY=0.005  DYAW=0.1  ;;
  *) echo "Неизвестный уровень: $LEVEL" >&2; exit 2 ;;
esac

case "$POLICY_ARG" in
  vlfm)   POLICY=HabitatITMPolicyV2 ;;
  cafs)   POLICY=HabitatITMPolicyV2ConfidenceAware ;;
  greedy) POLICY=GreedyFrontierPolicy ;;
  *)      POLICY="$POLICY_ARG"; POLICY_ARG=$(echo "$POLICY_ARG" | tr -c 'A-Za-z0-9\n' '_') ;;
esac

if [[ "${CONDA_DEFAULT_ENV:-}" != "vlfm_habitat" ]]; then
  echo "Предупреждение: ожидалось окружение vlfm_habitat, активно: ${CONDA_DEFAULT_ENV:-нет}" >&2
fi

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="reports/noise/${POLICY_ARG}_${LEVEL}_n${N}_seed${NOISE_SEED}_${STAMP}"
if [[ "$VIDEO" == "1" ]]; then VIDEO_OPT='habitat_baselines.eval.video_option=["disk"]'; else VIDEO_OPT='habitat_baselines.eval.video_option=[]'; fi

CMD=(python -um vlfm.run
  benchmark/nav/objectnav=objectnav_mp3d
  'habitat.dataset.data_path="data/datasets/objectnav/mp3d/v1/{split}/{split}.json.gz"'
  habitat.dataset.split=train
  "habitat.dataset.content_scenes=[${SCENE}]"
  habitat.dataset.scenes_dir=data/scene_datasets
  "habitat.simulator.habitat_sim_v0.gpu_device_id=${GPU_DEVICE_ID}"
  "habitat.seed=${SEED}"
  habitat.environment.max_episode_steps=500
  habitat.environment.iterator_options.shuffle=True
  habitat_baselines.evaluate=True
  habitat_baselines.eval.split=train
  habitat_baselines.eval_ckpt_path_dir=data/dummy_policy.pth
  habitat_baselines.eval.should_load_ckpt=False
  habitat_baselines.load_resume_state_config=False
  "habitat_baselines.rl.policy.name=${POLICY}"
  "habitat_baselines.rl.policy.pose_noise_xy_std=${XY}"
  "habitat_baselines.rl.policy.pose_noise_yaw_std_deg=${YAW}"
  "habitat_baselines.rl.policy.pose_drift_xy_std_per_step=${DXY}"
  "habitat_baselines.rl.policy.pose_drift_yaw_std_deg_per_step=${DYAW}"
  "habitat_baselines.rl.policy.pose_noise_seed=${NOISE_SEED}"
  habitat.task.lab_sensors.base_explorer.turn_angle=30
  habitat_baselines.num_environments=1
  "habitat_baselines.test_episode_count=${N}"
  "$VIDEO_OPT")

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Каталог результатов: $OUT"
  echo "ZSOS_LOG_DIR=$OUT/episodes"
  printf '%q ' "${CMD[@]}"; echo
  exit 0
fi

mkdir -p "$OUT/episodes"
{
  echo "Date: $(date -Is)"
  echo "Git commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "Policy: ${POLICY}"
  echo "Level: ${LEVEL}"
  echo "Episodes: ${N}"
  echo "Dataset: MP3D train / ${SCENE}"
  echo "habitat.seed: ${SEED}"
  echo "pose_noise_xy_std (m): ${XY}"
  echo "pose_noise_yaw_std_deg: ${YAW}"
  echo "pose_drift_xy_std_per_step (m): ${DXY}"
  echo "pose_drift_yaw_std_deg_per_step: ${DYAW}"
  echo "pose_noise_seed: ${NOISE_SEED}"
  echo "gpu_device_id: ${GPU_DEVICE_ID}"
  python --version
  python -c "import torch, numpy, cv2; print('torch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print('numpy:', numpy.__version__); print('opencv:', cv2.__version__)"
} > "$OUT/environment.txt" 2>&1

echo "Каталог результатов: $OUT"
echo "Запуск: policy=${POLICY} level=${LEVEL} N=${N}"
export ZSOS_LOG_DIR="$OUT/episodes"          # по эпизодам пишет JSON (vlfm/utils/log_saver.py)
"${CMD[@]}" 2>&1 | tee "$OUT/run.log"

python scripts/analyze_vlfm_episodes.py "$OUT/episodes" --out "$OUT/episodes.csv" | tee "$OUT/analysis.txt"
echo "Готово: $OUT. Таблицы отчёта: python scripts/make_tables.py"

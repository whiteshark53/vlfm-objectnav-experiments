#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

if [[ "${CONDA_DEFAULT_ENV:-}" != "vlfm_habitat" ]]; then
    echo "Expected vlfm_habitat; current: ${CONDA_DEFAULT_ENV:-none}"
    exit 1
fi

STAMP=$(date +%Y%m%d_%H%M%S)
OUT="reports/cafs_moderate_50ep_${STAMP}"
VIDEO_DIR="$OUT/videos"

mkdir -p "$VIDEO_DIR"

{
    echo "Date: $(date -Is)"
    echo "Git commit: $(git rev-parse HEAD)"
    echo "Conda environment: $CONDA_DEFAULT_ENV"
    echo "Policy: HabitatITMPolicyV2ConfidenceAware"
    echo "Episodes: 50"
    echo "Dataset: MP3D train / 17DRP5sb8fy"
    echo "Pose noise: moderate"
    echo "pose_noise_xy_std: 0.1"
    echo "pose_noise_yaw_std_deg: 3.0"
    echo "pose_drift_xy_std_per_step: 0.005"
    echo "pose_drift_yaw_std_deg_per_step: 0.1"
    echo "pose_noise_seed: 20261029"
    python --version
    python -c "import torch, numpy, cv2; print('torch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print('numpy:', numpy.__version__); print('opencv:', cv2.__version__)"
} > "$OUT/environment.txt"

echo "Output directory: $OUT"
echo "Starting CAFS moderate-noise evaluation..."

python -um vlfm.run \
  benchmark/nav/objectnav=objectnav_mp3d \
  'habitat.dataset.data_path="data/datasets/objectnav/mp3d/v1/{split}/{split}.json.gz"' \
  habitat.dataset.split=train \
  'habitat.dataset.content_scenes=[17DRP5sb8fy]' \
  habitat.dataset.scenes_dir=data/scene_datasets \
  habitat.simulator.habitat_sim_v0.gpu_device_id=-1 \
  habitat.seed=100 \
  habitat.environment.max_episode_steps=500 \
  habitat.environment.iterator_options.shuffle=True \
  habitat_baselines.evaluate=True \
  habitat_baselines.eval.split=train \
  habitat_baselines.eval_ckpt_path_dir=data/dummy_policy.pth \
  habitat_baselines.eval.should_load_ckpt=False \
  habitat_baselines.load_resume_state_config=False \
  habitat_baselines.rl.policy.name=HabitatITMPolicyV2ConfidenceAware \
  habitat_baselines.rl.policy.pose_noise_xy_std=0.1 \
  habitat_baselines.rl.policy.pose_noise_yaw_std_deg=3.0 \
  habitat_baselines.rl.policy.pose_drift_xy_std_per_step=0.005 \
  habitat_baselines.rl.policy.pose_drift_yaw_std_deg_per_step=0.1 \
  habitat_baselines.rl.policy.pose_noise_seed=20261029 \
  habitat.task.lab_sensors.base_explorer.turn_angle=30 \
  habitat_baselines.num_environments=1 \
  habitat_baselines.test_episode_count=50 \
  'habitat_baselines.eval.video_option=["disk"]' \
  "habitat_baselines.video_dir=$VIDEO_DIR" \
  2>&1 | tee "$OUT/run.log"

echo
echo "Evaluation finished: $OUT"
echo "Videos: $VIDEO_DIR"

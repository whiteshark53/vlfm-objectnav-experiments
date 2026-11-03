from pathlib import Path
import cv2
import math

video_dir = Path("reports/cafs_50ep_20261102_165339/videos")
out_dir = Path("reports/cafs_50ep_20261102_165339/contact_sheets")
out_dir.mkdir(parents=True, exist_ok=True)

videos = sorted(video_dir.glob("*.mp4"))
if not videos:
    raise SystemExit(f"No MP4 files found in {video_dir}")

cols = 4
thumb_w, thumb_h = 320, 220
frames_per_video = 4
batch_size = 12

def get_frames(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        print(f"Cannot open: {path.name}")
        return []

    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []

    if count <= 0:
        cap.release()
        return []

    for i in range(frames_per_video):
        frame_idx = round(i * (count - 1) / max(1, frames_per_video - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if ok:
            frame = cv2.resize(frame, (thumb_w, thumb_h))
            frames.append(frame)

    cap.release()
    return frames

for batch_start in range(0, len(videos), batch_size):
    batch = videos[batch_start:batch_start + batch_size]
    tiles = []

    for path in batch:
        frames = get_frames(path)
        if not frames:
            continue

        # Четыре кадра одного эпизода в одну строку
        strip = cv2.hconcat(frames)
        label = path.name[:110]
        canvas = cv2.copyMakeBorder(
            strip, 35, 0, 0, 0,
            cv2.BORDER_CONSTANT, value=(35, 35, 35)
        )
        cv2.putText(
            canvas, label, (8, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (255, 255, 255), 1, cv2.LINE_AA
        )
        tiles.append(canvas)

    if not tiles:
        continue

    rows = []
    for i in range(0, len(tiles), 2):
        row_tiles = tiles[i:i + 2]
        if len(row_tiles) == 1:
            blank = row_tiles[0].copy()
            blank[:] = 0
            row_tiles.append(blank)
        rows.append(cv2.hconcat(row_tiles))

    sheet = cv2.vconcat(rows)
    out_path = out_dir / f"contact_{batch_start // batch_size + 1:02d}.jpg"
    cv2.imwrite(str(out_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(out_path)

print(f"\nVideos: {len(videos)}")
print(f"Contact sheets: {out_dir}")

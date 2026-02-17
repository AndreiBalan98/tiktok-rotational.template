import math
import time
import subprocess
import pygame  # type: ignore
import random

# ==========================================================
# CONFIGURARE GLOBALĂ
# ==========================================================

CW, CH = 1080, 1920
FPS = 60

BG_COLOR = (255, 255, 255)

BALL_COLORS_HEX = ["80ffe8", "83bcff", "97d2fb", "e1eff6", "eccbd9"]
BALL_COLORS = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in BALL_COLORS_HEX]

RADIUS = 50

SPAWN_FREQUENCY = 300.0  # bile / secundă
START_ANGLE_DEG = 0.0
ANGLE_STEP_DEG = 32.0
LAUNCH_SPEED = 750.0
CULL_MARGIN = 800  # px

# Video output
RECORD_VIDEO = True
OUTPUT_MP4 = "output.mp4"
FFMPEG_PATH = "ffmpeg"  # sau r"C:\path\to\ffmpeg.exe"

# ==========================================================


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "color")

    def __init__(self, x, y, vx, vy, color):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color


def start_ffmpeg_recording():
    # Primește RGB24 raw frames (CW x CH) la FPS și produce MP4 (H.264)
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{CW}x{CH}",
        "-r", str(FPS),
        "-i", "-",                # stdin
        "-an",                    # fără audio
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",    # compatibil TikTok
        "-crf", "18",
        "-preset", "veryfast",
        OUTPUT_MP4,
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main():
    pygame.init()

    info = pygame.display.Info()
    scale = min((info.current_w * 0.92) / CW, (info.current_h * 0.92) / CH)
    win_w, win_h = max(320, int(CW * scale)), max(568, int(CH * scale))

    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("Ball Generator (Recording via FFmpeg)")
    clock = pygame.time.Clock()

    canvas = pygame.Surface((CW, CH)).convert()

    balls = []
    spawn_acc = 0.0
    angle_deg = START_ANGLE_DEG
    cx, cy = CW * 0.5, CH * 0.5

    left, right = -CULL_MARGIN, CW + CULL_MARGIN
    top, bottom = -CULL_MARGIN, CH + CULL_MARGIN

    ff = start_ffmpeg_recording() if RECORD_VIDEO else None

    def spawn_one():
        nonlocal angle_deg
        ang = math.radians(angle_deg)
        vx = math.cos(ang) * LAUNCH_SPEED
        vy = math.sin(ang) * LAUNCH_SPEED
        balls.append(Ball(cx, cy, vx, vy, random.choice(BALL_COLORS)))

        angle_deg += ANGLE_STEP_DEG
        if abs(angle_deg) >= 360.0:
            angle_deg = math.fmod(angle_deg, 360.0)

    running = True
    try:
        while running:
            frame_dt = clock.tick(FPS) / 1000.0

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key == pygame.K_r:
                        balls.clear()

            generating = pygame.key.get_pressed()[pygame.K_SPACE]

            if generating:
                spawn_acc += SPAWN_FREQUENCY * frame_dt
                n = int(spawn_acc)
                if n:
                    for _ in range(n):
                        spawn_one()
                    spawn_acc -= n
            else:
                spawn_acc = 0.0

            kept = []
            for b in balls:
                b.x += b.vx * frame_dt
                b.y += b.vy * frame_dt
                if left <= b.x <= right and top <= b.y <= bottom:
                    kept.append(b)
            balls = kept

            # render
            canvas.fill(BG_COLOR)
            for b in balls:
                pygame.draw.circle(canvas, b.color, (int(b.x), int(b.y)), RADIUS)

            # afișare (scalată)
            scaled = pygame.transform.smoothscale(canvas, screen.get_size())
            screen.blit(scaled, (0, 0))
            pygame.display.flip()

            # RECORD: trimite cadrul ORIGINAL (CW x CH) către ffmpeg
            if ff and ff.stdin:
                frame_bytes = pygame.image.tostring(canvas, "RGB")
                ff.stdin.write(frame_bytes)

    finally:
        pygame.quit()
        if ff and ff.stdin:
            try:
                ff.stdin.close()
            except Exception:
                pass
            ff.wait()


if __name__ == "__main__":
    main()

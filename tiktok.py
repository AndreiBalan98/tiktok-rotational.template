import math
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

# Parametri generare bile
SPAWN_FREQUENCY = 300.0  # bile / secundă (folosit în modul continuu)
START_ANGLE_DEG = 0.0

# NOTĂ: ANGLE_STEP_DEG trebuie să dividă 360 exact pentru ca 3 rotații să fie precise.
# Valori valide: 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 18, 20, 24, 30, 36, 40, 45, 60, 72, 90
ANGLE_STEP_DEG = 30.0   # 30° → 12 bile per rotație completă → 36 bile per burst

LAUNCH_SPEED = 750.0
CULL_MARGIN = 800  # px

# ==========================================================
# SETĂRI SIMULARE AUTOMATĂ
# ==========================================================

BPM = 120.0           # Bătăi pe minut; în exact acest ritm se simulează apăsarea space

BURST_COUNT = 4       # N: de câte ori se simulează apăsarea space (fiecare = 3 rotații complete)

CONTINUOUS_BEATS = 8  # M: câte bătăi de generare continuă după cele N burst-uri

SILENCE_BEATS = 4     # P: câte bătăi de liniște (fără generare) după modul continuu

# Calculat automat — 3 rotații complete exacte (3 × 360°) per burst
BURST_ROTATIONS = 3
BALLS_PER_BURST = round(BURST_ROTATIONS * 360.0 / ANGLE_STEP_DEG)
# Exemplu cu ANGLE_STEP_DEG=30: 3 × 360 / 30 = 36 bile per burst

# ==========================================================
# VIDEO OUTPUT
# ==========================================================

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
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{CW}x{CH}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
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

    # --- State machine simulare automată ---
    # Faze: "burst" → "continuous" → "silence" → "done"
    beat_interval = 60.0 / BPM   # secunde per bătaie
    phase = "burst"
    time_acc = 0.0               # timp acumulat în faza curentă
    bursts_done = 0              # câte burst-uri s-au executat

    def spawn_one():
        nonlocal angle_deg
        ang = math.radians(angle_deg)
        vx = math.cos(ang) * LAUNCH_SPEED
        vy = math.sin(ang) * LAUNCH_SPEED
        balls.append(Ball(cx, cy, vx, vy, random.choice(BALL_COLORS)))
        angle_deg = (angle_deg + ANGLE_STEP_DEG) % 360.0

    def do_burst():
        """Simulează o apăsare de space: spawnează exact BALLS_PER_BURST bile (3 rotații complete)."""
        for _ in range(BALLS_PER_BURST):
            spawn_one()

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

            # --- Logica simulare automată ---

            if phase == "burst":
                time_acc += frame_dt
                # Declanșează burst la fiecare bătaie exactă (BPM precis)
                while time_acc >= beat_interval and bursts_done < BURST_COUNT:
                    time_acc -= beat_interval
                    do_burst()
                    bursts_done += 1
                if bursts_done >= BURST_COUNT:
                    phase = "continuous"
                    time_acc = 0.0
                    spawn_acc = 0.0

            elif phase == "continuous":
                # Generare continuă timp de CONTINUOUS_BEATS bătăi (space ținut apăsat)
                time_acc += frame_dt
                continuous_duration = CONTINUOUS_BEATS * beat_interval
                if time_acc < continuous_duration:
                    spawn_acc += SPAWN_FREQUENCY * frame_dt
                    n = int(spawn_acc)
                    if n:
                        for _ in range(n):
                            spawn_one()
                        spawn_acc -= n
                else:
                    phase = "silence"
                    time_acc = 0.0
                    spawn_acc = 0.0

            elif phase == "silence":
                # Liniște: nicio generare timp de SILENCE_BEATS bătăi
                time_acc += frame_dt
                if time_acc >= SILENCE_BEATS * beat_interval:
                    phase = "done"

            # phase == "done": nu se mai generează bile

            # --- Fizică bile ---
            kept = []
            for b in balls:
                b.x += b.vx * frame_dt
                b.y += b.vy * frame_dt
                if left <= b.x <= right and top <= b.y <= bottom:
                    kept.append(b)
            balls = kept

            # --- Render ---
            canvas.fill(BG_COLOR)
            for b in balls:
                pygame.draw.circle(canvas, b.color, (int(b.x), int(b.y)), RADIUS)

            scaled = pygame.transform.smoothscale(canvas, screen.get_size())
            screen.blit(scaled, (0, 0))
            pygame.display.flip()

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

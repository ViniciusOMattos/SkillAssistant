from config import *
from targets import TargetManager
from target_predictor import TargetClamper
import cv2
import numpy as np
import mss
import time


class MultiTargetDetector:
    def __init__(self):
        self.target_manager = TargetManager()
        self.active_target_id = 1

        self.sct = mss.mss()
        mon = self.sct.monitors[1]
        self.region = {
            "left": int((mon["width"] - CAPTURE_WIDTH) / 2),
            "top": int((mon["height"] - CAPTURE_HEIGHT) / 2),
            "width": CAPTURE_WIDTH,
            "height": CAPTURE_HEIGHT,
        }

        self.detections = []
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.clamper = TargetClamper()
        self.clamped_pos = None
        self.raw_target_pos = None
        self.needs_reload = False

    def get_active_target(self):
        return self.target_manager.get(self.active_target_id)

    def reload_if_needed(self):
        if self.needs_reload:
            for tid in self.target_manager.get_all():
                self.target_manager.reload(tid)
            self.needs_reload = False
            print(f"All targets reloaded")

    def capture(self):
        img = np.array(self.sct.grab(self.region))
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        all_detections = []

        for target_id, target in self.target_manager.get_all().items():
            mask = cv2.inRange(hsv, target.lower_hsv, target.upper_hsv)
            resized = cv2.resize(
                target.template_gray, (target.scaled_w, target.scaled_h)
            )
            result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= target.template_threshold)

            for pt in zip(*locations[::-1]):
                x, y = pt
                roi_mask = mask[y : y + target.scaled_h, x : x + target.scaled_w]
                color_pixels = cv2.countNonZero(roi_mask)
                color_ratio = color_pixels / (target.scaled_w * target.scaled_h)
                score = result[y, x]

                if color_ratio >= target.color_threshold:
                    all_detections.append(
                        {
                            "x": x,
                            "y": y,
                            "w": target.scaled_w,
                            "h": target.scaled_h,
                            "score": score,
                            "color_ratio": color_ratio,
                            "target_id": target_id,
                        }
                    )

        self.detections = self._filter_overlapping(all_detections)

        center_x = PLAYER_OFFSET_X
        center_y = PLAYER_OFFSET_Y
        for det in self.detections:
            target_cx = det["x"] + det["w"] // 2 + TARGET_OFFSET_X
            target_cy = det["y"] + det["h"] // 2 + TARGET_OFFSET_Y
            det["dist_to_center"] = np.sqrt(
                (target_cx - center_x) ** 2 + (target_cy - center_y) ** 2
            )

        self.detections.sort(key=lambda d: d["dist_to_center"])

    def _filter_overlapping(self, detections):
        if not detections:
            return []
        filtered = []
        for det in detections:
            is_dup = any(
                abs(det["x"] - d["x"]) < 30 and abs(det["y"] - d["y"]) < 30
                for d in filtered
            )
            if not is_dup:
                filtered.append(det)
        return filtered

    def get_closest_target_pos(self):
        return self.clamped_pos

    def get_raw_target_pos(self):
        return self.raw_target_pos

    def draw(self, frame):
        out = frame.copy()

        player_cx = PLAYER_OFFSET_X
        player_cy = PLAYER_OFFSET_Y
        cv2.circle(out, (player_cx, player_cy), 10, (255, 255, 255), 3)
        cv2.line(
            out,
            (player_cx - 20, player_cy),
            (player_cx + 20, player_cy),
            (255, 255, 255),
            2,
        )
        cv2.line(
            out,
            (player_cx, player_cy - 20),
            (player_cx, player_cy + 20),
            (255, 255, 255),
            2,
        )
        cv2.circle(out, (player_cx, player_cy), ATTACK_RANGE, (100, 100, 255), 2)

        target_colors = {
            1: (0, 255, 0),
            2: (255, 100, 100),
            3: (100, 100, 255),
            4: (255, 255, 100),
        }

        for i, det in enumerate(self.detections):
            x, y, w, h = det["x"], det["y"], det["w"], det["h"]
            tid = det["target_id"]
            color = target_colors.get(tid, (0, 200, 0))

            if i == 0:
                thickness = 4
            else:
                thickness = 2

            cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
            cv2.circle(out, (x + w // 2, y + h // 2), 8, color, -1)
            cv2.putText(
                out, f"T{tid}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )

            if i == 0:
                target_cx = x + w // 2 + TARGET_OFFSET_X
                target_cy = y + h // 2 + TARGET_OFFSET_Y
                cv2.circle(out, (target_cx, target_cy), 10, (0, 255, 255), -1)

                rel_x = target_cx
                rel_y = target_cy

                if self.clamped_pos:
                    clamped_x, clamped_y = self.clamped_pos
                    clamped_rel_x = int(clamped_x - self.region["left"])
                    clamped_rel_y = int(clamped_y - self.region["top"])
                    cv2.line(
                        out,
                        (player_cx, player_cy),
                        (clamped_rel_x, clamped_rel_y),
                        (255, 255, 0),
                        2,
                    )
                    cv2.circle(
                        out, (clamped_rel_x, clamped_rel_y), 12, (255, 100, 255), -1
                    )
                    cv2.circle(
                        out, (clamped_rel_x, clamped_rel_y), 15, (255, 0, 255), 3
                    )
                    cv2.line(
                        out,
                        (rel_x, rel_y),
                        (clamped_rel_x, clamped_rel_y),
                        (255, 100, 0),
                        2,
                    )
                    cv2.putText(
                        out,
                        f"AIM: ({clamped_x}, {clamped_y})",
                        (x, y + h + 25),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 100, 255),
                        2,
                    )

                size = 15
                cv2.line(
                    out,
                    (rel_x - size, rel_y - size),
                    (rel_x + size, rel_y + size),
                    (0, 0, 255),
                    4,
                )
                cv2.line(
                    out,
                    (rel_x + size, rel_y - size),
                    (rel_x - size, rel_y + size),
                    (0, 0, 255),
                    4,
                )
                cv2.circle(out, (rel_x, rel_y), size + 5, (0, 0, 255), 2)
                rx = target_cx + self.region["left"]
                ry = target_cy + self.region["top"]
                cv2.putText(
                    out,
                    f"TARGET: ({rx}, {ry})",
                    (x, y + h + 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    2,
                )

        count = len(self.detections)
        status = f"TARGETS: {count}"
        status_color = (0, 255, 0) if count > 0 else (100, 100, 100)

        cv2.putText(
            out,
            f"FPS: {self.fps:.0f}",
            (15, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.putText(
            out, status, (15, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 3
        )

        active = self.get_active_target()
        y_pos = 160
        for tid, target in self.target_manager.get_all().items():
            prefix = ">" if tid == self.active_target_id else " "
            cv2.putText(
                out,
                f"{prefix}[{tid}] {target.file}: S={target.scale:.2f} C={target.color_threshold:.2f} T={target.template_threshold:.2f}",
                (15, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (200, 200, 200),
                1,
            )
            y_pos += 14

        cv2.putText(
            out,
            f"Active: S={active.scale:.2f} C={active.color_threshold:.2f} T={active.template_threshold:.2f}",
            (15, y_pos + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 255, 0),
            1,
        )

        cv2.putText(
            out,
            "=== CONTROLS ===",
            (15, y_pos + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (150, 150, 150),
            1,
        )
        cv2.putText(
            out,
            "1-9: Select | +/-: Scale | [/]: Color | [,/.]: Template",
            (15, y_pos + 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (200, 200, 200),
            1,
        )
        cv2.putText(
            out,
            "R: Reload all | ESC: Exit",
            (15, y_pos + 51),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (200, 200, 200),
            1,
        )

        return out

    def update_fps(self):
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.start_time = time.time()

    def run(self):
        cv2.namedWindow("DETECTOR", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("DETECTOR", CAPTURE_WIDTH, CAPTURE_HEIGHT)

        print("\n" + "=" * 60)
        print("MULTI-TARGET DETECTOR")
        print("=" * 60)
        print(self.target_manager.get_info())
        print("=" * 60)
        print("1-9       : Select target")
        print("+/-       : Scale (0.1 - 1.0)")
        print("[/]       : Color Threshold (0.0 - 1.0)")
        print(",/.       : Template Threshold (0.1 - 1.0)")
        print("R         : Reload all targets")
        print("ESC       : Exit")
        print("=" * 60 + "\n")

        while True:
            frame = self.capture()
            self.reload_if_needed()
            self.detect(frame)
            region_offset = (self.region["left"], self.region["top"])
            self.clamped_pos = self.clamper.update(self.detections, region_offset)
            self.raw_target_pos = self.clamper.get_raw_target_pos(self.detections)
            out = self.draw(frame)

            cv2.imshow("DETECTOR", out)
            self.update_fps()

            active = self.get_active_target()
            print(
                f"[{self.fps:.0f} FPS] Targets: {len(self.detections)} | Active: T{self.active_target_id} | S:{active.scale:.2f} C:{active.color_threshold:.2f} T:{active.template_threshold:.2f}",
                end="\r",
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                break
            elif key == ord("+") or key == ord("="):
                active.scale = min(1.0, active.scale + 0.05)
                active.update_scale(active.scale)
                print(
                    f"\n[T{self.active_target_id}] Scale: {active.scale:.2f} ({active.scaled_w}x{active.scaled_h})"
                )
            elif key == ord("-") or key == ord("_"):
                active.scale = max(0.1, active.scale - 0.05)
                active.update_scale(active.scale)
                print(
                    f"\n[T{self.active_target_id}] Scale: {active.scale:.2f} ({active.scaled_w}x{active.scaled_h})"
                )
            elif key == ord("[") or key == ord("{"):
                active.color_threshold = max(0.0, active.color_threshold - 0.01)
                print(
                    f"\n[T{self.active_target_id}] Color Threshold: {active.color_threshold:.2f}"
                )
            elif key == ord("]") or key == ord("}"):
                active.color_threshold = min(1.0, active.color_threshold + 0.01)
                print(
                    f"\n[T{self.active_target_id}] Color Threshold: {active.color_threshold:.2f}"
                )
            elif key == ord(",") or key == ord("<"):
                active.template_threshold = max(0.1, active.template_threshold - 0.01)
                print(
                    f"\n[T{self.active_target_id}] Template Threshold: {active.template_threshold:.2f}"
                )
            elif key == ord(".") or key == ord(">"):
                active.template_threshold = min(1.0, active.template_threshold + 0.01)
                print(
                    f"\n[T{self.active_target_id}] Template Threshold: {active.template_threshold:.2f}"
                )
            elif key >= ord("1") and key <= ord("9"):
                tid = key - ord("0")
                if tid in self.target_manager.get_all():
                    self.active_target_id = tid
                    print(
                        f"\nActive target: T{tid} ({self.target_manager.get(tid).file})"
                    )
            elif key == ord("r") or key == ord("R"):
                self.needs_reload = True

        cv2.destroyAllWindows()


def main():
    try:
        MultiTargetDetector().run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

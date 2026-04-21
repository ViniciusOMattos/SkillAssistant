from config import TARGET_CONFIGS, TARGETS_DIR
import cv2
import numpy as np


class TargetConfig:
    def __init__(self, target_id, config):
        self.id = target_id
        self.file = config["file"]
        self.scale = config["scale"]
        self.color_threshold = config["color_threshold"]
        self.template_threshold = config["template_threshold"]
        self._load_template()

    def _load_template(self):
        path = f"{TARGETS_DIR}/{self.file}"
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Template '{path}' not found")

        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        self.template_color = img
        self.template_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        masked = hsv[hsv[:, :, 1] > 50]

        if len(masked) > 0:
            h_mean = np.mean(masked[:, 0])
            h_std = np.std(masked[:, 0])
            s_mean = np.mean(masked[:, 1])
            s_std = np.std(masked[:, 1])
            v_mean = np.mean(masked[:, 2])
            v_std = np.std(masked[:, 2])
            self.lower_hsv = np.array(
                [
                    max(0, h_mean - h_std * 1.5),
                    max(30, s_mean - s_std),
                    max(20, v_mean - v_std),
                ]
            )
            self.upper_hsv = np.array(
                [
                    min(180, h_mean + h_std * 1.5),
                    min(255, s_mean + s_std),
                    min(255, v_mean + v_std),
                ]
            )
        else:
            self.lower_hsv = np.array([0, 80, 40])
            self.upper_hsv = np.array([20, 255, 150])

        self.scaled_w = int(self.template_gray.shape[1] * self.scale)
        self.scaled_h = int(self.template_gray.shape[0] * self.scale)

    def reload(self):
        self._load_template()

    def update_scale(self, scale):
        self.scale = scale
        self.scaled_w = int(self.template_gray.shape[1] * self.scale)
        self.scaled_h = int(self.template_gray.shape[0] * self.scale)


class TargetManager:
    def __init__(self):
        self.targets = {}
        for target_id, config in TARGET_CONFIGS.items():
            self.targets[target_id] = TargetConfig(target_id, config)

    def get(self, target_id):
        return self.targets.get(target_id)

    def get_all(self):
        return self.targets

    def reload(self, target_id):
        if target_id in self.targets:
            self.targets[target_id].reload()

    def reload_all(self):
        for target in self.targets.values():
            target.reload()

    def get_info(self):
        info = []
        for tid, target in self.targets.items():
            info.append(
                f"  [{tid}] {target.file}: S={target.scale:.2f} C={target.color_threshold:.2f} T={target.template_threshold:.2f}"
            )
        return "\n".join(info)

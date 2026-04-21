from config import (
    TARGET_OFFSET_X,
    TARGET_OFFSET_Y,
    ATTACK_RANGE,
    PLAYER_OFFSET_X,
    PLAYER_OFFSET_Y,
)

import math


class TargetClamper:
    def __init__(self):
        self.region_offset = (0, 0)

    def get_player_pos(self):
        return (
            PLAYER_OFFSET_X + self.region_offset[0],
            PLAYER_OFFSET_Y + self.region_offset[1],
        )

    def update(self, detections, region_offset=None):
        if not detections:
            return None

        if region_offset is not None:
            self.region_offset = region_offset

        nearest = detections[0]
        target_x = (
            nearest["x"] + nearest["w"] // 2 + TARGET_OFFSET_X + self.region_offset[0]
        )
        target_y = (
            nearest["y"] + nearest["h"] // 2 + TARGET_OFFSET_Y + self.region_offset[1]
        )

        player_pos = self.get_player_pos()
        return self._clamp_to_range(target_x, target_y, player_pos)

    def _clamp_to_range(self, target_x, target_y, player_pos):
        dx = target_x - player_pos[0]
        dy = target_y - player_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist <= ATTACK_RANGE or dist == 0:
            return (target_x, target_y)

        ratio = ATTACK_RANGE / dist
        return (player_pos[0] + dx * ratio, player_pos[1] + dy * ratio)

    def get_raw_target_pos(self, detections):
        if not detections:
            return None
        nearest = detections[0]
        return (
            nearest["x"] + nearest["w"] // 2 + TARGET_OFFSET_X + self.region_offset[0],
            nearest["y"] + nearest["h"] // 2 + TARGET_OFFSET_Y + self.region_offset[1],
        )

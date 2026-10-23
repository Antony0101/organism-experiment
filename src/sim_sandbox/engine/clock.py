"""Render-independent fixed-step simulation timing."""

from __future__ import annotations


class FixedStepClock:
    SPEEDS = (0.25, 1.0, 2.0, 4.0)

    def __init__(self, tick_rate: float = 60.0, max_steps_per_frame: int = 16) -> None:
        if tick_rate <= 0 or max_steps_per_frame <= 0:
            raise ValueError("tick rate and maximum step count must be positive")
        self.fixed_dt = 1.0 / tick_rate
        self.max_steps_per_frame = max_steps_per_frame
        self.speed = 1.0
        self.paused = False
        self._accumulator = 0.0
        self._single_steps = 0

    @property
    def alpha(self) -> float:
        if self.paused:
            return 1.0
        return min(1.0, self._accumulator / self.fixed_dt)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self._accumulator = 0.0

    def request_step(self) -> None:
        if self.paused:
            self._single_steps += 1

    def set_speed(self, speed: float) -> None:
        if speed not in self.SPEEDS:
            raise ValueError(f"speed must be one of {self.SPEEDS}")
        self.speed = speed

    def consume_steps(self, real_dt: float) -> int:
        if real_dt < 0:
            raise ValueError("real_dt cannot be negative")
        if self.paused:
            steps = min(self._single_steps, self.max_steps_per_frame)
            self._single_steps -= steps
            return steps
        self._single_steps = 0
        self._accumulator += min(real_dt, 0.25) * self.speed
        available = int((self._accumulator + 1e-12) / self.fixed_dt)
        steps = min(available, self.max_steps_per_frame)
        self._accumulator -= steps * self.fixed_dt
        return steps


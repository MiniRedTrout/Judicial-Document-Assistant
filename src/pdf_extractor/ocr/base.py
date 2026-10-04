from abc import ABC, abstractmethod

import numpy as np


class OCREngine(ABC):

    name: str = "base"

    @abstractmethod
    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        """
        Распознаёт текст на изображении.

        Returns:
            (текст, средняя уверенность 0..1)
        """
        ...
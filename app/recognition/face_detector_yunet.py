import cv2
import numpy as np

class FaceDetectorYuNet:
    def __init__(self, model_path, input_size=(320, 320), conf_threshold=0.9, nms_threshold=0.3, top_k=5000):
        self.model_path = model_path
        # Initialize YuNet
        self.detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=input_size,
            score_threshold=conf_threshold,
            nms_threshold=nms_threshold,
            top_k=top_k
        )
        self.input_size = input_size

    def set_input_size(self, size):
        self.input_size = size
        self.detector.setInputSize(size)

    def detect(self, image):
        """
        Returns a list of faces where each face is a NumPy array.
        The first 4 elements are bbox (x, y, w, h).
        The next 10 are landmarks (right eye, left eye, nose tip, right mouth corner, left mouth corner).
        The last element is confidence.
        """
        height, width, _ = image.shape
        if self.input_size != (width, height):
            self.set_input_size((width, height))
            
        _, faces = self.detector.detect(image)
        return faces if faces is not None else []

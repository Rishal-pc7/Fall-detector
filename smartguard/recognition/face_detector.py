import cv2

class FaceDetectorYuNet:
    """Wrapper for OpenCV YuNet face detector."""
    def __init__(self, model_path, input_size=(320, 320), conf_threshold=0.9, nms_threshold=0.3, top_k=5000):
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
        height, width, _ = image.shape
        if self.input_size != (width, height):
            self.set_input_size((width, height))
            
        _, faces = self.detector.detect(image)
        return faces if faces is not None else []

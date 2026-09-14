import cv2

class FaceRecognizerSFace:
    """Wrapper for OpenCV SFace recognizer."""
    def __init__(self, model_path):
        self.recognizer = cv2.FaceRecognizerSF.create(
            model=model_path,
            config=""
        )

    def align_crop(self, image, face):
        return self.recognizer.alignCrop(image, face)

    def feature(self, aligned_face):
        return self.recognizer.feature(aligned_face)

    def match(self, feature1, feature2, threshold=0.363):
        score = self.recognizer.match(feature1, feature2, cv2.FaceRecognizerSF_FR_COSINE)
        return score >= threshold, score

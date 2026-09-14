import cv2
import numpy as np

class FaceRecognizerSFace:
    def __init__(self, model_path):
        self.recognizer = cv2.FaceRecognizerSF.create(
            model=model_path,
            config=""
        )

    def align_crop(self, image, face):
        """
        Aligns and crops the face using the 5 landmarks detected by YuNet.
        Returns the aligned face crop as 112x112 image.
        """
        return self.recognizer.alignCrop(image, face)

    def feature(self, aligned_face):
        """
        Extracts a 128-d feature vector (embedding) from an aligned face.
        """
        feature = self.recognizer.feature(aligned_face)
        return feature

    def match(self, feature1, feature2, threshold=0.363):
        """
        Matches two features. Returns True if matched, False otherwise.
        Uses cosine distance by default. For cosine, score >= threshold means match.
        """
        score = self.recognizer.match(feature1, feature2, cv2.FaceRecognizerSF_FR_COSINE)
        return score >= threshold, score

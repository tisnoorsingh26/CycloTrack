from io import BytesIO

import numpy as np
from PIL import Image

from app.schemas import CNN_SHAPE, WindPredictResponse
from app.services.registry import registry

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/tiff",
    "image/tif",
    "application/octet-stream",
}


class CnnError(ValueError):
    pass


def _from_array_clean(array: np.ndarray) -> tuple[np.ndarray, list[str]]:
    if array.ndim == 4 and array.shape[0] == 1:
        array = array[0]
    if array.shape != CNN_SHAPE:
        raise CnnError(
            f"CNN expects shape {CNN_SHAPE}. Received {tuple(array.shape)}. "
            "Training used 128×128 four-channel HDF5 arrays, not ordinary RGB photos."
        )
    array = array.astype(np.float32)
    if not np.isfinite(array).all():
        raise CnnError("Image contains non-finite values.")
    notes: list[str] = []
    if float(np.nanmax(array)) > 1.5:
        array = array / 255.0
        notes.append("Divided by 255.0, matching the training notebook.")
    else:
        notes.append("Values were already in [0, 1]; skipped /255 to avoid double-normalising.")
    notes.append(
        "Channel semantics are not documented in the training notebook; "
        "ordinary 3-channel RGB uploads are not a valid model input."
    )
    return array[np.newaxis, ...], notes


def load_cnn_input(filename: str, content: bytes) -> tuple[np.ndarray, list[str]]:
    name = filename.lower()
    if name.endswith(".npy"):
        array = np.load(BytesIO(content), allow_pickle=False)
        return _from_array_clean(array)
    if name.endswith(".npz"):
        packed = np.load(BytesIO(content), allow_pickle=False)
        key = "images" if "images" in packed.files else packed.files[0]
        return _from_array_clean(packed[key])

    try:
        image = Image.open(BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise CnnError(
            "Could not read the upload. Use a .npy/.npz array of shape (128, 128, 4) "
            "or a 4-channel PNG/TIFF. RGB photographs are not supported."
        ) from exc

    array = np.array(image)
    if array.ndim == 2:
        raise CnnError("Grayscale images are not supported. Need (128, 128, 4).")
    if array.ndim == 3 and array.shape[2] == 3:
        raise CnnError(
            "This CNN was trained on 4-channel 128×128 arrays from Cyclone_Images.h5. "
            "A 3-channel RGB photo cannot be passed in directly, and this API will not "
            "invent a fourth channel."
        )
    if array.ndim == 3 and array.shape[2] > 4:
        array = array[:, :, :4]
    if array.shape[:2] != CNN_SHAPE[:2]:
        raise CnnError(
            f"Image spatial size must be 128×128. Received {array.shape[0]}×{array.shape[1]}. "
            "The notebook did not resize images at train time."
        )
    return _from_array_clean(array)


def predict_wind(filename: str, content: bytes) -> WindPredictResponse:
    if registry.cnn is None:
        raise CnnError("CNN weights are not loaded. Check /health.")
    batch, notes = load_cnn_input(filename, content)
    raw = registry.cnn.predict(batch, verbose=0)
    value = float(np.asarray(raw).reshape(-1)[0])
    if not np.isfinite(value):
        raise CnnError("Model returned a non-finite wind speed.")
    return WindPredictResponse(
        predicted_wind_knots=value,
        input_shape=list(CNN_SHAPE),
        preprocessing="float32; divide by 255 if values exceed 1.5; no extra resizing",
        notes=notes,
    )

from datetime import datetime
import uuid

from app import mongo

COLLECTION = "protected_images"


def save_protected_image(
    user_id,
    filename,
    hidden_id,
    landmark_signature
):
    """
    Save protected image metadata to MongoDB.
    """

    document = {

        "image_id": str(uuid.uuid4()),

        "user_id": user_id,

        "filename": filename,

        "hidden_id": hidden_id,

        "landmark_signature": landmark_signature,

        "created_at": datetime.utcnow()

    }

    mongo.db[COLLECTION].insert_one(document)

    return document


def get_image_by_hidden_id(hidden_id):

    return mongo.db[COLLECTION].find_one(
        {"hidden_id": hidden_id}
    )
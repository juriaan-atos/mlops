import os
import logging
import json
import numpy
import joblib
import requests
from pathlib import Path


def get_token():
    access_token = None
    msi_endpoint = os.environ.get("MSI_ENDPOINT", None)
    msi_secret = os.environ.get("MSI_SECRET", None)

    # If UAI_CLIENT_ID is provided then assume that endpoint was created with user assigned identity,
    # # otherwise system assigned identity deployment.
    client_id = os.environ.get("UAI_CLIENT_ID", None)
    if client_id is not None:
        token_url = (
            msi_endpoint + f"?clientid={client_id}&resource=https://storage.azure.com/"
        )
    else:
        token_url = msi_endpoint + f"?resource=https://storage.azure.com/"

    logging.info("Trying to get identity token...")
    headers = {"secret": msi_secret, "Metadata": "true"}
    resp = requests.get(token_url, headers=headers)
    resp.raise_for_status()
    access_token = resp.json()["access_token"]
    logging.info("Retrieved token successfully.")
    return access_token


def access_blob_storage():
    logging.info("Trying to access blob storage...")
    storage_account = os.environ.get("STORAGE_ACCOUNT_NAME")
    storage_container = os.environ.get("STORAGE_CONTAINER_NAME")
    file_name = os.environ.get("FILE_NAME")
    logging.info(
        f"storage_account: {storage_account}, container: {storage_container}, filename: {file_name}"
    )
    token = get_token()

    blob_url = f"https://{storage_account}.blob.core.windows.net/{storage_container}/{file_name}?api-version=2019-04-01"
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-blob-type": "BlockBlob",
        "x-ms-version": "2019-02-02",
    }
    resp = requests.get(blob_url, headers=auth_headers)
    resp.raise_for_status()
    logging.info(f"Blob containts: {resp.text}")


def init():
    global model
    # AZUREML_MODEL_DIR is an environment variable created during deployment.
    # It is the path to the model folder (./azureml-models/$MODEL_NAME/$VERSION)
    # For multiple models, it points to the folder containing all deployed models (./azureml-models)
    model_path = os.path.join(
        os.getenv("AZUREML_MODEL_DIR"), "model", "sklearn_regression_model.pkl"
    )
    # deserialize the model file back into a sklearn model
    model = joblib.load(model_path)
    logging.info("Model loaded")

    # Access Azure resource (Blob storage) using system assigned identity token
    access_blob_storage()

    logging.info("Init complete")


# note you can pass in multiple rows for scoring
def run(raw_data):
    logging.info("Request received")
    data = json.loads(raw_data)["data"]
    data = numpy.array(data)
    result = model.predict(data)
    logging.info("Request processed")
    return result.tolist()

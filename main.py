import firebase_admin
from firebase_admin import credentials, storage, firestore
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import os
from flask_cors import CORS

cred = credentials.Certificate(f"{os.getcwd()}/config.json")
firebase_admin.initialize_app(cred)
bucket = storage.bucket("filesys-c1fc0.appspot.com")
db = firestore.client()

expiration_time_seconds = 3600
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/upload", methods=["POST"])
def upload():
    try:
        file = request.files["file"]
        upload_file_name = file.filename
        if upload_file_name.startswith("nextcloud_"):
            upload_file_name = upload_file_name.replace("nextcloud_", "")
        # Split the filename by underscores to separate company_id, project_id, and filename
        filename_parts = upload_file_name.split("_")
        if len(filename_parts) < 3:
            return jsonify({"message": "Invalid filename format"}), 400

        company_id = filename_parts[0]
        project_id = filename_parts[1]
        filename = "_".join(filename_parts[2:])

        blob = bucket.blob(f"{company_id}/{project_id}/{filename}")
        blob.upload_from_file(file)

        expiration_time = expiration_time = datetime.utcnow() + timedelta(days=3650)

        # Get the download URL of the uploaded file with the specified expiration time
        download_link = blob.generate_signed_url(expiration=expiration_time)
        # Store information in Firestore
        doc_ref = db.collection("files").document()
        doc_ref.set(
            {
                "company_id": company_id,
                "project_id": project_id,
                "filename": filename,
                "download_link": download_link,
                "isLocked": False,
            }
        )

        return jsonify({"message": "File uploaded successfully"}), 200
    except Exception as e:
        print(e)
        return jsonify({"message": f"File upload failed: {str(e)}"}), 500


# @app.route('/download', methods=['GET'])
# def download():
#     try:
#         filename = request.args.get('filename')

#         # Split the filename by underscores to separate company_id, project_id, and filename
#         filename_parts = filename.split('_')
#         if len(filename_parts) < 3:
#             return jsonify({'message': 'Invalid filename format'}), 400

#         company_id = filename_parts[0]
#         project_id = filename_parts[1]
#         filename = '_'.join(filename_parts[2:])

#         blob = bucket.blob(f'{company_id}/{project_id}/{filename}')
#         blob.download_to_filename(filename)

#         return jsonify({'message': 'File downloaded successfully'}), 200
#     except Exception as e:
#         return jsonify({'message': f'File download failed: {str(e)}'}), 500


@app.route("/lock", methods=["POST"])
def lock_file():
    try:
        # Get filename from request body
        filename = request.json.get("filename")
        print(filename)
        # if not filename:
        #     print("file not found")
        #     return jsonify({'message': 'Filename is required in the request body'}), 400

        # Get the document reference for the file
        file_ref = (
            db.collection("files").where("filename", "==", filename).limit(1).get()
        )
        if not file_ref:
            return jsonify({"message": "File not found"}), 404

        # Update the document to set isLocked to True
        file_ref[0].reference.update({"isLocked": True})

        return jsonify({"message": "File locked successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


@app.route("/unlock", methods=["POST"])
def unlock_file():
    try:
        # Get filename from request body
        filename = request.json.get("filename")
        if not filename:
            return jsonify({"message": "Filename is required in the request body"}), 400

        # Get the document reference for the file
        file_ref = (
            db.collection("files").where("filename", "==", filename).limit(1).get()
        )
        if not file_ref:
            return jsonify({"message": "File not found"}), 404

        # Update the document to set isLocked to False
        file_ref[0].reference.update({"isLocked": False})

        return jsonify({"message": "File unlocked successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500


@app.route("/overwrite", methods=["POST"])
def overwrite():
    try:
        # Get filename from request body
        file = request.files["file"]
        upload_file_name = file.filename
        if upload_file_name.startswith("nextcloud_"):
            upload_file_name = upload_file_name.replace("nextcloud_", "")
        # Split the filename by underscores to separate company_id, project_id, and filename
        filename_parts = upload_file_name.split("_")
        if len(filename_parts) < 3:
            return jsonify({"message": "Invalid filename format"}), 400

        company_id = filename_parts[0]
        project_id = filename_parts[1]
        filename = "_".join(filename_parts[2:])

        # Get the document reference for the file
        file_ref = (
            db.collection("files").where("filename", "==", filename).limit(1).get()
        )
        if not file_ref:
            return jsonify({"message": "File not found"}), 404

        # Delete the existing file from storage
        blob = bucket.blob(f"{company_id}/{project_id}/{filename}")
        blob.delete()

        # Reupload the new file
        blob = bucket.blob(f"{company_id}/{project_id}/{filename}")
        new_file = request.files["file"]
        blob.upload_from_file(new_file)

        # Update the document to set isLocked to True
        file_ref[0].reference.update({"isLocked": False})

        return jsonify({"message": "File updated successfully"}), 200
    except Exception as e:
        print(e)
        return jsonify({"message": f"Error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=os.environ.get("PORT", 5000))

"""Tests for the cloud_storage module."""

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import datetime
import io
import unittest
import unittest.mock

import cloud_storage


class CloudStorageTest(unittest.TestCase):
  """Test cases for cloud_storage module."""

  @unittest.mock.patch("cloud_storage.storage.Client")
  @unittest.mock.patch("uuid.uuid4")
  @unittest.mock.patch("datetime.datetime")
  def test_upload_video_to_gcs(
      self, mock_datetime, mock_uuid, mock_storage_client
  ):
    """Tests that upload_video_to_gcs correctly uploads a video and returns path."""
    mock_now = unittest.mock.MagicMock()
    mock_now.isoformat.return_value = "2023-01-01T12:00:00"
    mock_datetime.now.return_value = mock_now

    mock_uuid.return_value = "uuid-1234"

    mock_bucket = unittest.mock.MagicMock()
    mock_blob = unittest.mock.MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    video_file = io.BytesIO(b"video data")
    video_name = "test_video.mp4"
    bucket_name = "test-bucket"

    result = cloud_storage.upload_video_to_gcs(
        video_name, video_file, bucket_name
    )

    expected_dir = "2023-01-01T12_00_00-uuid-1234-test_video"
    expected_path = f"{expected_dir}/{expected_dir}"

    self.assertEqual(result, expected_path)
    mock_client_instance.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(expected_path)
    mock_blob.upload_from_file.assert_called_once_with(
        video_file, content_type="video/mp4"
    )

  @unittest.mock.patch("cloud_storage.storage.Client")
  def test_upload_file_to_gcs(self, mock_storage_client):
    """Tests that upload_file_to_gcs correctly uploads a file."""
    mock_bucket = unittest.mock.MagicMock()
    mock_blob = unittest.mock.MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    file_object = io.BytesIO(b"file data")
    target_path = "path/to/file.txt"
    bucket_name = "test-bucket"

    result = cloud_storage.upload_file_to_gcs(
        target_path, file_object, bucket_name
    )

    self.assertEqual(result, target_path)
    mock_client_instance.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(target_path)
    # Checks that it guesses mime type if not provided
    mock_blob.upload_from_file.assert_called_once_with(
        file_object, content_type="text/plain"
    )

  @unittest.mock.patch("cloud_storage.storage.Client")
  def test_upload_file_to_gcs_with_mime_type(self, mock_storage_client):
    """Tests valid upload_file_to_gcs with explicit mime type."""
    mock_bucket = unittest.mock.MagicMock()
    mock_blob = unittest.mock.MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    file_object = io.BytesIO(b"data")
    target_path = "file.bin"
    bucket_name = "test-bucket"
    mime_type = "application/custom"

    cloud_storage.upload_file_to_gcs(
        target_path, file_object, bucket_name, mime_type
    )

    mock_blob.upload_from_file.assert_called_once_with(
        file_object, content_type=mime_type
    )

  @unittest.mock.patch("cloud_storage.storage.Client")
  def test_get_url_for_path(self, mock_storage_client):
    """Tests that get_url_for_path generates a signed URL."""
    mock_bucket = unittest.mock.MagicMock()
    mock_blob = unittest.mock.MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    expected_url = "https://storage.googleapis.com/signed-url"
    mock_blob.generate_signed_url.return_value = expected_url

    bucket_name = "test-bucket"
    path = "some/file.txt"
    service_account_email = "test@service.com"
    access_token = "test-token"

    result = cloud_storage.get_url_for_path(
        bucket_name,
        path,
        service_account_email=service_account_email,
        access_token=access_token,
    )

    self.assertEqual(result, expected_url)
    mock_client_instance.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(path)
    mock_blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=(60 * 60 * 24),
        method="GET",
        service_account_email=service_account_email,
        access_token=access_token,
    )

  @unittest.mock.patch("cloud_storage.storage.Client")
  def test_generate_signed_upload_url(self, mock_storage_client):
    """Tests that generate_signed_upload_url generates a signed URL for PUT."""
    mock_bucket = unittest.mock.MagicMock()
    mock_blob = unittest.mock.MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    expected_url = "https://storage.googleapis.com/signed-upload-url"
    mock_blob.generate_signed_url.return_value = expected_url

    bucket_name = "test-bucket"
    object_name = "some/upload.mp4"
    content_type = "video/mp4"
    service_account_email = "test@service.com"
    access_token = "test-token"

    result = cloud_storage.generate_signed_upload_url(
        bucket_name,
        object_name,
        content_type=content_type,
        service_account_email=service_account_email,
        access_token=access_token,
    )

    self.assertEqual(result, expected_url)
    mock_client_instance.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(object_name)
    mock_blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type=content_type,
        service_account_email=service_account_email,
        access_token=access_token,
    )


if __name__ == "__main__":
  unittest.main()

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from typing import Optional
from app.config.settings import settings
import logging
import uuid
import os

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage with AWS S3"""
    
    def __init__(self, upload_folder: str = "uploads"):
        # self.s3_client = boto3.client(
        #     's3',
        #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        #     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        #     region_name=settings.AWS_REGION
        # )
        self.bucket_name = settings.AWS_S3_BUCKET
        
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)
    
    async def upload_file(
        self,
        file: UploadFile,
        key: str,
        content_type: Optional[str] = None
    ) -> str:
        """Upload file to S3 and return URL"""
        try:
            # Reset file pointer
            await file.seek(0)
            
            # Upload file
            # self.s3_client.upload_fileobj(
            #     file.file,
            #     self.bucket_name,
            #     key,
            #     ExtraArgs={
            #         'ContentType': content_type or file.content_type or 'application/octet-stream',
            #         'ACL': 'public-read'
            #     }
            # )
            
            # # Return public URL
            # url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
            # return url
            
            file_location = f"./uploads/{key}"
            print("file location:",file_location)
            with open(file_location, "wb") as f:
                contents = await file.read()
                f.write(contents)
            logger.info(f"File saved to {file_location}")
            return {file_location}
            
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")
    
    async def upload_from_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = 'application/octet-stream'
    ) -> str:
        """Upload bytes data to S3"""
        try:
            # self.s3_client.put_object(
            #     Bucket=self.bucket_name,
            #     Key=key,
            #     Body=data,
            #     ContentType=content_type,
            #     ACL='public-read'
            # )
            
            # url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
            # return url
        
            file_location = os.path.join(self.upload_folder, key)
            logger.info(f"Saving file to {file_location}")
            with open(file_location, "wb") as f:
                f.write(data)
            return file_location
            
        except ClientError as e:
            logger.error(f"Error uploading bytes to S3: {e}")
            raise Exception(f"Failed to upload data: {str(e)}")
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False
    
    async def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """Generate presigned URL for temporary access"""
        try:
            url = self.s3_client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise Exception(f"Failed to generate URL: {str(e)}")
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    async def get_file_info(self, key: str) -> Optional[dict]:
        """Get file metadata"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'size': response['ContentLength'],
                'content_type': response['ContentType'],
                'last_modified': response['LastModified'],
                'etag': response['ETag']
            }
        except ClientError as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    def generate_unique_key(self, user_id: str, folder: str, filename: str) -> str:
        """Generate unique S3 key for file"""
        file_extension = os.path.splitext(filename)[1]
        unique_name = f"{uuid.uuid4()}{file_extension}"
        return f"{folder}/{user_id}/{unique_name}"
    
    async def copy_file(self, source_key: str, dest_key: str) -> str:
        """Copy file within S3"""
        try:
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_key,
                ACL='public-read'
            )
            
            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{dest_key}"
            return url
            
        except ClientError as e:
            logger.error(f"Error copying file in S3: {e}")
            raise Exception(f"Failed to copy file: {str(e)}")
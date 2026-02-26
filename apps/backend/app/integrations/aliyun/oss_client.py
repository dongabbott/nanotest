"""Aliyun OSS client integration for object storage using httpx."""
import base64
import hashlib
import hmac
import urllib.parse
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

DEFAULT_OSS_STS_TOKEN_URL = "https://admin.shiguangxiaowu.cn/rhea/users/file_store_token"


@dataclass
class OSSConfig:
    """阿里云 OSS 配置"""
    endpoint: str
    access_key_id: str
    access_key_secret: str
    sts_token: str
    bucket: str
    path: str
    expiration: int
    expires_in: int
    has_accelerate: bool = False
    service: str = "aliyun_cn"


class AliyunOSSClient:
    """阿里云 OSS 客户端封装（使用 httpx 实现）"""
    
    def __init__(self):
        self._config: Optional[OSSConfig] = None
        self._config_expires_at: Optional[datetime] = None
        self._http_client = httpx.Client(timeout=300)  # 5 分钟超时，适合大文件上传
    
    def _is_config_expired(self) -> bool:
        """检查配置是否过期"""
        if not self._config or not self._config_expires_at:
            return True
        # 提前 5 分钟刷新
        return datetime.now() >= self._config_expires_at - timedelta(minutes=5)
    
    def _fetch_sts_token(self) -> OSSConfig:
        """从接口获取 STS Token"""
        logger.info("Fetching Aliyun OSS STS token...")
        try:
            sts_url = settings.oss_sts_token_url or DEFAULT_OSS_STS_TOKEN_URL
            response = httpx.get(sts_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            config = OSSConfig(
                endpoint=data["endpoint"],
                access_key_id=data["access_key_id"],
                access_key_secret=data["access_key_secret"],
                sts_token=data["sts_token"],
                bucket=data["bucket"],
                path=data["path"],
                expiration=data["expiration"],
                expires_in=data["expires_in"],
                has_accelerate=data.get("has_accelerate", False),
                service=data.get("service", "aliyun_cn"),
            )
            
            logger.info(f"Got OSS config, bucket: {config.bucket}, path: {config.path}")
            return config
        except Exception as e:
            logger.error(f"Failed to fetch STS token: {e}")
            raise RuntimeError(f"Failed to fetch Aliyun OSS credentials: {e}")
    
    def _ensure_config(self):
        """确保配置已加载且未过期"""
        if self._is_config_expired():
            self._config = self._fetch_sts_token()
            self._config_expires_at = datetime.now() + timedelta(seconds=self._config.expires_in)
            logger.info("Aliyun OSS config refreshed")
    
    def _get_full_key(self, object_key: str) -> str:
        """获取完整的对象键（包含配置的路径前缀）"""
        self._ensure_config()
        path_prefix = self._config.path.rstrip("/")
        return f"{path_prefix}/{object_key}"
    
    def _get_oss_host(self) -> str:
        """获取 OSS 主机地址"""
        self._ensure_config()
        endpoint = self._config.endpoint
        bucket = self._config.bucket

        # endpoint 格式可能是:
        # https://timehut-cn-sz.oss-cn-shenzhen.aliyuncs.com (已包含 bucket)
        # https://oss-cn-shenzhen.aliyuncs.com (需要拼接 bucket)
        # CDN host (e.g. https://alicn.timehutcdn.cn) MUST NOT be used for signed PUT/DELETE.
        if "timehutcdn.cn" in endpoint:
            # If STS token service accidentally returns CDN endpoint, fall back to standard bucket endpoint.
            # This assumes endpoint_without_bucket can be derived from the OSS region in the bucket endpoint.
            # Best-effort: keep https and strip host to bucket default.
            endpoint = "https://oss-cn-shenzhen.aliyuncs.com"

        if bucket in endpoint:
            return endpoint
        else:
            if endpoint.startswith("https://"):
                return f"https://{bucket}.{endpoint[8:]}"
            elif endpoint.startswith("http://"):
                return f"http://{bucket}.{endpoint[7:]}"
            else:
                return f"https://{bucket}.{endpoint}"
    
    def _sign_request(
        self,
        method: str,
        object_key: str,
        content_type: str = "",
        content_md5: str = "",
        headers: dict = None,
    ) -> dict:
        """
        生成 OSS 签名请求头
        
        使用 OSS V1 签名方式 (兼容 STS Token)
        """
        self._ensure_config()
        
        # GMT 时间
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # 构建 CanonicalizedOSSHeaders
        oss_headers = {}
        if headers:
            for k, v in headers.items():
                if k.lower().startswith("x-oss-"):
                    oss_headers[k.lower()] = v
        
        # 添加 STS Token
        oss_headers["x-oss-security-token"] = self._config.sts_token
        
        canonicalized_oss_headers = ""
        if oss_headers:
            sorted_headers = sorted(oss_headers.items())
            canonicalized_oss_headers = "".join(f"{k}:{v}\n" for k, v in sorted_headers)
        
        # 构建 CanonicalizedResource
        canonicalized_resource = f"/{self._config.bucket}/{object_key}"
        
        # 构建签名字符串
        string_to_sign = f"{method}\n{content_md5}\n{content_type}\n{date}\n{canonicalized_oss_headers}{canonicalized_resource}"
        
        # 计算签名
        signature = base64.b64encode(
            hmac.new(
                self._config.access_key_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        
        # 构建请求头
        request_headers = {
            "Date": date,
            "Authorization": f"OSS {self._config.access_key_id}:{signature}",
            "x-oss-security-token": self._config.sts_token,
        }
        
        if content_type:
            request_headers["Content-Type"] = content_type
        if content_md5:
            request_headers["Content-MD5"] = content_md5
        
        return request_headers
    
    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        上传字节数据到 OSS
        
        Args:
            object_key: 对象键（不含路径前缀）
            data: 字节数据
            content_type: 内容类型
            
        Returns:
            完整的对象键
        """
        self._ensure_config()
        full_key = self._get_full_key(object_key)
        
        # 计算 Content-MD5
        content_md5 = base64.b64encode(hashlib.md5(data).digest()).decode("utf-8")
        
        # 生成签名
        headers = self._sign_request(
            method="PUT",
            object_key=full_key,
            content_type=content_type,
            content_md5=content_md5,
        )
        headers["Content-MD5"] = content_md5
        headers["Content-Length"] = str(len(data))
        
        # 构建 URL (uploads must always use OSS host, never CDN)
        url = f"{self._get_oss_host()}/{full_key}"
        
        logger.info(f"Uploading to OSS: {full_key}, size: {len(data)} bytes")
        
        response = self._http_client.put(url, content=data, headers=headers)
        
        if response.status_code not in (200, 201):
            logger.error(f"OSS upload failed: {response.status_code} - {response.text}")
            raise RuntimeError(f"OSS upload failed: {response.status_code} - {response.text}")
        
        logger.info(f"Upload completed: {full_key}")
        return full_key
    
    def download_bytes(self, object_key: str) -> bytes:
        """
        从 OSS 下载数据
        
        Args:
            object_key: 对象键（不含路径前缀，如果是完整路径则直接使用）
            
        Returns:
            字节数据
        """
        self._ensure_config()
        
        # 判断是否是完整路径
        if object_key.startswith(self._config.path):
            full_key = object_key
        else:
            full_key = self._get_full_key(object_key)
        
        headers = self._sign_request(method="GET", object_key=full_key)
        url = f"{self._get_oss_host()}/{full_key}"
        
        response = self._http_client.get(url, headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"OSS download failed: {response.status_code}")
        
        return response.content
    
    def get_download_url(
        self,
        object_key: str,
        expires: int = 3600,
    ) -> str:
        """
        获取预签名下载 URL
        
        Args:
            object_key: 对象键（不含路径前缀，如果是完整路径则直接使用）
            expires: 过期时间（秒）
            
        Returns:
            预签名 URL
        """
        self._ensure_config()
        
        # 判断是否是完整路径
        if object_key.startswith(self._config.path):
            full_key = object_key
        else:
            full_key = self._get_full_key(object_key)
        
        # 计算过期时间戳
        expire_timestamp = int(datetime.now().timestamp()) + expires
        
        # 构建签名字符串
        string_to_sign = f"GET\n\n\n{expire_timestamp}\n/{self._config.bucket}/{full_key}"
        
        # 计算签名
        signature = base64.b64encode(
            hmac.new(
                self._config.access_key_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        
        # URL 编码签名
        encoded_signature = urllib.parse.quote(signature, safe="")
        
        # 构建预签名 URL
        url = (
            f"{self._get_oss_host()}/{full_key}"
            f"?OSSAccessKeyId={self._config.access_key_id}"
            f"&Expires={expire_timestamp}"
            f"&Signature={encoded_signature}"
            f"&security-token={urllib.parse.quote(self._config.sts_token, safe='')}"
        )
        
        return url
    
    def get_public_url(self, object_key: str) -> str:
        """
        获取公开访问 URL（需要 bucket 设置为公开读）
        
        Args:
            object_key: 对象键
            
        Returns:
            公开 URL
        """
        self._ensure_config()
        
        if object_key.startswith(self._config.path):
            full_key = object_key
        else:
            full_key = self._get_full_key(object_key)
        
        return f"{self._get_oss_host()}/{full_key}"
    
    def delete_object(self, object_key: str) -> None:
        """
        删除 OSS 对象
        
        Args:
            object_key: 对象键
        """
        self._ensure_config()
        
        if object_key.startswith(self._config.path):
            full_key = object_key
        else:
            full_key = self._get_full_key(object_key)
        
        headers = self._sign_request(method="DELETE", object_key=full_key)
        url = f"{self._get_oss_host()}/{full_key}"
        
        logger.info(f"Deleting from OSS: {full_key}")
        response = self._http_client.delete(url, headers=headers)
        
        if response.status_code not in (200, 204):
            logger.warning(f"OSS delete may have failed: {response.status_code}")
    
    def object_exists(self, object_key: str) -> bool:
        """
        检查对象是否存在
        
        Args:
            object_key: 对象键
            
        Returns:
            是否存在
        """
        self._ensure_config()
        
        if object_key.startswith(self._config.path):
            full_key = object_key
        else:
            full_key = self._get_full_key(object_key)
        
        headers = self._sign_request(method="HEAD", object_key=full_key)
        url = f"{self._get_oss_host()}/{full_key}"
        
        try:
            response = self._http_client.head(url, headers=headers)
            return response.status_code == 200
        except Exception:
            return False


# 单例实例
_oss_client: Optional[AliyunOSSClient] = None


def get_oss_client() -> AliyunOSSClient:
    """获取阿里云 OSS 客户端单例"""
    global _oss_client
    if _oss_client is None:
        _oss_client = AliyunOSSClient()
    return _oss_client

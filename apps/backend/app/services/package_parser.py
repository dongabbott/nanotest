"""App package parsing service for APK and IPA files."""
import hashlib
import io
import os
import plistlib
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class AppPackageInfo:
    """Parsed app package information."""
    platform: str  # android or ios
    package_name: str  # com.example.app or bundle identifier
    app_name: Optional[str] = None
    version_name: str = "1.0.0"
    version_code: Optional[int] = None  # Android only
    build_number: Optional[str] = None  # iOS only
    
    # Android specific
    min_sdk_version: Optional[int] = None
    target_sdk_version: Optional[int] = None
    app_activity: Optional[str] = None
    
    # iOS specific
    minimum_os_version: Optional[str] = None
    supported_platforms: Optional[list[str]] = None
    
    # Common
    permissions: Optional[list[str]] = None
    icon_data: Optional[bytes] = None
    extra_metadata: dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_metadata is None:
            self.extra_metadata = {}


class AXMLParser:
    """Simple parser for Android binary XML (AndroidManifest.xml)."""
    
    # Resource types
    RES_NULL_TYPE = 0x0000
    RES_STRING_POOL_TYPE = 0x0001
    RES_TABLE_TYPE = 0x0002
    RES_XML_TYPE = 0x0003
    RES_XML_START_NAMESPACE_TYPE = 0x0100
    RES_XML_END_NAMESPACE_TYPE = 0x0101
    RES_XML_START_ELEMENT_TYPE = 0x0102
    RES_XML_END_ELEMENT_TYPE = 0x0103
    RES_XML_CDATA_TYPE = 0x0104
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.string_pool = []
        self.package_name = None
        self.version_name = None
        self.version_code = None
        self.min_sdk = None
        self.target_sdk = None
        self.app_name = None
        self.main_activity = None
        self.permissions = []
        self._current_element = None
        self._in_activity = False
        self._activity_name = None
        self._has_main_action = False
        self._has_launcher_category = False
        
    def parse(self):
        """Parse the binary XML."""
        try:
            if len(self.data) < 8:
                logger.warning("AXML data too small")
                return
            
            chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", self.data, 0)
            if chunk_type != self.RES_XML_TYPE:
                logger.warning(f"Invalid AXML type: {hex(chunk_type)}")
                return
            if header_size < 8 or chunk_size < header_size or chunk_size > len(self.data):
                logger.warning("Invalid AXML header")
                return
            
            self.pos = header_size
            
            while self.pos + 8 <= len(self.data):
                start = self.pos
                chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", self.data, start)
                
                # Prevent infinite loop and invalid chunks
                if header_size < 8 or chunk_size < header_size:
                    logger.warning(f"Invalid chunk header: header_size={header_size}, chunk_size={chunk_size}")
                    break
                
                # Check if we have enough data for this chunk
                if start + chunk_size > len(self.data):
                    logger.warning("Chunk extends beyond data")
                    break
                
                if chunk_type == self.RES_STRING_POOL_TYPE:
                    self._parse_string_pool(start, header_size, chunk_size)
                elif chunk_type == self.RES_XML_START_ELEMENT_TYPE:
                    self._parse_start_element(start, header_size, chunk_size)
                elif chunk_type == self.RES_XML_END_ELEMENT_TYPE:
                    self._parse_end_element(start, header_size, chunk_size)
                
                self.pos = start + chunk_size
                
        except Exception as e:
            logger.warning(f"AXML parse error: {e}")
    
    def _parse_string_pool(self, start: int, header_size: int, chunk_size: int):
        if header_size < 28 or start + header_size > len(self.data):
            return

        string_count, style_count, flags, strings_start, styles_start = struct.unpack_from(
            "<IIIII", self.data, start + 8
        )
        is_utf8 = (flags & (1 << 8)) != 0

        offsets_start = start + header_size
        offsets_end = offsets_start + string_count * 4
        chunk_end = start + chunk_size
        if offsets_end > chunk_end:
            return

        offsets = []
        for i in range(string_count):
            offsets.append(struct.unpack_from("<I", self.data, offsets_start + i * 4)[0])

        strings_abs_start = start + strings_start
        if strings_abs_start >= chunk_end:
            return

        def read_length8(pos: int) -> tuple[int, int]:
            first = self.data[pos]
            if first & 0x80:
                return (((first & 0x7F) << 8) | self.data[pos + 1]), pos + 2
            return first, pos + 1

        def read_length16(pos: int) -> tuple[int, int]:
            first = struct.unpack_from("<H", self.data, pos)[0]
            if first & 0x8000:
                second = struct.unpack_from("<H", self.data, pos + 2)[0]
                return (((first & 0x7FFF) << 16) | second), pos + 4
            return first, pos + 2

        for offset in offsets:
            str_start = strings_abs_start + offset
            if str_start >= chunk_end:
                self.string_pool.append("")
                continue
            try:
                if is_utf8:
                    _, str_start = read_length8(str_start)
                    byte_len, str_start = read_length8(str_start)
                    if str_start + byte_len > chunk_end:
                        self.string_pool.append("")
                        continue
                    s = self.data[str_start : str_start + byte_len].decode("utf-8", errors="replace")
                else:
                    str_len, str_start = read_length16(str_start)
                    bytes_len = str_len * 2
                    if str_start + bytes_len > chunk_end:
                        self.string_pool.append("")
                        continue
                    s = self.data[str_start : str_start + bytes_len].decode("utf-16-le", errors="replace")
                self.string_pool.append(s)
            except Exception:
                self.string_pool.append("")
    
    def _get_string(self, index):
        """Get string from pool by index."""
        if 0 <= index < len(self.string_pool):
            return self.string_pool[index]
        return ""
    
    def _parse_start_element(self, start: int, header_size: int, chunk_size: int):
        if start + 36 > len(self.data):
            return

        ns_idx, name_idx = struct.unpack_from("<II", self.data, start + 16)
        attr_start, attr_size, attr_count = struct.unpack_from("<HHH", self.data, start + 24)
        
        element_name = self._get_string(name_idx)
        self._current_element = element_name
        
        # Parse attributes
        attrs = {}
        attr_pos = start + 16 + attr_start
        chunk_end = start + chunk_size
        
        # Validate we have enough space for all attributes (20 bytes each)
        if attr_pos + attr_count * 20 > chunk_end:
            attr_count = max(0, (chunk_end - attr_pos) // 20)
        
        for i in range(attr_count):
            if attr_pos + 20 > len(self.data):
                break
            ns, name, raw_value, value_size, _, value_type, value_data = struct.unpack(
                '<IIIHBBI', self.data[attr_pos:attr_pos+20]
            )
            attr_name = self._get_string(name)
            
            # Get attribute value
            if value_type == 0x03:  # String
                if raw_value != 0xFFFFFFFF:
                    attr_value = self._get_string(raw_value)
                else:
                    attr_value = self._get_string(value_data)
            elif value_type == 0x10:  # Int
                attr_value = value_data
            elif value_type == 0x01:  # Reference
                attr_value = f"@{value_data:08x}"
            else:
                attr_value = value_data
            
            attrs[attr_name] = attr_value
            attr_pos += 20
        
        # Extract relevant info
        if element_name == "manifest":
            self.package_name = attrs.get("package")
            self.version_code = attrs.get("versionCode")
            self.version_name = attrs.get("versionName")
        elif element_name == "uses-sdk":
            if "minSdkVersion" in attrs:
                self.min_sdk = attrs["minSdkVersion"]
            if "targetSdkVersion" in attrs:
                self.target_sdk = attrs["targetSdkVersion"]
        elif element_name == "uses-permission":
            perm = attrs.get("name", "")
            if perm:
                self.permissions.append(perm)
        elif element_name == "activity":
            self._in_activity = True
            self._activity_name = attrs.get("name")
            self._has_main_action = False
            self._has_launcher_category = False
        elif element_name == "action" and self._in_activity:
            if attrs.get("name") == "android.intent.action.MAIN":
                self._has_main_action = True
        elif element_name == "category" and self._in_activity:
            if attrs.get("name") == "android.intent.category.LAUNCHER":
                self._has_launcher_category = True
        elif element_name == "application":
            label = attrs.get("label")
            if label and not str(label).startswith("@"):
                self.app_name = label

    def _parse_end_element(self, start: int, header_size: int, chunk_size: int):
        if start + 24 > len(self.data):
            return
        
        ns_idx, name_idx = struct.unpack_from("<II", self.data, start + 16)
        element_name = self._get_string(name_idx)
        
        if element_name == "activity":
            if self._has_main_action and self._has_launcher_category and self._activity_name:
                self.main_activity = self._activity_name
            self._in_activity = False
            self._activity_name = None


class APKParser:
    """Parser for Android APK files."""
    
    @staticmethod
    def parse(file_data: bytes) -> AppPackageInfo:
        """Parse an APK file and extract metadata."""
        try:
            from androguard.core.bytecodes.apk import APK
        except ImportError:
            logger.warning("androguard not installed, using fallback APK parsing")
            return APKParser._parse_fallback(file_data)
        
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp_file:
            tmp_file.write(file_data)
            tmp_path = tmp_file.name
        
        try:
            apk = APK(tmp_path, skip_analysis=True)
            
            # Extract main activity
            main_activity = None
            try:
                main_activity = apk.get_main_activity()
            except Exception:
                main_activity = None
            
            # Extract permissions
            try:
                permissions = list(apk.get_permissions() or [])
            except Exception:
                permissions = []
            
            # Extract icon
            icon_data = None
            try:
                icon_file = apk.get_app_icon()
                if icon_file:
                    icon_data = apk.get_file(icon_file)
            except Exception as e:
                logger.warning(f"Failed to extract icon: {e}")
            
            # Build extra metadata
            extra: dict[str, Any] = {"parse_method": "androguard"}
            try:
                extra["uses_features"] = list(apk.get_features() or [])
            except Exception:
                extra["uses_features"] = []
            try:
                extra["libraries"] = list(apk.get_libraries() or [])
            except Exception:
                extra["libraries"] = []
            
            try:
                package_name = apk.get_package() or "unknown"
            except Exception:
                package_name = "unknown"
            try:
                app_name = apk.get_app_name() or None
            except Exception:
                app_name = None
            try:
                version_name = apk.get_androidversion_name() or "1.0.0"
            except Exception:
                version_name = "1.0.0"
            try:
                version_code = int(apk.get_androidversion_code()) if apk.get_androidversion_code() is not None else None
            except Exception:
                version_code = None
            try:
                min_sdk = int(apk.get_min_sdk_version()) if apk.get_min_sdk_version() is not None else None
            except Exception:
                min_sdk = None
            try:
                target_sdk = int(apk.get_target_sdk_version()) if apk.get_target_sdk_version() is not None else None
            except Exception:
                target_sdk = None

            if package_name == "unknown" or not version_name or (not app_name and not main_activity and not permissions):
                fallback = APKParser._parse_fallback(file_data)
                if package_name == "unknown" and fallback.package_name:
                    package_name = fallback.package_name
                if (not version_name or version_name == "1.0.0") and fallback.version_name:
                    version_name = fallback.version_name
                if version_code is None and fallback.version_code is not None:
                    version_code = fallback.version_code
                if min_sdk is None and fallback.min_sdk_version is not None:
                    min_sdk = fallback.min_sdk_version
                if target_sdk is None and fallback.target_sdk_version is not None:
                    target_sdk = fallback.target_sdk_version
                if app_name is None and fallback.app_name:
                    app_name = fallback.app_name
                if main_activity is None and fallback.app_activity:
                    main_activity = fallback.app_activity
                if not permissions and fallback.permissions:
                    permissions = list(fallback.permissions)
                if icon_data is None and fallback.icon_data:
                    icon_data = fallback.icon_data
                extra["fallback_merge"] = True

            return AppPackageInfo(
                platform="android",
                package_name=package_name,
                app_name=app_name,
                version_name=version_name,
                version_code=version_code,
                min_sdk_version=min_sdk,
                target_sdk_version=target_sdk,
                app_activity=main_activity,
                permissions=permissions or None,
                icon_data=icon_data,
                extra_metadata=extra,
            )
        except Exception as e:
            # Handle androguard parsing errors (e.g., "res1 must be zero!" for newer APKs)
            logger.warning(f"androguard failed to parse APK: {e}, using fallback parser")
            return APKParser._parse_fallback(file_data)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    
    @staticmethod
    def _parse_fallback(file_data: bytes) -> AppPackageInfo:
        """Fallback APK parsing using basic ZIP inspection and AXML parser."""
        package_name = "unknown"
        version_name = "1.0.0"
        version_code = None
        min_sdk = None
        target_sdk = None
        app_name = None
        main_activity = None
        permissions = []
        icon_data = None
        
        try:
            with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
                # Parse AndroidManifest.xml
                if "AndroidManifest.xml" in zf.namelist():
                    manifest_data = zf.read("AndroidManifest.xml")
                    parser = AXMLParser(manifest_data)
                    parser.parse()
                    
                    if parser.package_name:
                        package_name = parser.package_name
                    if parser.version_name:
                        version_name = parser.version_name
                    if parser.version_code:
                        try:
                            version_code = int(parser.version_code)
                        except Exception:
                            version_code = None
                    if parser.min_sdk:
                        try:
                            min_sdk = int(parser.min_sdk)
                        except Exception:
                            min_sdk = None
                    if parser.target_sdk:
                        try:
                            target_sdk = int(parser.target_sdk)
                        except Exception:
                            target_sdk = None
                    if parser.app_name:
                        app_name = parser.app_name
                    if parser.main_activity:
                        main_activity = parser.main_activity
                    permissions = parser.permissions
                
                # Try to extract icon
                icon_patterns = [
                    "res/mipmap-xxxhdpi-v4/ic_launcher.png",
                    "res/mipmap-xxhdpi-v4/ic_launcher.png",
                    "res/mipmap-xhdpi-v4/ic_launcher.png",
                    "res/drawable-xxxhdpi-v4/ic_launcher.png",
                    "res/drawable-xxhdpi-v4/ic_launcher.png",
                    "res/drawable-xhdpi-v4/ic_launcher.png",
                ]
                for pattern in icon_patterns:
                    if pattern in zf.namelist():
                        try:
                            icon_data = zf.read(pattern)
                            break
                        except Exception:
                            continue
                
                # If no exact match, try to find any launcher icon
                if not icon_data:
                    for name in zf.namelist():
                        if "ic_launcher" in name and name.endswith(".png"):
                            try:
                                icon_data = zf.read(name)
                                break
                            except Exception:
                                continue
                                
        except Exception as e:
            logger.warning(f"Fallback APK parsing error: {e}")
        
        return AppPackageInfo(
            platform="android",
            package_name=package_name,
            app_name=app_name,
            version_name=version_name,
            version_code=version_code,
            min_sdk_version=min_sdk,
            target_sdk_version=target_sdk,
            app_activity=main_activity,
            permissions=permissions if permissions else None,
            icon_data=icon_data,
            extra_metadata={"parse_method": "fallback"},
        )


class IPAParser:
    """Parser for iOS IPA files."""
    
    @staticmethod
    def parse(file_data: bytes) -> AppPackageInfo:
        """Parse an IPA file and extract metadata."""
        with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
            # Find the .app directory inside Payload/
            app_dir = None
            info_plist_path = None
            
            for name in zf.namelist():
                if name.startswith("Payload/") and name.endswith(".app/Info.plist"):
                    info_plist_path = name
                    app_dir = name.rsplit("/Info.plist", 1)[0]
                    break
            
            if not info_plist_path:
                raise ValueError("Invalid IPA: No Info.plist found in Payload/*.app/")
            
            # Parse Info.plist
            with zf.open(info_plist_path) as plist_file:
                try:
                    plist_data = plistlib.load(plist_file)
                except Exception:
                    # Try reading as bytes and parsing
                    plist_file.seek(0)
                    plist_bytes = plist_file.read()
                    plist_data = plistlib.loads(plist_bytes)
            
            # Extract basic info
            bundle_id = plist_data.get("CFBundleIdentifier", "unknown")
            app_name = plist_data.get("CFBundleDisplayName") or plist_data.get("CFBundleName", "")
            version_name = plist_data.get("CFBundleShortVersionString", "1.0.0")
            build_number = plist_data.get("CFBundleVersion", "1")
            minimum_os = plist_data.get("MinimumOSVersion")
            
            # Supported platforms
            supported_platforms = plist_data.get("CFBundleSupportedPlatforms", [])
            device_family = plist_data.get("UIDeviceFamily", [])
            device_names = []
            for family in device_family:
                if family == 1:
                    device_names.append("iPhone")
                elif family == 2:
                    device_names.append("iPad")
            
            # Try to extract icon
            icon_data = None
            icon_files = plist_data.get("CFBundleIcons", {}).get("CFBundlePrimaryIcon", {}).get("CFBundleIconFiles", [])
            if not icon_files:
                icon_files = plist_data.get("CFBundleIconFiles", [])
            
            if icon_files and app_dir:
                for icon_name in reversed(icon_files):  # Try largest first
                    for suffix in ["@3x.png", "@2x.png", ".png", ""]:
                        icon_path = f"{app_dir}/{icon_name}{suffix}"
                        try:
                            if icon_path in zf.namelist():
                                icon_data = zf.read(icon_path)
                                break
                        except Exception:
                            continue
                    if icon_data:
                        break
            
            # Extract entitlements and other metadata
            extra = {
                "executable": plist_data.get("CFBundleExecutable"),
                "bundle_name": plist_data.get("CFBundleName"),
                "device_family": device_names,
                "orientation": plist_data.get("UISupportedInterfaceOrientations", []),
                "requires_fullscreen": plist_data.get("UIRequiresFullScreen", False),
                "background_modes": plist_data.get("UIBackgroundModes", []),
                "url_schemes": IPAParser._extract_url_schemes(plist_data),
            }
            
            return AppPackageInfo(
                platform="ios",
                package_name=bundle_id,
                app_name=app_name,
                version_name=version_name,
                build_number=build_number,
                minimum_os_version=minimum_os,
                supported_platforms=supported_platforms or device_names,
                icon_data=icon_data,
                extra_metadata=extra,
            )
    
    @staticmethod
    def _extract_url_schemes(plist_data: dict) -> list[str]:
        """Extract URL schemes from plist."""
        schemes = []
        url_types = plist_data.get("CFBundleURLTypes", [])
        for url_type in url_types:
            schemes.extend(url_type.get("CFBundleURLSchemes", []))
        return schemes


class AppPackageParser:
    """Main parser that handles both APK and IPA files."""
    
    @staticmethod
    def parse(file_data: bytes, filename: str) -> AppPackageInfo:
        """
        Parse an app package file and extract metadata.
        
        Args:
            file_data: Raw bytes of the package file
            filename: Original filename to determine type
            
        Returns:
            AppPackageInfo with parsed metadata
            
        Raises:
            ValueError: If file type is not supported
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith(".apk"):
            return APKParser.parse(file_data)
        elif filename_lower.endswith(".ipa"):
            return IPAParser.parse(file_data)
        else:
            raise ValueError(f"Unsupported file type: {filename}. Only .apk and .ipa files are supported.")
    
    @staticmethod
    def calculate_hash(file_data: bytes) -> str:
        """Calculate SHA256 hash of file data."""
        return hashlib.sha256(file_data).hexdigest()
    
    @staticmethod
    def detect_platform(filename: str) -> str:
        """Detect platform from filename."""
        filename_lower = filename.lower()
        if filename_lower.endswith(".apk"):
            return "android"
        elif filename_lower.endswith(".ipa"):
            return "ios"
        else:
            raise ValueError(f"Cannot detect platform from filename: {filename}")

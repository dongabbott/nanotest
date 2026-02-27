"""Appium client integration for mobile automation."""
import base64
from typing import Any, Optional

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy

from app.core.config import settings


class AppiumClient:
    """Appium client wrapper for mobile automation."""

    def __init__(
        self,
        platform: str,
        device_udid: str,
        platform_version: str,
        server_url: Optional[str] = None,
        existing_session_id: Optional[str] = None,
        app_path: Optional[str] = None,
        app_package: Optional[str] = None,
        app_activity: Optional[str] = None,
        bundle_id: Optional[str] = None,
    ):
        self.platform = platform.lower()
        self.device_udid = device_udid
        self.platform_version = platform_version
        self.server_url = server_url or settings.appium_server_url
        self.existing_session_id = existing_session_id
        self.app_path = app_path
        self.app_package = app_package
        self.app_activity = app_activity
        self.bundle_id = bundle_id
        self._driver: Optional[webdriver.Remote] = None
        self._started_new_session = False

    def _get_options(self) -> Any:
        """Get Appium options based on platform."""
        if self.platform == "android":
            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.device_name = self.device_udid
            options.udid = self.device_udid
            options.platform_version = self.platform_version
            options.automation_name = "UiAutomator2"
            options.new_command_timeout = settings.appium_session_timeout
            
            if self.app_path:
                options.app = self.app_path
            if self.app_package:
                options.app_package = self.app_package
            if self.app_activity:
                options.app_activity = self.app_activity
            
            return options
        
        elif self.platform == "ios":
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.device_name = self.device_udid
            options.udid = self.device_udid
            options.platform_version = self.platform_version
            options.automation_name = "XCUITest"
            options.new_command_timeout = settings.appium_session_timeout
            
            if self.app_path:
                options.app = self.app_path
            if self.bundle_id:
                options.bundle_id = self.bundle_id
            
            return options
        
        else:
            raise ValueError(f"Unsupported platform: {self.platform}")

    def start_session(self) -> None:
        """Start an Appium session."""
        if self.existing_session_id:
            from appium.options.common.base import AppiumOptions
            from appium.webdriver.webdriver import WebDriver as AppiumWebDriver

            class AttachedWebDriver(AppiumWebDriver):
                def __init__(self, command_executor: str, session_id: str):
                    self._attached_session_id = session_id
                    super().__init__(
                        command_executor=command_executor,
                        options=AppiumOptions(),
                        direct_connection=False,
                    )

                def start_session(self, capabilities, browser_profile=None) -> None:
                    self.session_id = self._attached_session_id
                    self.caps = {"attached": True}
                    self.w3c = True

            self._driver = AttachedWebDriver(self.server_url, self.existing_session_id)
            self._started_new_session = False
            return

        options = self._get_options()
        self._driver = webdriver.Remote(
            command_executor=self.server_url,
            options=options,
        )
        self._started_new_session = True

    def stop_session(self) -> None:
        """Stop the Appium session."""
        if self._driver and self._started_new_session:
            self._driver.quit()
            self._driver = None

    @property
    def driver(self) -> webdriver.Remote:
        """Get the Appium driver."""
        if not self._driver:
            raise RuntimeError("Appium session not started")
        return self._driver

    # ==========================================================================
    # Element Finding
    # ==========================================================================

    def _get_by(self, locator_type: str):
        by_map = {
            "id": AppiumBy.ID,
            "xpath": AppiumBy.XPATH,
            "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
            "class_name": AppiumBy.CLASS_NAME,
            "name": AppiumBy.NAME,
            "css": AppiumBy.CSS_SELECTOR,
            "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
            "ios_predicate": AppiumBy.IOS_PREDICATE,
            "ios_class_chain": AppiumBy.IOS_CLASS_CHAIN,
        }
        by = by_map.get(locator_type.lower())
        if not by:
            raise ValueError(f"Unknown locator type: {locator_type}")
        return by

    def find_element(self, locator_type: str, locator_value: str):
        """Find an element using various locator strategies."""
        by = self._get_by(locator_type)
        return self.driver.find_element(by, locator_value)

    def find_elements(self, locator_type: str, locator_value: str):
        """Find multiple elements using various locator strategies."""
        by = self._get_by(locator_type)
        return self.driver.find_elements(by, locator_value)

    # ==========================================================================
    # Actions
    # ==========================================================================

    def _new_finger_actions(self):
        """Create a W3C touch ActionBuilder in a version-tolerant way."""
        try:
            from selenium.webdriver.common.actions.action_builder import ActionBuilder
            from selenium.webdriver.common.actions.pointer_input import PointerInput

            # Selenium 4 expects kind to be the string 'touch'. Some environments
            # don't expose PointerInput.TOUCH.
            finger = PointerInput("touch", "finger")
            return ActionBuilder(self.driver, mouse=finger)
        except Exception:
            return None

    def tap_xy(self, x: int, y: int) -> None:
        """Tap at a screen coordinate (x, y)."""
        actions = self._new_finger_actions()
        if actions:
            actions.pointer_action.move_to_location(x, y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(0.05)
            actions.pointer_action.pointer_up()
            actions.perform()
            return

        # Fallback (older clients)
        try:
            from appium.webdriver.common.touch_action import TouchAction
            TouchAction(self.driver).tap(x=x, y=y).perform()
        except Exception as e:
            raise RuntimeError(f"tap_xy not supported: {e}")

    def double_tap(self, locator_type: str, locator_value: str) -> None:
        """Double-tap on an element."""
        element = self.find_element(locator_type, locator_value)
        rect = element.rect
        x = int(rect["x"] + rect["width"] / 2)
        y = int(rect["y"] + rect["height"] / 2)

        actions = self._new_finger_actions()
        if not actions:
            # Fallback to two taps
            self.tap_xy(x, y)
            self.tap_xy(x, y)
            return

        for _ in range(2):
            actions.pointer_action.move_to_location(x, y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(0.05)
            actions.pointer_action.pointer_up()
            actions.pointer_action.pause(0.08)
        actions.perform()

    def input_text(self, locator_type: str, locator_value: str, text: str) -> None:
        """Input text into an element."""
        element = self.find_element(locator_type, locator_value)
        element.clear()
        element.send_keys(text)

    def clear_text(self, locator_type: str, locator_value: str) -> None:
        """Clear text from an element."""
        element = self.find_element(locator_type, locator_value)
        element.clear()

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: int = 500,
    ) -> None:
        """Perform a swipe gesture using W3C actions (fallback if needed)."""
        actions = self._new_finger_actions()
        if actions:
            actions.pointer_action.move_to_location(start_x, start_y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(max(duration, 50) / 1000.0)
            actions.pointer_action.move_to_location(end_x, end_y)
            actions.pointer_action.pointer_up()
            actions.perform()
            return

        # Fallback
        try:
            self.driver.swipe(start_x, start_y, end_x, end_y, duration)
        except Exception as e:
            raise RuntimeError(f"swipe not supported: {e}")

    def scroll(self, direction: str = "down") -> None:
        """Scroll screen up/down."""
        direction = (direction or "down").lower()
        if direction == "up":
            self.scroll_up()
        else:
            self.scroll_down()

    def scroll_down(self) -> None:
        """Scroll down on the screen."""
        size = self.driver.get_window_size()
        start_x = size["width"] // 2
        start_y = int(size["height"] * 0.8)
        end_y = int(size["height"] * 0.2)
        self.swipe(start_x, start_y, start_x, end_y)

    def scroll_up(self) -> None:
        """Scroll up on the screen."""
        size = self.driver.get_window_size()
        start_x = size["width"] // 2
        start_y = int(size["height"] * 0.2)
        end_y = int(size["height"] * 0.8)
        self.swipe(start_x, start_y, start_x, end_y)

    def long_press(
        self,
        locator_type: str,
        locator_value: str,
        duration: int = 1000,
    ) -> None:
        """Long press on an element."""
        element = self.find_element(locator_type, locator_value)
        rect = element.rect
        x = int(rect["x"] + rect["width"] / 2)
        y = int(rect["y"] + rect["height"] / 2)

        actions = self._new_finger_actions()
        if actions:
            actions.pointer_action.move_to_location(x, y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(max(duration, 200) / 1000.0)
            actions.pointer_action.pointer_up()
            actions.perform()
            return

        # Fallback
        try:
            from appium.webdriver.common.touch_action import TouchAction
            TouchAction(self.driver).long_press(x=x, y=y, duration=duration).release().perform()
        except Exception as e:
            raise RuntimeError(f"long_press not supported: {e}")

    def back(self) -> None:
        """Press the back button."""
        self.driver.back()

    def home(self) -> None:
        """Press the home button (Android only)."""
        if self.platform == "android":
            self.driver.press_keycode(3)  # KEYCODE_HOME

    def hide_keyboard(self) -> None:
        """Hide the on-screen keyboard if present."""
        try:
            self.driver.hide_keyboard()
        except Exception:
            # Not all drivers/platforms support it consistently
            pass

    # ==========================================================================
    # App Management
    # ==========================================================================

    def launch_app(self, app_id: Optional[str] = None) -> None:
        """Launch the app."""
        if app_id:
            self.driver.activate_app(app_id)
        else:
            self.driver.activate_app(
                self.bundle_id if self.platform == "ios" else self.app_package
            )

    def close_app(self, app_id: Optional[str] = None) -> None:
        """Close the app."""
        if app_id:
            self.driver.terminate_app(app_id)
        else:
            self.driver.terminate_app(
                self.bundle_id if self.platform == "ios" else self.app_package
            )

    def reset_app(self) -> None:
        """Reset the app state."""
        app_id = self.bundle_id if self.platform == "ios" else self.app_package
        if app_id:
            self.driver.terminate_app(app_id)
            self.driver.activate_app(app_id)

    # ==========================================================================
    # Screenshots & State
    # ==========================================================================

    def take_screenshot(self) -> bytes:
        """Take a screenshot and return as bytes."""
        screenshot_base64 = self.driver.get_screenshot_as_base64()
        return base64.b64decode(screenshot_base64)

    def get_page_source(self) -> str:
        """Get the current page source (XML hierarchy)."""
        return self.driver.page_source

    def get_window_size(self) -> dict[str, int]:
        """Get the window size."""
        return self.driver.get_window_size()

    # ==========================================================================
    # Waits & Assertions
    # ==========================================================================

    def wait_for_element(
        self,
        locator_type: str,
        locator_value: str,
        timeout: int = 10,
    ):
        """Wait for an element to be present."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by = self._get_by(locator_type)
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, locator_value)))

    def wait_for_visible(
        self,
        locator_type: str,
        locator_value: str,
        timeout: int = 10,
    ):
        """Wait for an element to be visible."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by = self._get_by(locator_type)
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.visibility_of_element_located((by, locator_value)))

    def wait_for_clickable(
        self,
        locator_type: str,
        locator_value: str,
        timeout: int = 10,
    ):
        """Wait for an element to be clickable."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by = self._get_by(locator_type)
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable((by, locator_value)))

    def wait_invisible(
        self,
        locator_type: str,
        locator_value: str,
        timeout: int = 10,
    ) -> bool:
        """Wait until an element becomes invisible or disappears."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by = self._get_by(locator_type)
        wait = WebDriverWait(self.driver, timeout)
        return bool(wait.until(EC.invisibility_of_element_located((by, locator_value))))

    def element_exists(self, locator_type: str, locator_value: str) -> bool:
        """Check if an element exists."""
        # Do not swallow invalid locator types.
        self._get_by(locator_type)
        try:
            elements = self.find_elements(locator_type, locator_value)
            return len(elements) > 0
        except Exception:
            return False

    def get_element_text(self, locator_type: str, locator_value: str) -> str:
        """Get the text of an element."""
        element = self.find_element(locator_type, locator_value)
        return element.text

    def get_element_attribute(
        self,
        locator_type: str,
        locator_value: str,
        attribute: str,
    ) -> Optional[str]:
        """Get an attribute value from an element."""
        element = self.find_element(locator_type, locator_value)
        return element.get_attribute(attribute)

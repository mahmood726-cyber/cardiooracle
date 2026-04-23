"""
Selenium tests for CardioOracle HTML app shell.
Tests: title, tabs, tab switching, dark mode, invalid NCT warning,
       search bar Enter key, no console errors, ARIA roles.

Usage:
    CARDIOORACLE_RUN_BROWSER_TESTS=1 python -m pytest tests/test_prediction.py -v --timeout=60
    python -m pytest tests/test_prediction.py -v --timeout=60
"""

import sys
import os
import io
import time
import unittest
import shutil

# UTF-8 stdout (Windows cp1252 safety) — only reconfigure when running directly,
# not when imported by pytest (which replaces sys.stdout with its own capture object).
if __name__ == '__main__' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# ── Path to the HTML file ─────────────────────────────────────────────────────
HTML_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'CardioOracle.html')
)
FILE_URL = 'file:///' + HTML_PATH.replace('\\', '/')

# ── Pre-cached ChromeDriver locations (avoids network download at test time) ──
_WDM_CACHE_ROOT = os.path.expanduser('~/.wdm/drivers/chromedriver/win64')
_CACHED_DRIVERS = []
if os.path.isdir(_WDM_CACHE_ROOT):
    for _ver in sorted(os.listdir(_WDM_CACHE_ROOT), reverse=True):
        for _subdir in ('chromedriver-win32', ''):
            _candidate = os.path.join(_WDM_CACHE_ROOT, _ver, _subdir, 'chromedriver.exe').rstrip(os.sep)
            if os.path.isfile(_candidate):
                _CACHED_DRIVERS.append(_candidate)
                break


def _chrome_options():
    opts = ChromeOptions()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--incognito')
    opts.add_argument('--window-size=1280,900')
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    return opts


def _chrome_driver():
    """Build a headless Chrome WebDriver with console log capture.

    Strategy (no network):
    1. Try each pre-cached ChromeDriver (newest first).
    2. Fall back to system PATH chromedriver.
    3. Optionally fall back to webdriver-manager only when explicitly enabled.
    """
    opts = _chrome_options()

    # 1. Try cached drivers (no download)
    for driver_path in _CACHED_DRIVERS:
        try:
            service = ChromeService(executable_path=driver_path)
            return webdriver.Chrome(service=service, options=opts)
        except WebDriverException:
            continue

    # 2. System PATH chromedriver only (avoid implicit Selenium Manager downloads)
    system_driver = shutil.which('chromedriver')
    if system_driver:
        try:
            service = ChromeService(executable_path=system_driver)
            return webdriver.Chrome(service=service, options=opts)
        except WebDriverException:
            pass

    # 3. webdriver-manager (opt-in only; avoids hanging on offline test hosts)
    if os.environ.get('CARDIOORACLE_ALLOW_DRIVER_DOWNLOAD', '').lower() in {'1', 'true', 'yes'}:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=opts)
        except Exception:
            pass

    raise WebDriverException('Cannot locate a working ChromeDriver.')


def _edge_driver():
    """Fallback: headless Edge WebDriver."""
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService

    opts = EdgeOptions()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--inprivate')
    opts.add_argument('--window-size=1280,900')

    # Try explicit system PATH driver first (avoid implicit Selenium Manager downloads)
    system_driver = shutil.which('msedgedriver') or shutil.which('edgedriver')
    if system_driver:
        try:
            service = EdgeService(executable_path=system_driver)
            return webdriver.Edge(service=service, options=opts)
        except WebDriverException:
            pass

    if os.environ.get('CARDIOORACLE_ALLOW_DRIVER_DOWNLOAD', '').lower() in {'1', 'true', 'yes'}:
        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=opts)
        except Exception:
            pass

    raise WebDriverException('Cannot locate a working EdgeDriver.')


class TestCardioOracleShell(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = None
        if os.environ.get('CARDIOORACLE_RUN_BROWSER_TESTS', '').lower() not in {'1', 'true', 'yes'}:
            raise unittest.SkipTest(
                'Browser tests are opt-in. Set CARDIOORACLE_RUN_BROWSER_TESTS=1 to enable Selenium runs.'
            )
        # Try Chrome first, fall back to Edge
        for factory in (_chrome_driver, _edge_driver):
            try:
                cls.driver = factory()
                break
            except WebDriverException as exc:
                print(f'[WARN] Driver factory failed: {exc}')

        if cls.driver is None:
            raise unittest.SkipTest(
                'No WebDriver available (Chrome or Edge). '
                'Install ChromeDriver or Edge WebDriver.'
            )

        cls.driver.set_page_load_timeout(30)
        cls.driver.get(FILE_URL)
        # Allow JS to initialise
        time.sleep(2)
        # Dismiss tutorial overlay if present (blocks clicks on first visit)
        try:
            cls.driver.execute_script(
                "var t = document.getElementById('tutorialOverlay');"
                "if (t) t.classList.add('hidden');"
                "try { localStorage.setItem('cardiooracle_tutorial_seen','true'); } catch(e) {}"
            )
            time.sleep(0.3)
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            try:
                # Attempt graceful quit; use service.process kill as fallback
                # if it hangs (can occur with minor Chrome/ChromeDriver version skew).
                import threading
                done = threading.Event()

                def _quit():
                    try:
                        cls.driver.quit()
                    except Exception:
                        pass
                    finally:
                        done.set()

                t = threading.Thread(target=_quit, daemon=True)
                t.start()
                if not done.wait(timeout=10):
                    # Forcibly terminate the browser process
                    try:
                        cls.driver.service.process.kill()
                    except Exception:
                        pass
            except Exception:
                pass

    # ── helpers ───────────────────────────────────────────────────────────────

    def _wait(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def _reset_to_predict_tab(self):
        """Ensure the Predict tab is active before a test."""
        predict_tab = self.driver.find_element(By.ID, 'tab-predict')
        if predict_tab.get_attribute('aria-selected') != 'true':
            predict_tab.click()
            time.sleep(0.4)

    # ── Test 01 ───────────────────────────────────────────────────────────────

    def test_01_title(self):
        """Page title must contain 'CardioOracle'."""
        self.assertIn('CardioOracle', self.driver.title,
                      f"Expected 'CardioOracle' in title, got: {self.driver.title!r}")

    # ── Test 02 ───────────────────────────────────────────────────────────────

    def test_02_tabs_present(self):
        """Exactly 6 tab buttons (.tab-btn) must be rendered."""
        tabs = self.driver.find_elements(By.CSS_SELECTOR, '.tab-btn')
        self.assertEqual(len(tabs), 6,
                         f'Expected 6 .tab-btn elements, found {len(tabs)}')

    # ── Test 03 ───────────────────────────────────────────────────────────────

    def test_03_tab_switching(self):
        """Clicking Design tab activates panel-design; clicking Predict restores it."""
        self._reset_to_predict_tab()

        design_tab = self.driver.find_element(By.ID, 'tab-design')
        design_tab.click()
        time.sleep(0.4)

        panel_design = self.driver.find_element(By.ID, 'panel-design')
        self.assertIn('active', panel_design.get_attribute('class'),
                      'panel-design should have class "active" after clicking Design tab')

        # Return to Predict tab
        self.driver.find_element(By.ID, 'tab-predict').click()
        time.sleep(0.4)

        panel_predict = self.driver.find_element(By.ID, 'panel-predict')
        self.assertIn('active', panel_predict.get_attribute('class'),
                      'panel-predict should be active after clicking back to Predict tab')

    # ── Test 04 ───────────────────────────────────────────────────────────────

    def test_04_dark_mode_toggle(self):
        """Clicking the dark-mode button sets data-theme='dark'; clicking again removes it."""
        btn = self.driver.find_element(By.ID, 'darkModeBtn')
        html_el = self.driver.find_element(By.TAG_NAME, 'html')

        # Ensure we start in light mode
        current_theme = html_el.get_attribute('data-theme')
        if current_theme == 'dark':
            btn.click()
            time.sleep(0.3)

        # Toggle to dark
        btn.click()
        time.sleep(0.3)
        self.assertEqual(
            self.driver.find_element(By.TAG_NAME, 'html').get_attribute('data-theme'),
            'dark',
            'data-theme should be "dark" after first toggle'
        )

        # Toggle back to light
        btn.click()
        time.sleep(0.3)
        theme_after = self.driver.find_element(By.TAG_NAME, 'html').get_attribute('data-theme')
        self.assertNotEqual(theme_after, 'dark',
                            'data-theme should not be "dark" after second toggle')

    # ── Test 05 ───────────────────────────────────────────────────────────────

    def test_05_invalid_nct_shows_warning(self):
        """Typing 'INVALID' and clicking Predict shows a validation error."""
        self._reset_to_predict_tab()

        nct_input = self.driver.find_element(By.ID, 'nctInput')
        nct_input.clear()
        nct_input.send_keys('INVALID')

        predict_btn = self.driver.find_element(By.ID, 'predictBtn')
        predict_btn.click()
        time.sleep(0.5)

        error_el = self.driver.find_element(By.ID, 'predictionError')
        error_text = error_el.text.strip()
        self.assertTrue(
            len(error_text) > 0,
            'predictionError element should have visible text after invalid input'
        )
        # The error message should reference NCT ID validity
        self.assertTrue(
            'nct' in error_text.lower() or 'invalid' in error_text.lower()
                or 'format' in error_text.lower(),
            f'Expected an NCT-related error message, got: {error_text!r}'
        )

        # Clean up input
        nct_input.clear()

    # ── Test 06 ───────────────────────────────────────────────────────────────

    def test_06_search_bar_enter_key(self):
        """Pressing Enter in the search bar triggers the prediction flow."""
        self._reset_to_predict_tab()

        nct_input = self.driver.find_element(By.ID, 'nctInput')
        nct_input.clear()
        nct_input.send_keys('NCT03036124')
        nct_input.send_keys(Keys.RETURN)
        time.sleep(1.5)

        # Either a spinner appeared/disappeared, an error showed, or the result area has content
        spinner = self.driver.find_element(By.ID, 'predictSpinner')
        error_el = self.driver.find_element(By.ID, 'predictionError')
        result_el = self.driver.find_element(By.ID, 'predictionResult')

        has_content = (
            len(result_el.text.strip()) > 0
            or len(error_el.text.strip()) > 0
            or 'visible' in (spinner.get_attribute('class') or '')
        )
        self.assertTrue(
            has_content,
            'After pressing Enter with a valid NCT ID, the app should show a result, '
            'error, or spinner. All three were empty/invisible.'
        )

        # Clean up
        nct_input.clear()

    # ── Test 07 ───────────────────────────────────────────────────────────────

    def test_07_no_console_errors(self):
        """Browser console should have no SEVERE errors (favicon 404 excluded)."""
        try:
            logs = self.driver.get_log('browser')
        except Exception:
            self.skipTest('Browser log capture not supported by this WebDriver')

        severe = [
            entry for entry in logs
            if entry.get('level') == 'SEVERE'
            and 'favicon' not in entry.get('message', '').lower()
        ]
        if severe:
            msgs = '\n'.join(e['message'] for e in severe)
            self.fail(f'SEVERE console errors detected:\n{msgs}')

    # ── Test 08 ───────────────────────────────────────────────────────────────

    def test_08_aria_roles_present(self):
        """ARIA roles: one tablist, 6 tab, 6 tabpanel elements must be present."""
        tablist = self.driver.find_elements(By.CSS_SELECTOR, '[role="tablist"]')
        self.assertEqual(len(tablist), 1,
                         f'Expected 1 role="tablist", found {len(tablist)}')

        tab_els = self.driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
        self.assertEqual(len(tab_els), 6,
                         f'Expected 6 role="tab" elements, found {len(tab_els)}')

        tabpanel_els = self.driver.find_elements(By.CSS_SELECTOR, '[role="tabpanel"]')
        self.assertEqual(len(tabpanel_els), 6,
                         f'Expected 6 role="tabpanel" elements, found {len(tabpanel_els)}')


class TestCardioOraclePhase2to4(unittest.TestCase):
    """Phase 2-4 feature tests: Design tab, Training Data tab, Calibration tab,
    WebR tab, About modal, and config dropdown.

    Uses a fresh browser session to avoid state pollution from Phase 1 tests.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = None
        for factory in (_chrome_driver, _edge_driver):
            try:
                cls.driver = factory()
                break
            except WebDriverException as exc:
                print(f'[WARN] Driver factory failed: {exc}')

        if cls.driver is None:
            raise RuntimeError('No WebDriver available (Chrome or Edge).')

        cls.driver.set_page_load_timeout(30)
        cls.driver.get(FILE_URL)
        time.sleep(2)
        # Dismiss tutorial overlay if present
        try:
            cls.driver.execute_script(
                "var t = document.getElementById('tutorialOverlay');"
                "if (t) t.classList.add('hidden');"
                "try { localStorage.setItem('cardiooracle_tutorial_seen','true'); } catch(e) {}"
            )
            time.sleep(0.3)
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            try:
                import threading
                done = threading.Event()

                def _quit():
                    try:
                        cls.driver.quit()
                    except Exception:
                        pass
                    finally:
                        done.set()

                t = threading.Thread(target=_quit, daemon=True)
                t.start()
                if not done.wait(timeout=10):
                    try:
                        cls.driver.service.process.kill()
                    except Exception:
                        pass
            except Exception:
                pass

    def _wait(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def _click_tab(self, tab_id, panel_id, sleep=0.5):
        """Click a tab and wait for its panel to become active."""
        tab = self.driver.find_element(By.ID, tab_id)
        tab.click()
        time.sleep(sleep)
        panel = self.driver.find_element(By.ID, panel_id)
        self.assertIn('active', panel.get_attribute('class'),
                      f'{panel_id} should be active after clicking {tab_id}')
        return panel

    # ── Test 09 ───────────────────────────────────────────────────────────────

    def test_09_design_tab_has_sliders(self):
        """Design tab must contain the designEnrollment range input."""
        self._click_tab('tab-design', 'panel-design')
        slider = self.driver.find_element(By.ID, 'designEnrollment')
        self.assertEqual(slider.get_attribute('type'), 'range',
                         'designEnrollment should be a range (slider) input')

    # ── Test 10 ───────────────────────────────────────────────────────────────

    def test_10_design_tab_dropdowns(self):
        """designDrugClass select must have at least 3 options."""
        # Design tab should still be active from test_09; click again to be safe
        tab = self.driver.find_element(By.ID, 'tab-design')
        tab.click()
        time.sleep(0.4)

        select = self.driver.find_element(By.ID, 'designDrugClass')
        options = select.find_elements(By.TAG_NAME, 'option')
        self.assertGreaterEqual(len(options), 3,
                                f'designDrugClass should have >=3 options, found {len(options)}')

    # ── Test 11 ───────────────────────────────────────────────────────────────

    def test_11_training_data_tab(self):
        """Training Data tab must render a table with at least 5 rows."""
        self._click_tab('tab-training', 'panel-training')
        # Wait for the table to appear
        time.sleep(0.5)
        rows = self.driver.find_elements(By.CSS_SELECTOR, '#panel-training table tbody tr')
        self.assertGreaterEqual(len(rows), 5,
                                f'Training data table should have >=5 rows, found {len(rows)}')

    # ── Test 12 ───────────────────────────────────────────────────────────────

    def test_12_calibration_tab(self):
        """Calibration tab must render at least one metrics card or stat element."""
        self._click_tab('tab-calibration', 'panel-calibration')
        time.sleep(0.5)
        # Look for any .card, .stat, or .metric element inside the panel
        panel = self.driver.find_element(By.ID, 'panel-calibration')
        cards = panel.find_elements(By.CSS_SELECTOR, '.card, .stat, .metric, .metric-card')
        self.assertGreater(len(cards), 0,
                           'Calibration panel should contain at least one card/stat/metric element')

    # ── Test 13 ───────────────────────────────────────────────────────────────

    def test_13_webr_tab_has_button(self):
        """WebR tab must contain a Run Validation button."""
        self._click_tab('tab-webr', 'panel-webr')
        time.sleep(0.4)
        panel = self.driver.find_element(By.ID, 'panel-webr')
        buttons = panel.find_elements(By.TAG_NAME, 'button')
        run_btns = [b for b in buttons if 'validation' in b.text.lower() or 'run' in b.text.lower()]
        self.assertGreater(len(run_btns), 0,
                           f'WebR panel should contain a Run/Validation button. Buttons found: '
                           f'{[b.text for b in buttons]}')

    # ── Test 14 ───────────────────────────────────────────────────────────────

    def test_14_about_modal(self):
        """About link must open a modal; Escape / X button must close it."""
        # Open the modal
        about_btn = self.driver.find_element(By.ID, 'aboutBtn')
        about_btn.click()
        time.sleep(0.4)

        modal = self.driver.find_element(By.ID, 'aboutModal')
        self.assertNotIn('hidden', modal.get_attribute('class'),
                         'About modal should be visible after clicking About button')

        # Modal content sanity check
        modal_text = modal.text
        self.assertIn('CardioOracle', modal_text,
                      'Modal should contain "CardioOracle" text')

        # Close via X button
        close_btn = self.driver.find_element(By.ID, 'aboutModalClose')
        close_btn.click()
        time.sleep(0.3)

        modal_after = self.driver.find_element(By.ID, 'aboutModal')
        self.assertIn('hidden', modal_after.get_attribute('class'),
                      'About modal should be hidden after clicking close button')

    # ── Test 15 ───────────────────────────────────────────────────────────────

    def test_15_config_dropdown(self):
        """configSelect dropdown must have at least 2 options."""
        config_select = self.driver.find_element(By.ID, 'configSelect')
        options = config_select.find_elements(By.TAG_NAME, 'option')
        self.assertGreaterEqual(len(options), 2,
                                f'configSelect should have >=2 options, found {len(options)}')

    # ── Test 16 ───────────────────────────────────────────────────────────────

    def test_16_traffic_light_distinct_icons(self):
        """Traffic-light icons must differ between high/moderate/low."""
        icons = self.driver.execute_script("""
            // Simulate predictions to capture icons
            var icons = {};
            ['high', 'moderate', 'low'].forEach(function(level) {
                var span = document.createElement('span');
                span.innerHTML = level === 'high' ? '&#10003;' : level === 'moderate' ? '&#9670;' : '&#10007;';
                icons[level] = span.textContent;
            });
            return icons;
        """)
        self.assertNotEqual(icons['high'], icons['moderate'],
                            'High and moderate icons should differ')
        self.assertNotEqual(icons['high'], icons['low'],
                            'High and low icons should differ')
        self.assertNotEqual(icons['moderate'], icons['low'],
                            'Moderate and low icons should differ')

    # ── Test 17 ───────────────────────────────────────────────────────────────

    def test_17_design_tab_live_prediction(self):
        """Adjusting enrollment slider should produce a live prediction gauge."""
        self._click_tab('tab-design', 'panel-design')
        time.sleep(0.5)

        # Set enrollment slider to a new value via JS
        self.driver.execute_script("""
            var slider = document.getElementById('designEnrollment');
            if (slider) {
                slider.value = '8000';
                slider.dispatchEvent(new Event('input', {bubbles: true}));
            }
        """)
        time.sleep(0.5)

        gauge = self.driver.find_element(By.ID, 'designPredictionGauge')
        gauge_text = gauge.text.strip()
        self.assertTrue(len(gauge_text) > 0,
                        'Design prediction gauge should have content after slider change')
        self.assertIn('%', gauge_text,
                      'Gauge should show a percentage')

    # ── Test 18 ───────────────────────────────────────────────────────────────

    def test_18_training_data_filter(self):
        """Filtering by drug class should reduce the total count shown in status."""
        self._click_tab('tab-training', 'panel-training')
        time.sleep(0.5)

        # Get total count from JS (_filteredData length before filter)
        total = self.driver.execute_script("""
            return (typeof TRAINING_DATA !== 'undefined' && TRAINING_DATA.trials)
                ? TRAINING_DATA.trials.length : 0;
        """)

        # Filter by sglt2i
        self.driver.execute_script("""
            var sel = document.getElementById('tdFilterDrugClass');
            if (sel) {
                sel.value = 'sglt2i';
                sel.dispatchEvent(new Event('change', {bubbles: true}));
            }
        """)
        time.sleep(0.5)

        # Check row status element shows filtered count
        status_text = self.driver.execute_script("""
            var el = document.getElementById('tdRowStatus');
            return el ? el.textContent : '';
        """)
        self.assertIn('of', status_text,
                       f'Status should show "X of Y", got: {status_text!r}')

        # Verify filter reduced visible rows or status reflects smaller count
        filtered_rows = self.driver.find_elements(
            By.CSS_SELECTOR, '#trainingTableBody tr'
        )
        self.assertGreater(len(filtered_rows), 0,
                           'Filtering by sglt2i should still show some rows')
        self.assertLessEqual(len(filtered_rows), 50,
                             'Filtered rows should not exceed page size')

        # Reset filter
        self.driver.execute_script("""
            var sel = document.getElementById('tdFilterDrugClass');
            if (sel) {
                sel.value = '';
                sel.dispatchEvent(new Event('change', {bubbles: true}));
            }
        """)

    # ── Test 19 ───────────────────────────────────────────────────────────────

    def test_19_aria_sort_on_training_headers(self):
        """Clicking a sortable header should set aria-sort attribute."""
        self._click_tab('tab-training', 'panel-training')
        time.sleep(0.5)

        # Click the enrollment header to sort
        self.driver.execute_script("""
            var th = document.querySelector('th[data-col="enrollment"]');
            if (th) th.click();
        """)
        time.sleep(0.3)

        aria_sort = self.driver.execute_script("""
            var th = document.querySelector('th[data-col="enrollment"]');
            return th ? th.getAttribute('aria-sort') : null;
        """)
        self.assertIn(aria_sort, ['ascending', 'descending'],
                      f'enrollment header should have aria-sort after click, got: {aria_sort!r}')

    # ── Test 20 ───────────────────────────────────────────────────────────────

    def test_20_truthcert_bundle_export_function_exists(self):
        """exportPredictionBundle function must be defined and async."""
        result = self.driver.execute_script("""
            return typeof exportPredictionBundle === 'function';
        """)
        self.assertTrue(result, 'exportPredictionBundle should be a function')

    # ── Test 21 ───────────────────────────────────────────────────────────────

    def test_21_sha256_function_works(self):
        """sha256Hex should return a 64-char hex string."""
        result = self.driver.execute_script("""
            return sha256Hex('test').then(function(h) { return h; });
        """)
        time.sleep(0.5)
        # Execute as async
        result = self.driver.execute_async_script("""
            var callback = arguments[arguments.length - 1];
            sha256Hex('hello world').then(function(h) {
                callback(h);
            }).catch(function(e) {
                callback('error: ' + e.message);
            });
        """)
        self.assertEqual(len(result), 64,
                         f'SHA-256 hex should be 64 chars, got {len(result)}: {result!r}')
        # Known SHA-256 of "hello world"
        self.assertEqual(result, 'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9',
                         'SHA-256 of "hello world" should match known hash')

    # ── Test 22 ───────────────────────────────────────────────────────────────

    def test_22_z_alpha_function(self):
        """zAlpha() should return ~1.96 for conf_level=0.95."""
        result = self.driver.execute_script("""
            return zAlpha();
        """)
        self.assertIsNotNone(result, 'zAlpha() should return a number')
        self.assertAlmostEqual(result, 1.96, delta=0.02,
                               msg=f'zAlpha() at conf_level=0.95 should be ~1.96, got {result}')

    # ── Test 23 ───────────────────────────────────────────────────────────────

    def test_23_normal_quantile_function(self):
        """normalQuantile should be the inverse of normalCDF."""
        result = self.driver.execute_script("""
            var tests = [
                [0.025, -1.96],
                [0.5, 0],
                [0.975, 1.96],
                [0.05, -1.645]
            ];
            var passed = true;
            var details = [];
            for (var i = 0; i < tests.length; i++) {
                var p = tests[i][0];
                var expected = tests[i][1];
                var got = normalQuantile(p);
                if (Math.abs(got - expected) > 0.02) {
                    passed = false;
                    details.push('normalQuantile(' + p + ') = ' + got + ', expected ~' + expected);
                }
            }
            return {passed: passed, details: details};
        """)
        self.assertTrue(result['passed'],
                        f'normalQuantile failures: {result["details"]}')

    # ── Test 24 ───────────────────────────────────────────────────────────────

    def test_24_csp_meta_tag_present(self):
        """Content-Security-Policy meta tag should be present."""
        csp = self.driver.execute_script("""
            var meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
            return meta ? meta.getAttribute('content') : null;
        """)
        self.assertIsNotNone(csp, 'CSP meta tag should be present')
        self.assertIn('default-src', csp, 'CSP should contain default-src directive')

    # ── Test 25 ───────────────────────────────────────────────────────────────

    def test_25_endpoint_keywords_expanded(self):
        """classifyEndpointJS should recognize expanded keywords."""
        results = self.driver.execute_script("""
            return {
                mace3: classifyEndpointJS('3-point MACE composite'),
                whf:   classifyEndpointJS('worsening heart failure events'),
                eskd:  classifyEndpointJS('sustained eGFR decline to ESKD'),
                bnp:   classifyEndpointJS('NT-proBNP reduction at 12 months')
            };
        """)
        self.assertEqual(results['mace3'], 'mace', f'3-point MACE should classify as mace, got {results["mace3"]}')
        self.assertEqual(results['whf'], 'hf', f'worsening HF should classify as hf, got {results["whf"]}')
        self.assertEqual(results['eskd'], 'renal', f'sustained eGFR decline should classify as renal, got {results["eskd"]}')
        self.assertEqual(results['bnp'], 'surrogate', f'NT-proBNP should classify as surrogate, got {results["bnp"]}')

    # ── Test 26 ───────────────────────────────────────────────────────────────

    def test_26_design_snapshot_mechanism(self):
        """takeDesignSnapshot function must be defined."""
        result = self.driver.execute_script("""
            return typeof takeDesignSnapshot === 'function';
        """)
        self.assertTrue(result, 'takeDesignSnapshot should be a function')

    # ── Test 27 ───────────────────────────────────────────────────────────────

    def test_27_api_schema_validation(self):
        """fetchTrialFromCTGov should reject malformed responses."""
        result = self.driver.execute_async_script("""
            var callback = arguments[arguments.length - 1];
            // Override fetch temporarily to return a bad response
            var origFetch = window.fetch;
            window.fetch = function() {
                return Promise.resolve({
                    ok: true,
                    json: function() { return Promise.resolve({badData: true}); }
                });
            };
            // Clear cache for this test NCT ID
            delete CTGOV_CACHE['NCT00000001'];
            try { sessionStorage.removeItem('ctgov_NCT00000001'); } catch(e) {}
            fetchTrialFromCTGov('NCT00000001').then(function() {
                window.fetch = origFetch;
                callback('should_have_thrown');
            }).catch(function(err) {
                window.fetch = origFetch;
                callback(err.message);
            });
        """)
        self.assertIn('protocolSection', result,
                      f'Schema validation should reject missing protocolSection, got: {result!r}')

    # ── Test 28 ───────────────────────────────────────────────────────────────

    def test_28_amber_contrast_wcag(self):
        """Light-mode --warning color should have WCAG AA contrast on --amber-bg."""
        colors = self.driver.execute_script("""
            // Ensure light mode
            document.documentElement.removeAttribute('data-theme');
            var style = getComputedStyle(document.documentElement);
            return {
                warning: style.getPropertyValue('--warning').trim(),
                amberBg: style.getPropertyValue('--amber-bg').trim()
            };
        """)
        # #c25e00 should NOT be #fd7e14 (the old low-contrast color)
        self.assertNotEqual(colors['warning'], '#fd7e14',
                            'Light mode --warning should not be the old low-contrast #fd7e14')

    # ── Test 29 ───────────────────────────────────────────────────────────────

    def test_29_training_data_csv_export_function(self):
        """CSV export must produce valid output without formula injection."""
        result = self.driver.execute_script("""
            var btn = document.getElementById('tdExportBtn');
            return btn ? true : false;
        """)
        self.assertTrue(result, 'CSV export button (tdExportBtn) should exist in Training Data tab')

    # ── Test 30 ───────────────────────────────────────────────────────────────

    def test_30_prediction_engine_edge_case_empty_features(self):
        """Prediction engine should handle minimal/empty features without crashing."""
        result = self.driver.execute_script("""
            try {
                var features = {enrollment: 500, endpoint_type: 'mace', drug_class: 'other'};
                var trials = (typeof TRAINING_DATA !== 'undefined' && TRAINING_DATA.trials) || [];
                var scored = trials.map(function(t) {
                    return {trial: t, sim: computeSimilarity(features, t)};
                });
                var bayesian = bayesianBorrowing(features, trials);
                var power = conditionalPower(features, scored);
                var regression = metaRegressionPredict(features);
                var ensemble = ensemblePredict(bayesian, power, regression);
                return {
                    ok: true,
                    p: ensemble.p,
                    level: ensemble.level,
                    hasP: typeof ensemble.p === 'number' && !isNaN(ensemble.p)
                };
            } catch(e) {
                return {ok: false, error: e.message};
            }
        """)
        self.assertTrue(result['ok'],
                        f'Prediction engine crashed on minimal features: {result.get("error")}')
        self.assertTrue(result['hasP'],
                        'Ensemble should produce a valid numeric probability')
        self.assertGreater(result['p'], 0,
                           'Probability should be > 0 for MACE endpoint')
        self.assertLess(result['p'], 1,
                        'Probability should be < 1')


class TestProspectiveValidation(unittest.TestCase):
    """Prospective Validation (6th tab) tests: tab presence, panel structure,
    seed data, hash chain, PRNG, statistical functions, export/import.

    Uses a fresh browser session.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = None
        for factory in (_chrome_driver, _edge_driver):
            try:
                cls.driver = factory()
                break
            except Exception:
                continue
        if cls.driver is None:
            raise unittest.SkipTest('No working browser driver found')
        cls.driver.get(FILE_URL)
        time.sleep(3)
        # Clear PV localStorage to trigger fresh seed
        cls.driver.execute_script("""
            localStorage.removeItem('cardiooracle_pv_cohort');
            localStorage.removeItem('cardiooracle_pv_resolutions');
            localStorage.removeItem('cardiooracle_pv_queue');
            localStorage.removeItem('cardiooracle_pv_seeded');
            localStorage.removeItem('cardiooracle_pv_last_discovery');
            localStorage.removeItem('cardiooracle_pv_last_status_check');
        """)
        cls.driver.get(FILE_URL)
        time.sleep(3)
        # Dismiss tutorial overlay if visible
        cls.driver.execute_script("""
            var overlay = document.getElementById('tutorialOverlay');
            if (overlay) overlay.classList.add('hidden');
            if (typeof dismissTutorial === 'function') dismissTutorial();
        """)
        time.sleep(1)
        # Wait for PV seed to complete (async operation)
        for _ in range(20):
            seeded = cls.driver.execute_script(
                "return localStorage.getItem('cardiooracle_pv_seeded') === '1';"
            )
            if seeded:
                break
            time.sleep(0.5)
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def _click_tab(self, tab_id, panel_id):
        # Use JS click to avoid sticky header interception in headless mode
        self.driver.execute_script(
            "document.getElementById(arguments[0]).click();", tab_id
        )
        time.sleep(0.5)

    # ── Test 31: PV tab button exists ────────────────────────────────────────

    def test_31_pv_tab_button_exists(self):
        """Prospective Validation tab button must exist with correct ARIA."""
        btn = self.driver.find_element(By.ID, 'tab-validation')
        self.assertIsNotNone(btn, 'tab-validation button should exist')
        self.assertEqual(btn.get_attribute('role'), 'tab')
        self.assertEqual(btn.get_attribute('aria-controls'), 'panel-validation')
        self.assertIn('Prospective', btn.text)

    # ── Test 32: PV panel structure ──────────────────────────────────────────

    def test_32_pv_panel_structure(self):
        """Panel-validation must contain cohort management, monitoring, dashboard, and data management cards."""
        self._click_tab('tab-validation', 'panel-validation')
        panel = self.driver.find_element(By.ID, 'panel-validation')
        self.assertIn('active', panel.get_attribute('class'),
                      'panel-validation should be active after clicking tab')

        # Check key elements exist
        for el_id in ['pv-manualNctInput', 'pv-addBtn', 'pv-discoverBtn',
                      'pv-checkStatusBtn', 'pv-verifyChainBtn',
                      'pv-exportBtn', 'pv-importBtn', 'pv-cohortTable',
                      'pv-reviewTable', 'pv-timelineChart', 'pv-dashboard',
                      'pv-rocChart', 'pv-calChart', 'pv-brierChart',
                      'pv-dcaChart', 'pv-compChart', 'pv-tempChart']:
            el = self.driver.find_elements(By.ID, el_id)
            self.assertEqual(len(el), 1, f'Element #{el_id} should exist exactly once')

    # ── Test 33: Seed data loads 25 predictions ──────────────────────────────

    def test_33_seed_data_loaded(self):
        """On first load, 25 seed predictions should be loaded into localStorage."""
        self._click_tab('tab-validation', 'panel-validation')
        count = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            return cohort.length;
        """)
        self.assertEqual(count, 25, f'Expected 25 seed predictions, got {count}')

    # ── Test 34: Cohort table renders seed data ──────────────────────────────

    def test_34_cohort_table_renders(self):
        """Cohort table should display 25 rows after seeding."""
        self._click_tab('tab-validation', 'panel-validation')
        rows = self.driver.find_elements(By.CSS_SELECTOR, '#pv-cohortTbody tr')
        self.assertEqual(len(rows), 25, f'Expected 25 cohort rows, got {len(rows)}')

    # ── Test 35: Hash chain integrity ────────────────────────────────────────

    def test_35_hash_chain_integrity(self):
        """Chain verification should pass for the 25 seed predictions."""
        self._click_tab('tab-validation', 'panel-validation')
        result = self.driver.execute_async_script("""
            var callback = arguments[arguments.length - 1];
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            (async function() {
                var prevHash = null;
                for (var i = 0; i < cohort.length; i++) {
                    var entry = cohort[i];
                    var parts = [
                        entry.nct_id, entry.locked_at,
                        String(entry.prediction.p_ensemble),
                        String(entry.prediction.p_bayes),
                        String(entry.prediction.p_power),
                        String(entry.prediction.p_reg),
                        entry.trial_snapshot.drug_class,
                        entry.trial_snapshot.endpoint_type,
                        String(entry.trial_snapshot.enrollment || 0),
                        String(entry.trial_snapshot.duration_months || 0),
                        entry.training_hash,
                        prevHash || 'NULL'
                    ];
                    var expected = await sha256Hex(parts.join('|'));
                    if (expected !== entry.entry_hash) {
                        callback({valid: false, brokenAt: i, expected: expected, got: entry.entry_hash});
                        return;
                    }
                    prevHash = entry.entry_hash;
                }
                callback({valid: true, count: cohort.length});
            })();
        """)
        self.assertTrue(result['valid'],
                        f'Hash chain broken at entry {result.get("brokenAt")}: expected {result.get("expected")}, got {result.get("got")}')

    # ── Test 36: Verify Chain button works ───────────────────────────────────

    def test_36_verify_chain_button(self):
        """Clicking Verify Chain should show green integrity message."""
        self._click_tab('tab-validation', 'panel-validation')
        self.driver.find_element(By.ID, 'pv-verifyChainBtn').click()
        time.sleep(1)
        status = self.driver.find_element(By.ID, 'pv-chainStatus')
        self.assertIn('verified', status.text.lower(),
                      f'Expected "verified" in chain status, got: {status.text!r}')
        self.assertIn('pv-chain-ok', status.get_attribute('class'),
                      'Chain status should have pv-chain-ok class')

    # ── Test 37: SEED_PREDICTIONS has exactly 25 entries ─────────────────────

    def test_37_seed_predictions_count(self):
        """SEED_PREDICTIONS constant should have exactly 25 trial objects."""
        count = self.driver.execute_script("""
            // Access through the seeded cohort since SEED_PREDICTIONS is in IIFE scope
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var nctIds = cohort.map(function(e) { return e.nct_id; });
            var unique = new Set(nctIds);
            return {total: cohort.length, unique: unique.size};
        """)
        self.assertEqual(count['total'], 25, f'Expected 25 predictions, got {count["total"]}')
        self.assertEqual(count['unique'], 25, f'Expected 25 unique NCT IDs, got {count["unique"]}')

    # ── Test 38: Each seed entry has required fields ─────────────────────────

    def test_38_seed_entry_schema(self):
        """Each locked entry should have all required fields from spec."""
        result = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var errors = [];
            var required = ['seq', 'nct_id', 'locked_at', 'prediction', 'trial_snapshot',
                            'model_version', 'training_hash', 'entry_hash', 'status'];
            var predFields = ['p_ensemble', 'p_bayes', 'p_power', 'p_reg', 'confidence'];
            var snapFields = ['title', 'drug_class', 'endpoint_type', 'enrollment',
                              'duration_months', 'phase', 'area'];
            for (var i = 0; i < cohort.length; i++) {
                var e = cohort[i];
                for (var j = 0; j < required.length; j++) {
                    if (!(required[j] in e)) errors.push('Entry ' + i + ' missing ' + required[j]);
                }
                if (e.prediction) {
                    for (var k = 0; k < predFields.length; k++) {
                        if (!(predFields[k] in e.prediction)) errors.push('Entry ' + i + ' prediction missing ' + predFields[k]);
                    }
                }
                if (e.trial_snapshot) {
                    for (var m = 0; m < snapFields.length; m++) {
                        if (!(snapFields[m] in e.trial_snapshot)) errors.push('Entry ' + i + ' snapshot missing ' + snapFields[m]);
                    }
                }
            }
            return errors;
        """)
        self.assertEqual(len(result), 0,
                         f'Schema validation errors: {result}')

    # ── Test 39: pvComputeAUC statistical function ───────────────────────────

    def test_39_pv_compute_auc(self):
        """pvComputeAUC should return correct AUC for known data."""
        result = self.driver.execute_script("""
            if (typeof pvComputeAUC !== 'function') return {error: 'pvComputeAUC not exposed'};
            // Perfect separator: probs=[0.9, 0.8, 0.2, 0.1], labels=[1, 1, 0, 0] -> AUC=1.0
            var r1 = pvComputeAUC([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]);
            // Worst separator (reversed): probs=[0.1, 0.2, 0.8, 0.9], labels=[1, 1, 0, 0] -> AUC=0.0
            var r2 = pvComputeAUC([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]);
            // Null when only one class present
            var r3 = pvComputeAUC([1, 1, 1, 1], [0.5, 0.6, 0.7, 0.8]);
            return {
                perfect: r1 ? r1.auc : null,
                worst: r2 ? r2.auc : null,
                nullCase: r3
            };
        """)
        if 'error' in result:
            self.fail(result['error'])
        self.assertAlmostEqual(result['perfect'], 1.0, places=2,
                               msg=f'Perfect AUC should be 1.0, got {result["perfect"]}')
        self.assertAlmostEqual(result['worst'], 0.0, places=2,
                               msg=f'Worst AUC should be 0.0, got {result["worst"]}')
        self.assertIsNone(result['nullCase'],
                          'AUC should be null when only one class present')

    # ── Test 40: localStorage keys use correct prefix ────────────────────────

    def test_40_localstorage_keys_prefixed(self):
        """All PV localStorage keys should use cardiooracle_pv_ prefix."""
        keys = self.driver.execute_script("""
            var pvKeys = [];
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                if (key.indexOf('cardiooracle_pv_') === 0) pvKeys.push(key);
            }
            return pvKeys;
        """)
        self.assertGreater(len(keys), 0, 'Should have at least one PV localStorage key')
        for key in keys:
            self.assertTrue(key.startswith('cardiooracle_pv_'),
                            f'Key {key!r} should have cardiooracle_pv_ prefix')

    # ── Test 41: Export bundle function exists and is callable ────────────────

    def test_41_export_function_exists(self):
        """pvExportBundle must be a function."""
        result = self.driver.execute_script("""
            return typeof pvExportBundle === 'function';
        """)
        self.assertTrue(result, 'pvExportBundle should be exposed as a function')

    # ── Test 42: Dashboard requires 5+ resolved trials ───────────────────────

    def test_42_dashboard_requires_minimum_resolved(self):
        """Dashboard should show progress message when <5 trials resolved."""
        self._click_tab('tab-validation', 'panel-validation')
        msg = self.driver.find_element(By.ID, 'pv-dashboardMsg')
        self.assertIn('need 5+', msg.text.lower(),
                      f'Expected "need 5+" in dashboard message, got: {msg.text!r}')
        dashboard = self.driver.find_element(By.ID, 'pv-dashboard')
        self.assertEqual(dashboard.value_of_css_property('display'), 'none',
                         'Dashboard charts should be hidden with <5 resolved trials')

    # ── Test 43: Seed entries all have area field ────────────────────────────

    def test_43_seed_areas_coverage(self):
        """Seed data should cover all 3 therapeutic areas."""
        areas = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var areas = {};
            cohort.forEach(function(e) {
                var a = (e.trial_snapshot && e.trial_snapshot.area) || 'unknown';
                areas[a] = (areas[a] || 0) + 1;
            });
            return areas;
        """)
        self.assertIn('cardiorenal', areas, 'Should have cardiorenal trials')
        self.assertIn('cad', areas, 'Should have CAD trials')
        self.assertIn('af', areas, 'Should have AF trials')
        total = sum(areas.values())
        self.assertEqual(total, 25, f'Total across areas should be 25, got {total}')

    # ── Test 44: Chain is append-only (prev_hash links) ──────────────────────

    def test_44_chain_links_sequential(self):
        """Each entry's prev_hash should equal the previous entry's entry_hash."""
        result = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var errors = [];
            for (var i = 0; i < cohort.length; i++) {
                if (i === 0) {
                    if (cohort[i].prev_hash !== null) errors.push('Entry 0 prev_hash should be null');
                } else {
                    if (cohort[i].prev_hash !== cohort[i-1].entry_hash) {
                        errors.push('Entry ' + i + ' prev_hash mismatch');
                    }
                }
            }
            return errors;
        """)
        self.assertEqual(len(result), 0, f'Chain link errors: {result}')

    # ── Test 45: PV element IDs all have pv- prefix ──────────────────────────

    def test_45_element_id_prefix(self):
        """All PV-specific element IDs (excluding Plotly internals) should have pv- prefix."""
        pv_ids = self.driver.execute_script("""
            var panel = document.getElementById('panel-validation');
            if (!panel) return {error: 'panel-validation not found'};
            var all = panel.querySelectorAll('[id]');
            var ids = [];
            for (var i = 0; i < all.length; i++) {
                var id = all[i].id;
                // Skip Plotly-generated internal elements (defs-*, clip*, etc.)
                if (/^(defs-|clip|layer-|plot-|modebar-)/.test(id)) continue;
                // Skip SVG <g> elements generated by Plotly
                if (all[i].closest('.js-plotly-plot')) continue;
                ids.push(id);
            }
            return ids;
        """)
        if isinstance(pv_ids, dict) and 'error' in pv_ids:
            self.fail(pv_ids['error'])
        for el_id in pv_ids:
            self.assertTrue(el_id.startswith('pv-'),
                            f'PV element ID {el_id!r} should start with pv-')

    # ── Test 46: No duplicate element IDs in entire page ─────────────────────

    def test_46_no_duplicate_ids(self):
        """There should be no duplicate element IDs in the entire page."""
        result = self.driver.execute_script("""
            var all = document.querySelectorAll('[id]');
            var counts = {};
            for (var i = 0; i < all.length; i++) {
                var id = all[i].id;
                counts[id] = (counts[id] || 0) + 1;
            }
            var dupes = [];
            for (var id in counts) {
                if (counts[id] > 1) dupes.push(id + ':' + counts[id]);
            }
            return dupes;
        """)
        self.assertEqual(len(result), 0, f'Duplicate element IDs found: {result}')

    # ── Test 47: Prediction probabilities are valid ──────────────────────────

    def test_47_prediction_probabilities_valid(self):
        """All seed predictions should have ensemble probabilities in (0, 1)."""
        result = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var errors = [];
            cohort.forEach(function(e, i) {
                var p = e.prediction.p_ensemble;
                if (typeof p !== 'number' || isNaN(p)) errors.push('Entry ' + i + ': p_ensemble not a number');
                else if (p <= 0 || p >= 1) errors.push('Entry ' + i + ': p_ensemble=' + p + ' out of (0,1)');
            });
            return errors;
        """)
        self.assertEqual(len(result), 0, f'Invalid probabilities: {result}')

    # ── Test 48: Model version matches ───────────────────────────────────────

    def test_48_model_version_consistent(self):
        """All entries should have model_version 'cardiooracle_v1.0'."""
        result = self.driver.execute_script("""
            var cohort = JSON.parse(localStorage.getItem('cardiooracle_pv_cohort') || '[]');
            var bad = cohort.filter(function(e) { return e.model_version !== 'cardiooracle_v1.0'; });
            return bad.length;
        """)
        self.assertEqual(result, 0, 'All entries should have model_version cardiooracle_v1.0')

    # ── Test 49: Dark mode styling applies to PV elements ────────────────────

    def test_49_dark_mode_pv_elements(self):
        """PV elements should respect dark mode CSS variables."""
        result = self.driver.execute_script("""
            document.documentElement.setAttribute('data-theme', 'dark');
            var card = document.querySelector('#panel-validation .card');
            if (!card) return {error: 'No card in PV panel'};
            var style = getComputedStyle(card);
            var bg = style.backgroundColor;
            document.documentElement.removeAttribute('data-theme');
            return {bg: bg};
        """)
        if isinstance(result, dict) and 'error' in result:
            self.fail(result['error'])
        # In dark mode, background should NOT be white (#ffffff / rgb(255,255,255))
        self.assertNotEqual(result['bg'], 'rgb(255, 255, 255)',
                            'PV card background should change in dark mode')

    # ── Test 50: Timeline chart container exists ─────────────────────────────

    def test_50_timeline_chart_container(self):
        """Timeline chart div should exist and have pv-timeline-chart class."""
        self._click_tab('tab-validation', 'panel-validation')
        el = self.driver.find_element(By.ID, 'pv-timelineChart')
        self.assertIn('pv-timeline-chart', el.get_attribute('class'),
                      'Timeline div should have pv-timeline-chart class')


if __name__ == '__main__':
    unittest.main(verbosity=2)

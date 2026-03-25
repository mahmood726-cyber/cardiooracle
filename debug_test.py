import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

_WDM_CACHE_ROOT = os.path.expanduser('~/.wdm/drivers/chromedriver/win64')
driver_path = None
if os.path.isdir(_WDM_CACHE_ROOT):
    for _ver in sorted(os.listdir(_WDM_CACHE_ROOT), reverse=True):
        for _subdir in ('chromedriver-win32', ''):
            _candidate = os.path.join(_WDM_CACHE_ROOT, _ver, _subdir, 'chromedriver.exe').rstrip(os.sep)
            if os.path.isfile(_candidate):
                driver_path = _candidate
                break
        if driver_path:
            break

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-gpu')
opts.add_argument('--incognito')
opts.add_argument('--window-size=1280,900')
opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

service = Service(executable_path=driver_path) if driver_path else None
if service:
    driver = webdriver.Chrome(service=service, options=opts)
else:
    driver = webdriver.Chrome(options=opts)

HTML_PATH = os.path.abspath('CardioOracle.html')
FILE_URL = 'file:///' + HTML_PATH.replace('\\', '/')
driver.get(FILE_URL)
time.sleep(2)

print("=== TAB SWITCHING ===")
tab = driver.find_element(By.ID, 'tab-design')
print('tab-design tabindex:', tab.get_attribute('tabindex'))
print('tab-design displayed:', tab.is_displayed())
print('tab-design enabled:', tab.is_enabled())

panel = driver.find_element(By.ID, 'panel-design')
print('panel-design class BEFORE click:', panel.get_attribute('class'))

# JS click
driver.execute_script('arguments[0].click();', tab)
time.sleep(0.5)
print('panel-design class AFTER JS click:', panel.get_attribute('class'))
print('aria-selected AFTER JS click:', tab.get_attribute('aria-selected'))

# Regular click
tab2 = driver.find_element(By.ID, 'tab-design')
tab2.click()
time.sleep(0.5)
print('panel-design class AFTER regular click:', driver.find_element(By.ID, 'panel-design').get_attribute('class'))

print("\n=== DARK MODE ===")
btn = driver.find_element(By.ID, 'darkModeBtn')
print('darkModeBtn text:', btn.text)
print('html data-theme BEFORE:', driver.find_element(By.TAG_NAME, 'html').get_attribute('data-theme'))
driver.execute_script('arguments[0].click();', btn)
time.sleep(0.3)
print('html data-theme AFTER JS click:', driver.find_element(By.TAG_NAME, 'html').get_attribute('data-theme'))

print("\n=== PREDICTION ERROR ===")
nct = driver.find_element(By.ID, 'nctInput')
nct.send_keys('INVALID')
pBtn = driver.find_element(By.ID, 'predictBtn')
pBtn.click()
time.sleep(0.5)
errEl = driver.find_element(By.ID, 'predictionError')
print('predictionError class:', errEl.get_attribute('class'))
print('predictionError text (selenium):', repr(errEl.text))
print('predictionError textContent via JS:', repr(driver.execute_script('return document.getElementById("predictionError").textContent')))

print("\n=== CONSOLE ERRORS ===")
logs = driver.get_log('browser')
for l in logs:
    if l.get('level') != 'INFO':
        print(l)

print("\n=== CONFIG SELECT ===")
cs = driver.find_element(By.ID, 'configSelect')
opts_els = cs.find_elements(By.TAG_NAME, 'option')
print('configSelect option count:', len(opts_els))
for o in opts_els:
    print(' -', o.get_attribute('value'), ':', o.text)

print("\n=== ABOUT BUTTON ===")
ab = driver.find_element(By.ID, 'aboutBtn')
print('aboutBtn displayed:', ab.is_displayed())
print('aboutBtn enabled:', ab.is_enabled())
driver.execute_script('arguments[0].click();', ab)
time.sleep(0.4)
modal = driver.find_element(By.ID, 'aboutModal')
print('modal class after JS click:', modal.get_attribute('class'))

driver.quit()
print("\nDONE")

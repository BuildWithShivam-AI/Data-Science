from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --------------------------
# Chrome Options
# --------------------------

options = webdriver.ChromeOptions()

options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

driver.execute_script(
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)

wait = WebDriverWait(driver, 40)

# --------------------------
# Open Website
# --------------------------

url = "https://myaadhaar.uidai.gov.in/verify-email-mobile/en"

driver.get(url)

time.sleep(10)

# --------------------------
# Basic Information
# --------------------------

print("="*60)
print("Title :", driver.title)
print("URL   :", driver.current_url)
print("="*60)

driver.save_screenshot("uidai_page.png")
print("Screenshot saved as uidai_page.png")

# --------------------------
# Check Inputs
# --------------------------

inputs = driver.find_elements(By.TAG_NAME, "input")

print("\nINPUT FIELDS FOUND :", len(inputs))

for i, inp in enumerate(inputs):

    print("---------------------------")
    print("Input :", i)
    print("Type :", inp.get_attribute("type"))
    print("Name :", inp.get_attribute("name"))
    print("ID :", inp.get_attribute("id"))
    print("Placeholder :", inp.get_attribute("placeholder"))

# --------------------------
# Check Iframes
# --------------------------

frames = driver.find_elements(By.TAG_NAME, "iframe")

print("\nIFRAMES FOUND :", len(frames))

for i, frame in enumerate(frames):
    print(i, frame.get_attribute("src"))

# --------------------------
# Try Every Frame
# --------------------------

if len(frames) > 0:

    for index in range(len(frames)):

        driver.switch_to.default_content()
        driver.switch_to.frame(index)

        inputs = driver.find_elements(By.TAG_NAME, "input")

        print(f"\nFrame {index} has {len(inputs)} input fields")

driver.switch_to.default_content()

print("\nDone.")

input("\nPress ENTER to close...")

driver.quit()
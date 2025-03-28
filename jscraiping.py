from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_with_selenium(url):
    # Chrome options setting
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)

    # WebDriver configuration
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Access the web page
        driver.get(url)

        # Wait until the title is present or until a timeout (10 seconds)
        WebDriverWait(driver, 10).until(EC.title_is_not(""))

        # Get the page title
        title = driver.title

        # Wait until all paragraph elements are present
        paragraphs = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, 'p'))
        )
        # Extract text from each paragraph
        paragraph_texts = [p.text for p in paragraphs]

        return {
            "title": title,
            "paragraphs": paragraph_texts
        }

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    finally:
        # Close the browser
        driver.quit()

# Usage example
if __name__ == "__main__":
    url = "https://example.com"  # Specify the URL of the site you want to scrape
    result = scrape_with_selenium(url)

    if result:
        print(f"Page Title: {result['title']}")
        print("\nFirst 3 Paragraphs:")
        for i, para in enumerate(result['paragraphs'][:3], 1):
            print(f"{i}. {para[:100]}...")  # Show only the first 100 characters of each paragraph

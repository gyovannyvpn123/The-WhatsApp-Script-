import json
import logging
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WhatsAppTester:
    def __init__(self, credentials):
        self.credentials = credentials
        self.driver = None
    
    def initialize_driver(self):
        """Initialize the Selenium WebDriver with appropriate options."""
        try:
            chrome_options = Options()
            # Comment out headless mode to see the browser window (for debugging)
            # chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("WebDriver inițializat cu succes")
            return True
        except Exception as e:
            logger.error(f"Eroare la inițializarea WebDriver: {str(e)}")
            return False
    
    def login_to_whatsapp(self):
        """Log in to WhatsApp Web using credentials."""
        try:
            self.driver.get("https://web.whatsapp.com/")
            logger.info("Accesat web.whatsapp.com")
            
            # Handle WhatsApp Web authentication using credentials
            if "noiseKey" in self.credentials:
                # Handle new format credentials (as in creds.json)
                logger.info("Folosire credențiale din creds.json")
                
                # Serialize credentials into localStorage format
                credentials_json = json.dumps(self.credentials)
                # Now set it in localStorage
                self.driver.execute_script(f"""
                    localStorage.setItem('creds', JSON.stringify({json.dumps(credentials_json)}));
                """)
                
                if "me" in self.credentials and "id" in self.credentials["me"]:
                    whatsapp_id = self.credentials["me"]["id"].split(':')[0]
                    logger.info(f"Setare ID WhatsApp: {whatsapp_id}")
                
                self.driver.refresh()
            
            logger.info("Așteaptă încărcarea WhatsApp Web...")
            # Wait for WhatsApp to load (look for the search box which indicates successful login)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='3']"))
            )
            
            logger.info("Autentificare reușită în WhatsApp Web")
            return True
        
        except TimeoutException:
            logger.error("Timeout la așteptarea încărcării WhatsApp Web")
            
            # Try to check for QR code - in case we need manual login
            try:
                qr_code = self.driver.find_element(By.XPATH, "//canvas")
                if qr_code:
                    logger.info("Cod QR detectat. Vă rugăm să scanați codul QR pentru conectare.")
                    # Take screenshot of QR code
                    self.driver.save_screenshot("whatsapp_qr_code.png")
                    logger.info("Captură de ecran cu codul QR salvată în 'whatsapp_qr_code.png'")
                    
                    input("Scanați codul QR și apăsați ENTER pentru a continua...")
                    
                    # Allow an additional time to scan QR code
                    WebDriverWait(self.driver, 60).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='3']"))
                    )
                    logger.info("Autentificare reușită după scanarea codului QR!")
                    return True
            except:
                logger.error("Nu s-a putut detecta codul QR")
                
            return False
        except Exception as e:
            logger.error(f"Eroare la autentificarea în WhatsApp Web: {str(e)}")
            return False
    
    def send_message(self, phone_number, message):
        """Send a message to a specific phone number."""
        try:
            # Format the phone number (remove any spaces, dashes, etc.)
            formatted_number = ''.join(filter(str.isdigit, phone_number))
            
            # Navigate to the chat with this number
            chat_url = f"https://web.whatsapp.com/send?phone={formatted_number}&text&source&data&app_absent"
            logger.info(f"Navigare către chat: {chat_url}")
            self.driver.get(chat_url)
            
            # Wait for the chat to load (message input field)
            logger.info("Așteptare încărcare chat...")
            message_box = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='10']"))
            )
            
            # Type the message
            logger.info("Introducere text mesaj...")
            message_box.send_keys(message)
            
            # Click send button
            logger.info("Apăsare buton trimitere...")
            send_button = self.driver.find_element(By.XPATH, "//span[@data-icon='send']")
            send_button.click()
            
            # Wait for the message to be sent (look for the "delivered" or "read" status)
            logger.info("Așteptare confirmare trimitere...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[@data-icon='msg-dblcheck' or @data-icon='msg-check']"))
            )
            
            logger.info(f"Mesaj trimis cu succes către {phone_number}")
            
            # Take a screenshot for verification
            self.driver.save_screenshot("message_sent.png")
            logger.info("Captură de ecran salvată în 'message_sent.png'")
            
            return True
        
        except TimeoutException:
            logger.error(f"Timeout la așteptarea încărcării chat-ului cu {phone_number}")
            return False
        except NoSuchElementException as e:
            logger.error(f"Element negăsit: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Eroare la trimiterea mesajului către {phone_number}: {str(e)}")
            return False


def run_test(target_number="+40712345678", message_text="Acesta este un mesaj de test"):
    try:
        # Load credentials from file
        logger.info("Încărcare credențiale din fișier...")
        with open('attached_assets/creds.json', 'r') as f:
            credentials = json.load(f)
        
        # Log the target number and message for visibility
        logger.info(f"Număr de telefon țintă: {target_number}")
        logger.info(f"Mesaj de test: {message_text}")
        
        # Create tester instance
        tester = WhatsAppTester(credentials)
        
        # Initialize WebDriver
        if not tester.initialize_driver():
            logger.error("Nu s-a putut inițializa WebDriver-ul!")
            return False
        
        # Login to WhatsApp
        if not tester.login_to_whatsapp():
            logger.error("Autentificare eșuată! Asigurați-vă că fișierul creds.json este valid.")
            if tester.driver:
                tester.driver.quit()
            return False
        
        # Send a single message
        success = tester.send_message(target_number, message_text)
        
        # Cleanup
        time.sleep(5)  # Wait a bit to ensure screenshots are saved
        if tester.driver:
            tester.driver.quit()
        
        return success
        
    except Exception as e:
        logger.error(f"Eroare în timpul testului: {str(e)}")
        return False


if __name__ == "__main__":
    print("=== TEST DIRECT TRIMITERE MESAJ WHATSAPP ===")
    print("Acest script va testa trimiterea unui mesaj real prin WhatsApp.")
    print("NOTĂ: Este posibil să fie nevoie să scanați un cod QR pentru autentificare.")
    
    # Specificați numărul dvs. de telefon aici pentru testare
    target_number = "+4071XXXXXXX"  # De înlocuit cu numărul real
    message_text = "Test mesaj trimis din aplicația WhatsApp Automation Server"
    
    result = run_test(target_number, message_text)
    
    if result:
        print("\n✓ Testul a fost finalizat cu succes! Mesajul a fost trimis.")
    else:
        print("\n✗ Testul a eșuat! Verificați log-urile pentru detalii.")
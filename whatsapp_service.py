import time
import logging
import json
import base64
import tempfile
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import os

class WhatsAppMessenger:
    def __init__(self, credentials):
        self.credentials = credentials
        self.logger = logging.getLogger(__name__)
        self.driver = None
    
    def initialize_driver(self):
        """Initialize the Selenium WebDriver with appropriate options."""
        try:
            chrome_options = Options()
            
            # Verificăm dacă suntem pe Render (identificat prin variabila de mediu RENDER)
            is_render = os.environ.get('RENDER') == 'true'
            
            if is_render:
                # În mediul Render folosim un browser non-headless cu Xvfb
                self.logger.info("Rulare în mediul Render cu Xvfb")
                # Nu folosim headless, dar setăm alte opțiuni necesare
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
            else:
                # În mediul Replit sau local, folosim headless (deși nu va funcționa 
                # pentru WhatsApp în Replit)
                self.logger.info("Rulare în mediu non-Render, folosind headless")
                chrome_options.add_argument("--headless=new")
            
            # Opțiuni comune pentru ambele medii
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-gpu")
            
            # Setări de browser pentru a evita detectarea automatizării
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Adăugăm un director pentru profilul Chrome pentru a păstra datele sesiunii
            # Dacă suntem pe Render, folosim un director persistent
            if is_render:
                user_data_dir = "/tmp/chrome-profile"
            else:
                # În alte medii, folosim un director temporar
                user_data_dir = os.path.join(tempfile.gettempdir(), "chrome-profile")
            
            os.makedirs(user_data_dir, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            
            # Add user data directory if provided in credentials
            if "user_data_dir" in self.credentials:
                chrome_options.add_argument(f"--user-data-dir={self.credentials['user_data_dir']}")
            
            # Inițializăm ChromeDriver cu webdriver-manager pentru instalare automată chromedriver
            if is_render:
                # În Render folosim calea preinstalată de ChromeDriver
                self.driver = webdriver.Chrome(options=chrome_options)
            else:
                # În alte medii folosim webdriver-manager pentru a descărca automat chromedriver potrivit
                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
            
            # Creștem dimensiunea ferestrei pentru a asigura că toate elementele sunt vizibile
            self.driver.set_window_size(1920, 1080)
            
            # Adăugăm comenzi CDP pentru a evita detectarea automatizării
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            })
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                    
                    // Overriding the permissions API
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' || parameters.name === 'clipboard-read' || parameters.name === 'clipboard-write' ?
                        Promise.resolve({state: 'granted'}) :
                        originalQuery(parameters)
                    );
                """
            })
            
            # Setăm un timeout implicit pentru așteptarea elementelor
            self.driver.implicitly_wait(10)  # 10 secunde
            
            self.logger.info("WebDriver inițializat cu succes cu măsuri anti-detecție")
            return True
        except Exception as e:
            self.logger.error(f"Eroare la inițializarea WebDriver: {str(e)}")
            return False
    
    def login_to_whatsapp(self):
        """Log in to WhatsApp Web using credentials."""
        try:
            self.driver.get("https://web.whatsapp.com/")
            
            # Handle WhatsApp Web authentication using credentials
            # Check for standard format credentials
            if "token" in self.credentials:
                # Use LocalStorage to set auth tokens (old method)
                self.driver.execute_script(
                    f"window.localStorage.setItem('WAToken1', '{self.credentials['token']}');"
                )
                self.driver.refresh()
            elif "noiseKey" in self.credentials:
                # Handle new format credentials (as in creds.json)
                # Store the credentials in localStorage
                self.logger.info("Using WhatsApp Web credentials from creds.json")
                
                # Serialize credentials into localStorage format
                credentials_json = json.dumps(self.credentials)
                # Now set it in localStorage
                self.driver.execute_script(f"""
                    localStorage.setItem('creds', JSON.stringify({json.dumps(credentials_json)}));
                """)
                
                # Also check if we have specific entries to set
                if "me" in self.credentials and "id" in self.credentials["me"]:
                    whatsapp_id = self.credentials["me"]["id"].split(':')[0]
                    self.logger.info(f"Setting WhatsApp user ID: {whatsapp_id}")
                    # You might need to set additional localStorage items depending on WhatsApp Web's requirements
                
                self.driver.refresh()
            
            # Wait for WhatsApp to load (look for the search box which indicates successful login)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='3']"))
            )
            
            self.logger.info("Successfully logged in to WhatsApp Web")
            return True
        
        except TimeoutException:
            self.logger.error("Timed out waiting for WhatsApp Web to load")
            
            # Try to check for QR code - in case we need manual login
            try:
                qr_code = self.driver.find_element(By.XPATH, "//canvas")
                if qr_code:
                    self.logger.info("QR Code detected. Please scan the QR code to log in.")
                    # Allow an additional time to scan QR code
                    WebDriverWait(self.driver, 120).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='3']"))
                    )
                    self.logger.info("Successfully logged in after QR code scan!")
                    return True
            except:
                pass
                
            return False
        except Exception as e:
            self.logger.error(f"Error logging in to WhatsApp Web: {str(e)}")
            return False
    
    def send_message(self, phone_number, message):
        """Send a message to a specific phone number."""
        try:
            # Format the phone number (remove any spaces, dashes, etc.)
            formatted_number = ''.join(filter(str.isdigit, phone_number))
            
            # Navigate to the chat with this number
            chat_url = f"https://web.whatsapp.com/send?phone={formatted_number}&text&source&data&app_absent"
            self.driver.get(chat_url)
            
            # Wait for the chat to load (message input field)
            message_box = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='10']"))
            )
            
            # Type the message
            message_box.send_keys(message)
            
            # Click send button
            send_button = self.driver.find_element(By.XPATH, "//span[@data-icon='send']")
            send_button.click()
            
            # Wait for the message to be sent (look for the "delivered" or "read" status)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[@data-icon='msg-dblcheck' or @data-icon='msg-check']"))
            )
            
            self.logger.info(f"Message sent to {phone_number}")
            return True
        
        except TimeoutException:
            self.logger.error(f"Timed out waiting for chat with {phone_number} to load")
            return False
        except NoSuchElementException as e:
            self.logger.error(f"Element not found: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message to {phone_number}: {str(e)}")
            return False
    
    def start_messaging(self, target_number, message_text, delay_seconds, stop_event, campaign_id):
        """Start the messaging campaign."""
        try:
            # Initialize the WebDriver
            if not self.initialize_driver():
                self.logger.error("Failed to initialize WebDriver. Stopping messaging campaign.")
                self.update_campaign_status(campaign_id, False)
                return
            
            # Login to WhatsApp
            if not self.login_to_whatsapp():
                self.logger.error("Failed to log in to WhatsApp. Stopping messaging campaign.")
                self.update_campaign_status(campaign_id, False)
                self.driver.quit()
                return
            
            # Parse the target number(s)
            target_numbers = [num.strip() for num in target_number.split(',')]
            
            messages_sent = 0
            # Send messages to each number in a continuous loop
            while not stop_event.is_set():
                for number in target_numbers:
                    if stop_event.is_set():
                        self.logger.info("Stop event received. Stopping messaging campaign.")
                        break
                    
                    if self.send_message(number, message_text):
                        messages_sent += 1
                        self.update_messages_sent(campaign_id, messages_sent)
                    
                    # Wait for the specified delay
                    if delay_seconds > 0 and not stop_event.is_set():
                        time.sleep(delay_seconds)
            
            # Update campaign status
            self.update_campaign_status(campaign_id, False)
            
            # Clean up
            self.driver.quit()
            
        except Exception as e:
            self.logger.error(f"Error in messaging campaign: {str(e)}")
            self.update_campaign_status(campaign_id, False)
            if self.driver:
                self.driver.quit()
    
    def update_campaign_status(self, campaign_id, is_active):
        """Update the campaign status in the database."""
        from app import app, db
        from models import MessageCampaign
        with app.app_context():
            campaign = MessageCampaign.query.get(campaign_id)
            if campaign:
                campaign.is_active = is_active
                db.session.commit()
    
    def update_messages_sent(self, campaign_id, count):
        """Update the number of messages sent in the database."""
        from app import app, db
        from models import MessageCampaign
        with app.app_context():
            campaign = MessageCampaign.query.get(campaign_id)
            if campaign:
                campaign.messages_sent = count
                db.session.commit()
